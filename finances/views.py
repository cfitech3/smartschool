
from django.shortcuts import render, redirect, get_object_or_404
from core.cycle_filter import get_cycles_actifs_ids, get_classes_actives, get_eleves_actifs, get_inscriptions_actives
from accounts.permissions import permission_required, role_required, require_etab as req
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db import transaction
from django.db.models import Sum, Q
from django.utils import timezone
from django.http import JsonResponse, HttpResponse
from django.core.paginator import Paginator
from .models import Paiement, TypeFrais
from eleves.models import Eleve
from etablissements.models import AnneeScolaire, ModeleDocument
from decimal import Decimal, InvalidOperation
import datetime
import logging

logger = logging.getLogger(__name__)


def _resynchroniser_echeances(etab, eleve, annee, type_frais, paiement_cree=None, periode_payee='', paiement_annule=None):
    """
    Recalcule de manière atomique l'état des échéances d'un élève pour un type de frais.
    Verrouille les échéances via select_for_update() afin de garantir la cohérence
    même en cas d'annulation d'un paiement partiel ou d'encaissements concurrents.
    """
    from .models import Echeance

    echeances = list(
        Echeance.objects.select_for_update()
        .filter(etablissement=etab, eleve=eleve, annee=annee, type_frais=type_frais)
        .exclude(statut='dispensee')
        .order_by('numero')
    )
    if not echeances:
        return

    if paiement_cree and periode_payee.strip():
        matched_ech = next(
            (
                e for e in echeances
                if e.statut in ('a_payer', 'retard')
                and e.libelle.strip().lower() == periode_payee.strip().lower()
            ),
            None,
        )
        if matched_ech and Decimal(str(paiement_cree.montant)) >= Decimal(str(matched_ech.montant)):
            matched_ech.marquer_payee(paiement_cree)
            return

    total_paye = (
        Paiement.objects.filter(
            etablissement=etab, eleve=eleve, annee=annee, type_frais=type_frais, statut='valide'
        ).aggregate(t=Sum('montant'))['t']
        or Decimal('0')
    )
    dernier_valide = paiement_cree or (
        Paiement.objects.filter(
            etablissement=etab, eleve=eleve, annee=annee, type_frais=type_frais, statut='valide'
        ).order_by('-date_paiement', '-pk').first()
    )

    today = timezone.now().date()
    cumul = Decimal('0')
    for ech in echeances:
        cumul += Decimal(str(ech.montant))
        if total_paye >= cumul:
            if ech.statut != 'payee' or (paiement_annule and ech.paiement_id == paiement_annule.pk):
                if dernier_valide:
                    ech.marquer_payee(dernier_valide)
        else:
            if ech.statut == 'payee' or (paiement_annule and ech.paiement_id == paiement_annule.pk):
                ech.statut = 'retard' if (ech.date_limite and ech.date_limite < today) else 'a_payer'
                ech.paiement = None
                ech.date_paiement = None
                ech.save(update_fields=['statut', 'paiement', 'date_paiement'])

@login_required
@permission_required("paiements")
@req
def api_periodes_frais(request, pk):
    etab = request.etablissement
    tf = get_object_or_404(TypeFrais, pk=pk, etablissement=etab)
    periodes = []
    if tf.periodicite == 'mensuel':
        periodes = ["Septembre", "Octobre", "Novembre", "Décembre", "Janvier", "Février", "Mars", "Avril", "Mai", "Juin"]
    elif tf.periodicite == 'tranches':
        nb = tf.nombre_tranches or 1
        periodes = [f"Tranche {i}" for i in range(1, nb + 1)]
    else:
        periodes = ["Frais Global"]
        
    return JsonResponse({"periodes": periodes, "montant_defaut": float(tf.montant_defaut)})

