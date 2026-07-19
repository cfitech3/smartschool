"""
Gestion des paiements par tranches (échéancier).
"""
import datetime
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db import transaction
from django.utils import timezone
from django.db.models import Sum, Count, Q
from accounts.permissions import permission_required
from .models import TypeFrais, Echeance, Paiement
from eleves.models import Eleve, Inscription
from etablissements.models import AnneeScolaire
from core.cycle_filter import get_eleves_actifs


@login_required
@permission_required('finances')
def generer_echeances(request, type_frais_pk):
    """
    Génère les échéances pour tous les élèves actifs d'un type de frais 'par tranches'.
    """
    etab = request.etablissement
    type_frais = get_object_or_404(TypeFrais, pk=type_frais_pk, etablissement=etab)
    annee = AnneeScolaire.objects.filter(etablissement=etab, is_active=True).first()

    if type_frais.periodicite != 'tranches':
        messages.error(request, "Ce type de frais n'est pas configuré en paiement par tranches.")
        return redirect('liste_types_frais')

    if request.method == 'POST':
        dates_str = [request.POST.get(f'date_{i}', '') for i in range(1, type_frais.nombre_tranches + 1)]
        montants_str = [request.POST.get(f'montant_{i}', '0') for i in range(1, type_frais.nombre_tranches + 1)]

        # Validation
        errors = []
        montants = []
        dates = []
        for i, (m, d) in enumerate(zip(montants_str, dates_str), 1):
            try:
                montants.append(int(m))
            except ValueError:
                errors.append(f"Montant invalide pour la tranche {i}.")
            if d:
                try:
                    dates.append(datetime.date.fromisoformat(d))
                except ValueError:
                    errors.append(f"Date invalide pour la tranche {i}.")
            else:
                dates.append(None)

        if sum(montants) != int(type_frais.montant_defaut):
            errors.append(f"La somme des tranches ({sum(montants):,} FCFA) doit égaler le montant total ({int(type_frais.montant_defaut):,} FCFA).")

        if errors:
            for e in errors:
                messages.error(request, e)
        else:
            eleves = get_eleves_actifs(etab)
            nb_crees = 0
            with transaction.atomic():
                for eleve in eleves:
                    for i, (montant, date_limite) in enumerate(zip(montants, dates), 1):
                        _, created = Echeance.objects.get_or_create(
                            etablissement=etab, eleve=eleve,
                            annee=annee, type_frais=type_frais, numero=i,
                            defaults={
                                'libelle': f'Tranche {i}',
                                'montant': montant,
                                'date_limite': date_limite,
                                'statut': 'a_payer',
                            }
                        )
                        if created:
                            nb_crees += 1

            messages.success(request, f"✅ {nb_crees} échéance(s) générée(s) pour {eleves.count()} élève(s).")
            return redirect('tableau_tranches', type_frais_pk=type_frais.pk)

    # Prépopuler les montants équitables
    nb = type_frais.nombre_tranches or 1
    montant_total = int(type_frais.montant_defaut)
    montant_tranche = montant_total // nb
    reste = montant_total - (montant_tranche * nb)

    tranches_init = []
    for i in range(1, nb + 1):
        m = montant_tranche + (reste if i == nb else 0)
        tranches_init.append({'numero': i, 'libelle': f'Tranche {i}', 'montant': m})

    return render(request, 'finances/generer_echeances.html', {
        'type_frais': type_frais,
        'tranches': tranches_init,
        'annee': annee,
        'nb_eleves': get_eleves_actifs(etab).count(),
    })


