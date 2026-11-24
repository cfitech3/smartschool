"""
Vues : Bourses, Réductions & Échéanciers personnalisés par élève.
"""
from decimal import Decimal, InvalidOperation

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.db.models import Count, Q, Sum
from django.shortcuts import get_object_or_404, redirect, render

from accounts.permissions import permission_required, require_etab
from core.cycle_filter import get_eleves_actifs
from eleves.models import Eleve
from etablissements.models import AnneeScolaire

from .models import ReductionFrais, TypeFrais
from .services_bourses import (
    appliquer_echeancier_personnalise, detecter_fratrie, parse_date,
    recalculer_echeances_eleve, resume_echeancier,
)


def _annee_active(etab):
    return AnneeScolaire.objects.filter(etablissement=etab, is_active=True).first()


def _log(request, etab, cible, detail):
    try:
        from etablissements.models import JournalAction
        JournalAction.log(request, 'autre', cible=cible, etablissement=etab, detail=detail)
    except Exception:
        import logging
        logging.getLogger(__name__).warning("Échec journalisation bourse (%s)", cible, exc_info=True)


@login_required
@permission_required("paiements")
@require_etab
def liste_bourses(request):
    """Tableau de bord des bourses et réductions de l'année active."""
    etab = request.etablissement
    annee = _annee_active(etab)
    categorie = request.GET.get('categorie', '')
    q = request.GET.get('q', '').strip()

    reductions = ReductionFrais.objects.filter(etablissement=etab, annee=annee) \
        .select_related('eleve', 'type_frais', 'accordee_par').order_by('eleve__nom', 'eleve__prenom')
    if categorie:
        reductions = reductions.filter(categorie=categorie)
    if q:
        reductions = reductions.filter(
            Q(eleve__nom__icontains=q) | Q(eleve__prenom__icontains=q)
            | Q(eleve__matricule__icontains=q) | Q(organisme_tiers__icontains=q)
        )

    base_qs = ReductionFrais.objects.filter(etablissement=etab, annee=annee)
    labels = dict(ReductionFrais.CATEGORIES)
    par_categorie = [
        {'code': r['categorie'], 'libelle': labels.get(r['categorie'], r['categorie']),
         'nb': r['nb'], 'total': r['total'] or 0}
        for r in base_qs.values('categorie').annotate(nb=Count('id'), total=Sum('montant')).order_by('-total')
    ]
    stats = {
        'nb': base_qs.count(),
        'nb_eleves': base_qs.values('eleve').distinct().count(),
        'total': base_qs.aggregate(t=Sum('montant'))['t'] or 0,
        'tiers': base_qs.exclude(organisme_tiers='').aggregate(t=Sum('montant'))['t'] or 0,
    }
    return render(request, 'finances/liste_bourses.html', {
        'reductions': reductions, 'annee': annee, 'stats': stats,
        'par_categorie': par_categorie, 'categories': ReductionFrais.CATEGORIES,
        'categorie': categorie, 'q': q,
    })


@login_required
@permission_required("paiements")
@require_etab
def ajouter_reduction(request):
    """Création ou modification (?pk=) d'une bourse / réduction."""
    etab = request.etablissement
    annee = _annee_active(etab)
    types_frais = TypeFrais.objects.filter(etablissement=etab).filter(Q(annee=annee) | Q(annee__isnull=True))

    instance = None
    if request.GET.get('pk'):
        instance = get_object_or_404(ReductionFrais, pk=request.GET.get('pk'), etablissement=etab)

    eleve_id = request.POST.get('eleve') or request.GET.get('eleve') or (instance.eleve_id if instance else None)
    eleve_pre = None
    if eleve_id:
        try:
            eleve_pre = Eleve.objects.filter(pk=int(eleve_id), etablissement=etab).first()
        except (TypeError, ValueError):
            eleve_pre = None

    if request.method == "POST":
        if not annee:
            messages.error(request, "Aucune année scolaire active.")
            return redirect("liste_paiements")
        try:
            eleve = get_object_or_404(Eleve, pk=request.POST.get("eleve"), etablissement=etab)
            tf = get_object_or_404(TypeFrais, pk=request.POST.get("type_frais"), etablissement=etab)

            mode = request.POST.get('mode_calcul', 'fixe')
            if mode not in dict(ReductionFrais.MODES_CALCUL):
                mode = 'fixe'
            categorie = request.POST.get('categorie', 'autre')
            if categorie not in dict(ReductionFrais.CATEGORIES):
                categorie = 'autre'

            pct = None
            montant = Decimal('0')
            if mode == 'pourcentage':
                pct = Decimal(request.POST.get('valeur_pourcentage', '').replace(',', '.').strip() or 'x')
                if pct <= 0 or pct > 100:
                    raise ValueError("Le pourcentage doit être compris entre 0 et 100.")
            else:
                montant = Decimal(request.POST.get('montant', '').replace(' ', '').replace(',', '.') or 'x')
                if montant <= 0:
                    raise ValueError("Le montant doit être strictement positif.")
                if tf.montant_defaut and montant > tf.montant_defaut:
                    raise ValueError(
                        f"La réduction ({int(montant):,} F) dépasse le tarif du frais "
                        f"({int(tf.montant_defaut):,} F).".replace(',', ' ')
                    )

            with transaction.atomic():
                red = ReductionFrais.objects.select_for_update().filter(eleve=eleve, annee=annee, type_frais=tf).first()
                # Si on modifie une réduction et qu'on change de frais, supprimer l'ancienne
                if instance and (instance.type_frais_id != tf.pk or instance.eleve_id != eleve.pk):
                    ancien_tf, ancien_eleve = instance.type_frais, instance.eleve
                    instance.delete()
                    recalculer_echeances_eleve(ancien_eleve, annee, ancien_tf)
                if red is None:
                    red = ReductionFrais(etablissement=etab, eleve=eleve, annee=annee, type_frais=tf)
                red.categorie = categorie
                red.mode_calcul = mode
                red.valeur_pourcentage = pct
                red.montant = montant
                red.organisme_tiers = request.POST.get('organisme_tiers', '').strip()[:150]
                red.motif = request.POST.get('motif', '').strip()[:200]
                red.accordee_par = request.user
                red.save()

                nb = recalculer_echeances_eleve(eleve, annee, tf)
            _log(request, etab, eleve.matricule,
                 f"Bourse/Réduction {red.get_categorie_display()} {red.libelle_valeur} "
                 f"({int(red.montant)} FCFA) sur {tf.nom} — {eleve.nom_complet}")
            msg = f"{red.get_categorie_display()} enregistrée : {red.libelle_valeur} soit {int(red.montant):,} FCFA déduits pour {eleve.nom_complet}.".replace(',', ' ')
            if nb:
                msg += f" {nb} échéance(s) non payée(s) recalculée(s)."
            messages.success(request, msg)
            return redirect("situation_eleve", pk=eleve.pk)
        except (InvalidOperation, ValueError) as e:
            messages.error(request, f"Erreur : {e}" if str(e) and 'decimal' not in str(e).lower() else "Erreur : valeur numérique invalide.")

    eleves = get_eleves_actifs(etab, user=request.user).order_by("nom", "prenom")
    fratrie = list(detecter_fratrie(eleve_pre, annee)) if eleve_pre else []
    reductions_existantes = ReductionFrais.objects.filter(eleve=eleve_pre, annee=annee) \
        .select_related('type_frais') if eleve_pre else []

    return render(request, "finances/ajouter_reduction.html", {
        "eleves": eleves, "types_frais": types_frais, "eleve_pre": eleve_pre,
        "instance": instance, "categories": ReductionFrais.CATEGORIES,
        "fratrie": fratrie, "rang_fratrie": len(fratrie) + 1,
        "reductions_existantes": reductions_existantes, "annee": annee,
    })