@login_required
@permission_required("paiements")
@req
def liste_paiements(request):
    etab=request.etablissement
    annee=AnneeScolaire.objects.filter(etablissement=etab,is_active=True).first()
    base_paiements=Paiement.objects.filter(etablissement=etab)
    today=timezone.now().date()
    stats={
        "total_jour":base_paiements.filter(date_paiement__date=today,statut="valide").aggregate(t=Sum("montant"))["t"] or 0,
        "total_mois":base_paiements.filter(date_paiement__month=today.month,date_paiement__year=today.year,statut="valide").aggregate(t=Sum("montant"))["t"] or 0,
        "nb_jour":base_paiements.filter(date_paiement__date=today).count(),
        "total_valide":base_paiements.filter(statut="valide").aggregate(t=Sum("montant"))["t"] or 0,
    }
    paiements=base_paiements.select_related("eleve","type_frais","encaisse_par")
    q=request.GET.get("q",""); statut=request.GET.get("statut",""); mode=request.GET.get("mode","")
    dd=request.GET.get("date_debut",""); df=request.GET.get("date_fin","")
    if q: paiements=paiements.filter(Q(eleve__nom__icontains=q)|Q(eleve__prenom__icontains=q)|Q(reference__icontains=q))
    if statut: paiements=paiements.filter(statut=statut)
    if mode: paiements=paiements.filter(mode_paiement=mode)
    if dd: paiements=paiements.filter(date_paiement__date__gte=dd)
    if df: paiements=paiements.filter(date_paiement__date__lte=df)
    paiements=paiements.order_by("-date_paiement")
    paginator=Paginator(paiements,30); page=request.GET.get("page",1); paiements=paginator.get_page(page)
    return render(request,"finances/liste_paiements.html",{
        "paiements":paiements,"stats":stats,"annee":annee,"q":q,"statut":statut,"mode":mode,
        "date_debut":dd,"date_fin":df,"modes":Paiement.MODES,"statuts":Paiement.STATUTS,
    })