@login_required
@permission_required('finances')
def tableau_tranches(request, type_frais_pk):
    """Tableau de bord des tranches : état des paiements par élève et par tranche."""
    etab = request.etablissement
    type_frais = get_object_or_404(TypeFrais, pk=type_frais_pk, etablissement=etab)
    annee = AnneeScolaire.objects.filter(etablissement=etab, is_active=True).first()
    today = timezone.now().date()

    # Mettre à jour les statuts "en retard"
    Echeance.objects.filter(
        etablissement=etab, type_frais=type_frais,
        statut='a_payer', date_limite__lt=today
    ).update(statut='retard')

    echeances = Echeance.objects.filter(
        etablissement=etab, type_frais=type_frais, annee=annee
    ).select_related('eleve', 'paiement').order_by('eleve__nom', 'eleve__prenom', 'numero')

    # Grouper par élève
    eleves_dict = {}
    for e in echeances:
        pk = e.eleve.pk
        if pk not in eleves_dict:
            eleves_dict[pk] = {'eleve': e.eleve, 'tranches': [], 'total_paye': 0, 'nb_retard': 0}
        eleves_dict[pk]['tranches'].append(e)
        if e.statut == 'payee':
            eleves_dict[pk]['total_paye'] += int(e.montant)
        if e.statut == 'retard':
            eleves_dict[pk]['nb_retard'] += 1

    # Stats globales
    nb_tranches = type_frais.nombre_tranches or 1
    total_echeances = echeances.count()
    nb_payees = echeances.filter(statut='payee').count()
    nb_retard = echeances.filter(statut='retard').count()
    nb_a_payer = echeances.filter(statut='a_payer').count()

    # Tranche active (la plus proche non payée)
    prochaine_tranche = Echeance.objects.filter(
        etablissement=etab, type_frais=type_frais, annee=annee,
        statut__in=['a_payer', 'retard']
    ).order_by('date_limite', 'numero').first()

    return render(request, 'finances/tableau_tranches.html', {
        'type_frais': type_frais,
        'annee': annee,
        'eleves_data': list(eleves_dict.values()),
        'nb_tranches': nb_tranches,
        'stats': {
            'total': total_echeances,
            'payees': nb_payees,
            'retard': nb_retard,
            'a_payer': nb_a_payer,
            'taux': round(nb_payees / total_echeances * 100) if total_echeances else 0,
        },
        'prochaine_tranche': prochaine_tranche,
        'today': today,
    })


@login_required
@permission_required('finances')
def payer_tranche(request, echeance_pk):
    """Encaisse le paiement d'une tranche spécifique."""
    etab = request.etablissement
    echeance = get_object_or_404(Echeance, pk=echeance_pk, etablissement=etab)
    annee = AnneeScolaire.objects.filter(etablissement=etab, is_active=True).first()

    if echeance.statut == 'payee':
        messages.warning(request, "Cette tranche est déjà payée.")
        return redirect('tableau_tranches', type_frais_pk=echeance.type_frais.pk)

    if request.method == 'POST':
        mode = request.POST.get('mode_paiement', 'especes')
        notes = request.POST.get('notes', '')
        montant = int(request.POST.get('montant', echeance.montant))

        with transaction.atomic():
            pai = Paiement.objects.create(
                etablissement=etab,
                eleve=echeance.eleve,
                annee=annee,
                type_frais=echeance.type_frais,
                montant=montant,
                mode_paiement=mode,
                statut='valide',
                periode_payee=echeance.libelle,
                encaisse_par=request.user,
                notes=notes,
            )
            echeance.marquer_payee(pai)

        messages.success(request, f"✅ {echeance.libelle} de {echeance.eleve.nom_complet} encaissée — {montant:,} FCFA.")
        return redirect('tableau_tranches', type_frais_pk=echeance.type_frais.pk)

    return render(request, 'finances/payer_tranche.html', {
        'echeance': echeance,
        'modes': Paiement.MODES,
    })


@login_required
@permission_required('finances')
def situation_tranches_eleve(request, eleve_pk):
    """Vue complète des tranches d'un élève : toutes les années, tous les types."""
    etab = request.etablissement
    eleve = get_object_or_404(Eleve, pk=eleve_pk, etablissement=etab)
    annee = AnneeScolaire.objects.filter(etablissement=etab, is_active=True).first()
    today = timezone.now().date()

    # Mettre à jour les retards
    Echeance.objects.filter(
        eleve=eleve, statut='a_payer', date_limite__lt=today
    ).update(statut='retard')

    echeances = Echeance.objects.filter(
        eleve=eleve, annee=annee
    ).select_related('type_frais', 'paiement').order_by('type_frais__nom', 'numero')

    # Grouper par type de frais
    par_type = {}
    for e in echeances:
        tf = e.type_frais.nom
        if tf not in par_type:
            par_type[tf] = {'type_frais': e.type_frais, 'echeances': [], 'total': 0, 'paye': 0}
        par_type[tf]['echeances'].append(e)
        par_type[tf]['total'] += int(e.montant)
        if e.statut == 'payee':
            par_type[tf]['paye'] += int(e.montant)

    total_du = sum(d['total'] for d in par_type.values())
    total_paye = sum(d['paye'] for d in par_type.values())

    return render(request, 'finances/situation_tranches_eleve.html', {
        'eleve': eleve,
        'par_type': par_type,
        'total_du': total_du,
        'total_paye': total_paye,
        'reste': total_du - total_paye,
        'annee': annee,
        'today': today,
    })