@login_required
@permission_required("paiements")
@require_etab
def supprimer_reduction(request, pk):
    etab = request.etablissement
    red = get_object_or_404(ReductionFrais, pk=pk, etablissement=etab)
    eleve, annee, tf = red.eleve, red.annee, red.type_frais
    if request.method == "POST":
        detail = f"Suppression {red.get_categorie_display()} {red.libelle_valeur} sur {tf.nom} — {eleve.nom_complet}"
        with transaction.atomic():
            red.delete()
            nb = recalculer_echeances_eleve(eleve, annee, tf)
        _log(request, etab, eleve.matricule, detail)
        messages.success(request, f"Réduction supprimée. {nb} échéance(s) recalculée(s) au tarif standard.")
    return redirect("situation_eleve", pk=eleve.pk)


@login_required
@permission_required("paiements")
@require_etab
def personnaliser_echeancier(request, eleve_pk, type_frais_pk):
    """Rééchelonnement individuel : dates et montants des tranches non payées."""
    etab = request.etablissement
    annee = _annee_active(etab)
    eleve = get_object_or_404(Eleve, pk=eleve_pk, etablissement=etab)
    tf = get_object_or_404(TypeFrais, pk=type_frais_pk, etablissement=etab)
    if not annee:
        messages.error(request, "Aucune année scolaire active.")
        return redirect("situation_eleve", pk=eleve.pk)

    echeances, paye, reste, net = resume_echeancier(eleve, annee, tf)
    payees = [e for e in echeances if e.statut == 'payee']
    ouvertes = [e for e in echeances if e.statut != 'payee']

    if request.method == "POST":
        libelles = request.POST.getlist('libelle')
        montants = request.POST.getlist('montant')
        dates = request.POST.getlist('date_limite')
        try:
            lignes = []
            for i, (lib, m, d) in enumerate(zip(libelles, montants, dates), 1):
                m = (m or '').replace(' ', '').strip()
                if not m and not lib.strip():
                    continue
                try:
                    montant = int(Decimal(m.replace(',', '.') or '0'))
                except InvalidOperation:
                    raise ValueError(f"Montant invalide pour la ligne {i}.")
                lignes.append({'libelle': lib.strip(), 'montant': montant, 'date_limite': parse_date(d)})
            motif = request.POST.get('motif', '').strip()
            crees = appliquer_echeancier_personnalise(etab, eleve, annee, tf, lignes)
            _log(request, etab, eleve.matricule,
                 f"Échéancier personnalisé {tf.nom} — {eleve.nom_complet} : {len(crees)} tranche(s), "
                 f"reste {int(reste)} FCFA. Motif : {motif or '—'}")
            messages.success(request, f"Échéancier personnalisé enregistré : {len(crees)} tranche(s) pour {eleve.nom_complet}.")
            return redirect("situation_tranches_eleve", eleve_pk=eleve.pk)
        except ValueError as e:
            messages.error(request, str(e))

    lignes_init = [
        {'libelle': e.libelle, 'montant': int(e.montant),
         'date_limite': e.date_limite.isoformat() if e.date_limite else ''}
        for e in ouvertes if e.statut != 'dispensee' or int(reste) == 0
    ] or [{'libelle': f"Tranche {len(payees) + 1}", 'montant': int(reste), 'date_limite': ''}]

    return render(request, "finances/personnaliser_echeancier.html", {
        'eleve': eleve, 'type_frais': tf, 'annee': annee,
        'payees': payees, 'lignes': lignes_init,
        'net': int(net), 'paye': int(paye), 'reste': int(reste),
        'reduction': ReductionFrais.objects.filter(eleve=eleve, annee=annee, type_frais=tf).first(),
    })