@login_required
@permission_required("paiements")
@req
def enregistrer_paiement(request):
    etab=request.etablissement
    annee=AnneeScolaire.objects.filter(etablissement=etab,is_active=True).first()
    types_frais=TypeFrais.objects.filter(etablissement=etab).filter(Q(annee=annee) | Q(annee__isnull=True))
    eleve_id=request.GET.get("eleve")
    eleve_pre=get_object_or_404(Eleve,pk=eleve_id,etablissement=etab) if eleve_id else None
    if request.method=="POST":
        if not annee:
            messages.error(request, "Aucune année scolaire active. Veuillez activer une année scolaire avant d'enregistrer un paiement.")
            return redirect("liste_paiements")
        from django.core.cache import cache
        idem_token = (request.POST.get("idempotency_token") or "").strip()
        if idem_token and cache.get(f"pay_idem_{idem_token}"):
            messages.warning(request, "Ce paiement vient déjà d'être enregistré (double soumission ignorée).")
            return redirect("liste_paiements")

        eid=request.POST.get("eleve"); fid=request.POST.get("type_frais")
        montant=request.POST.get("montant","").replace(" ",""); mode=request.POST.get("mode_paiement","especes")
        try:
            val_montant = Decimal(montant.replace(",","."))
            if val_montant <= 0:
                raise ValueError("Le montant doit être strictement positif.")

            tf=get_object_or_404(TypeFrais,pk=fid,etablissement=etab)
            periode_payee=request.POST.get("periode_payee", "")
            with transaction.atomic():
                eleve=get_object_or_404(Eleve.objects.select_for_update(),pk=eid,etablissement=etab)
                # Contrôle anti-surpaiement sur les frais à enveloppe annuelle fixe (unique / tranches)
                if tf.periodicite in ("unique", "tranches") and Decimal(str(tf.montant_defaut or 0)) > 0:
                    from .services_bourses import net_a_payer
                    net_exige = net_a_payer(eleve, annee, tf)
                    deja_paye = (
                        Paiement.objects.filter(
                            etablissement=etab, eleve=eleve, annee=annee, type_frais=tf, statut="valide"
                        ).aggregate(t=Sum("montant"))["t"]
                        or Decimal("0")
                    )
                    reste_du = max(Decimal("0"), net_exige - deja_paye)
                    if reste_du == 0:
                        raise ValueError(
                            f"Aucun solde restant dû sur « {tf.nom} » pour {eleve.nom_complet} "
                            f"(frais déjà soldé ou boursier à 100 %)."
                        )
                    if val_montant > reste_du:
                        raise ValueError(
                            f"Surpaiement refusé : le montant saisi ({int(val_montant):,} FCFA) dépasse "
                            f"le reste net à payer ({int(reste_du):,} FCFA) sur « {tf.nom} ».".replace(",", " ")
                        )

                p=Paiement.objects.create(etablissement=etab,eleve=eleve,annee=annee,type_frais=tf,
                    montant=val_montant,mode_paiement=mode,statut="valide", periode_payee=periode_payee,
                    encaisse_par=request.user,notes=request.POST.get("notes",""))
                _resynchroniser_echeances(
                    etab, eleve, annee, tf,
                    paiement_cree=p, periode_payee=periode_payee,
                )
            if idem_token:
                cache.set(f"pay_idem_{idem_token}", p.pk, 900)
            messages.success(request,f"Paiement {p.montant:,.0f} FCFA enregistre. Ref: {p.reference}")
            if request.POST.get("imprimer_recu"): return redirect("recu_paiement",pk=p.pk)
            return redirect("liste_paiements")
        except (ValueError, InvalidOperation) as e:
            messages.error(request, f"{e}")
        except Exception:
            logger.exception("Erreur lors de l'enregistrement du paiement (etab=%s)", etab.pk)
            messages.error(request, "Impossible d'enregistrer le paiement. Veuillez réessayer ou contacter l'administrateur.")
    # Enrichir les élèves avec leur classe actuelle
    from eleves.models import Inscription
    from core.cycle_filter import get_classes_actives
    eleves_qs = get_eleves_actifs(etab, user=request.user).order_by("nom","prenom")
    # Ajouter classe_pk et classe_nom pour le filtre JS
    inscriptions_map = {
        i.eleve_id: i.classe
        for i in Inscription.objects.filter(
            eleve__in=eleves_qs, annee=annee, is_active=True
        ).select_related("classe")
    }
    eleves_avec_classe = []
    for e in eleves_qs:
        cl = inscriptions_map.get(e.pk)
        e.classe_pk  = cl.pk  if cl else None
        e.classe_nom = cl.nom if cl else None
        eleves_avec_classe.append(e)
    import uuid
    classes = get_classes_actives(etab, annee, user=request.user) if annee else []
    return render(request,"finances/enregistrer_paiement.html",{
        "eleves":eleves_avec_classe, "classes":classes,
        "types_frais":types_frais, "modes":Paiement.MODES,
        "eleve_pre":eleve_pre, "annee":annee,
        "idempotency_token": uuid.uuid4().hex,
    })

@login_required
@req
def recu_paiement(request,pk):
    etab=request.etablissement
    paiement=get_object_or_404(Paiement,pk=pk,etablissement=etab)

    # Sécurité RBAC + IDOR Famille
    if request.user.role in ['parent', 'eleve']:
        from core.views_espace_famille import get_eleves_accessibles
        eleves_ok = get_eleves_accessibles(request.user).values_list('pk', flat=True)
        if paiement.eleve.pk not in eleves_ok:
            messages.error(request, "Accès refusé. Ce reçu ne vous appartient pas.")
            return redirect('dashboard')
    elif request.user.role not in ['admin', 'super_admin', 'comptable']:
        messages.error(request, "Accès refusé. Vous n'avez pas l'autorisation de consulter les reçus financiers.")
        return redirect('dashboard')

    from core.verification_qr import construire_contexte_qr
    qr_ctx = {}
    if paiement.statut == 'valide':
        qr_ctx = construire_contexte_qr(
            request, 'recu', paiement.eleve, annee=paiement.annee,
            extra={'pay_pk': paiement.pk, 'ref': paiement.reference, 'mnt': int(paiement.montant)},
        )
    modele=ModeleDocument.objects.filter(etablissement=etab,type_document="recu",is_actif=True).first()
    ctx = {"paiement":paiement,"etablissement":etab,"modele":modele}
    ctx.update(qr_ctx)
    return render(request,"finances/recu.html",ctx)

@login_required
@permission_required("finances")
@req
def rapport_financier(request):
    import calendar
    import json
    from django.db.models import Count
    from django.db.models.functions import TruncMonth
    from finances.models import Echeance

    etab=request.etablissement
    annee=AnneeScolaire.objects.filter(etablissement=etab,is_active=True).first()
    today=timezone.now().date()

    if not annee:
        return render(request,"finances/rapport.html",{"mois_data":"[]","par_type":[],"eleves_en_retard":[],"total_annee":0,"annee":None,"today":today})

    base_paiements = Paiement.objects.filter(etablissement=etab, statut="valide")

    mois_cibles = []
    for i in range(11,-1,-1):
        target_month = (today.month - i - 1) % 12 + 1
        target_year = today.year + (today.month - i - 1) // 12
        mois_cibles.append((target_year, target_month))

    debut_12m = timezone.make_aware(datetime.datetime(mois_cibles[0][0], mois_cibles[0][1], 1))
    totaux_map = {
        (r["m"].year, r["m"].month): float(r["t"] or 0)
        for r in base_paiements.filter(date_paiement__gte=debut_12m)
        .annotate(m=TruncMonth("date_paiement")).values("m").annotate(t=Sum("montant"))
        if r["m"]
    }
    mois_data = [
        {"mois": f"{calendar.month_name[m][:3].capitalize()} {y}", "total": totaux_map.get((y, m), 0.0)}
        for (y, m) in mois_cibles
    ]

    par_type = base_paiements.filter(annee=annee).values("type_frais__nom").annotate(total=Sum("montant"), nb=Count("id")).order_by("-total")

    eleves_en_retard_ids = Echeance.objects.filter(
        etablissement=etab, annee=annee, statut__in=['a_payer', 'retard'], date_limite__lt=today
    ).values_list('eleve_id', flat=True).distinct()

    en_retard = Eleve.objects.filter(pk__in=eleves_en_retard_ids)[:10]
    total = base_paiements.filter(annee=annee).aggregate(t=Sum("montant"))["t"] or 0

    return render(request,"finances/rapport.html",{"mois_data":json.dumps(mois_data),"par_type":par_type,"eleves_en_retard":en_retard,"total_annee":total,"annee":annee,"today":today})

@login_required
@req
def situation_eleve(request,pk):
    etab=request.etablissement
    eleve=get_object_or_404(Eleve,pk=pk,etablissement=etab)
    if request.user.role in ['parent', 'eleve']:
        from core.views_espace_famille import get_eleves_accessibles
        if not get_eleves_accessibles(request.user).filter(pk=eleve.pk).exists():
            messages.error(request, "Accès refusé. Cette fiche financière ne vous appartient pas.")
            return redirect('dashboard')
    elif request.user.role not in ['admin', 'super_admin', 'comptable']:
        messages.error(request, "Accès refusé. Vous n'avez pas l'autorisation de consulter la situation financière d'un élève.")
        return redirect('dashboard')
    annee=AnneeScolaire.objects.filter(etablissement=etab,is_active=True).first()
    paiements=eleve.paiements.filter(annee=annee).select_related("type_frais").order_by("-date_paiement") if annee else Paiement.objects.none()
    total_paye = paiements.filter(statut="valide").aggregate(t=Sum("montant"))["t"] or Decimal('0')
    
    # P3.1 : Prise en compte des réductions / bourses (tarif standard inchangé)
    from .models import TypeFrais, ReductionFrais, Echeance
    reductions = ReductionFrais.objects.filter(eleve=eleve, annee=annee).select_related("type_frais", "accordee_par")
    reduc_map = {r.type_frais_id: r for r in reductions}
    total_reductions = reductions.aggregate(t=Sum("montant"))["t"] or Decimal('0')

    # Détail par type de frais : tarif standard, réduction, net, payé, reste
    types_frais_annee = TypeFrais.objects.filter(etablissement=etab).filter(Q(annee=annee) | Q(annee__isnull=True))
    paye_map = {
        r['type_frais_id']: r['t'] or Decimal('0')
        for r in (paiements.filter(statut="valide").values('type_frais_id').annotate(t=Sum('montant')) if annee else [])
    }
    tf_echeancier = set(Echeance.objects.filter(eleve=eleve, annee=annee).values_list('type_frais_id', flat=True)) if annee else set()
    detail_frais = []
    total_obligatoire = Decimal('0'); total_exige = Decimal('0'); total_paye_obligatoire = Decimal('0')
    for tf in types_frais_annee:
        red = reduc_map.get(tf.pk)
        paye_tf = paye_map.get(tf.pk, Decimal('0'))
        if not tf.is_obligatoire and not red and not paye_tf:
            continue
        base = Decimal(str(tf.montant_defaut or 0))
        reduc = Decimal(str(red.montant)) if red else Decimal('0')
        net = max(Decimal('0'), base - reduc)
        if tf.is_obligatoire:
            total_obligatoire += base
            total_exige += net
            total_paye_obligatoire += paye_tf
        detail_frais.append({
            'type_frais': tf, 'base': base, 'reduction': red, 'net': net,
            'paye': paye_tf, 'reste': net - paye_tf, 'a_echeancier': tf.pk in tf_echeancier,
        })
    reste_a_payer = max(Decimal('0'), total_exige - total_paye_obligatoire)

    return render(request, "finances/situation_eleve.html", {
        "eleve": eleve, "paiements": paiements, "total_paye": total_paye, "annee": annee,
        "reductions": reductions, "total_reductions": total_reductions,
        "total_obligatoire": total_obligatoire, "detail_frais": detail_frais,
        "total_exige": total_exige, "reste_a_payer": reste_a_payer,
        "peut_gerer": request.user.role in ['admin', 'super_admin', 'comptable'],
    })

# ajouter_reduction : déplacée dans finances/views_bourses.py (bourses, % , fratrie, recalcul des échéances)

@login_required
@permission_required("paiements")
@req
def annuler_paiement(request, pk):
    etab = request.etablissement
    paiement = get_object_or_404(Paiement, pk=pk, etablissement=etab)
    
    if request.method == "POST":
        if paiement.statut == 'annule':
            messages.error(request, "Ce paiement est déjà annulé.")
        else:
            motif = request.POST.get("motif_annulation", "").strip()
            if not motif:
                messages.error(request, "Le motif d'annulation est obligatoire.")
            else:
                with transaction.atomic():
                    paiement.statut = 'annule'
                    paiement.date_annulation = timezone.now()
                    paiement.motif_annulation = motif
                    paiement.annule_par = request.user
                    paiement.save()

                    _resynchroniser_echeances(
                        etab, paiement.eleve, paiement.annee, paiement.type_frais,
                        paiement_annule=paiement,
                    )
                    from etablissements.models import JournalAction
                    JournalAction.log(
                        request, 'autre', cible=paiement.reference,
                        etablissement=etab,
                        detail=f"Annulation paiement {paiement.montant} FCFA ({paiement.eleve.nom_complet}) — Motif: {motif}"
                    )
                        
                messages.success(request, f"Paiement {paiement.reference} annulé avec succès. Les échéances ont été remises en attente.")
                
    return redirect("liste_paiements")

@login_required
@permission_required("paiements")
@req
def get_montant_frais(request):
    etab=request.etablissement
    try:
        f=TypeFrais.objects.get(pk=request.GET.get("id"),etablissement=etab)
        return JsonResponse({"montant":float(f.montant_defaut),"nom":f.nom})
    except (TypeFrais.DoesNotExist, ValueError, TypeError):
        return JsonResponse({"error":"Non trouve"},status=404)
