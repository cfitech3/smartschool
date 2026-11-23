
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
        eid=request.POST.get("eleve"); fid=request.POST.get("type_frais")
        montant=request.POST.get("montant","").replace(" ",""); mode=request.POST.get("mode_paiement","especes")
        try:
            val_montant = Decimal(montant.replace(",","."))
            if val_montant <= 0:
                raise ValueError("Le montant doit être strictement positif.")
            
            eleve=get_object_or_404(Eleve,pk=eid,etablissement=etab)
            tf=get_object_or_404(TypeFrais,pk=fid,etablissement=etab)
            periode_payee=request.POST.get("periode_payee", "")
            with transaction.atomic():
                p=Paiement.objects.create(etablissement=etab,eleve=eleve,annee=annee,type_frais=tf,
                    montant=val_montant,mode_paiement=mode,statut="valide", periode_payee=periode_payee,
                    encaisse_par=request.user,notes=request.POST.get("notes",""))
                _resynchroniser_echeances(
                    etab, eleve, annee, tf,
                    paiement_cree=p, periode_payee=periode_payee,
                )
            messages.success(request,f"Paiement {p.montant:,.0f} FCFA enregistre. Ref: {p.reference}")
            if request.POST.get("imprimer_recu"): return redirect("recu_paiement",pk=p.pk)
            return redirect("liste_paiements")
        except (ValueError, InvalidOperation) as e:
            messages.error(request, f"Montant invalide : {e}")
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
    classes = get_classes_actives(etab, annee, user=request.user) if annee else []
    return render(request,"finances/enregistrer_paiement.html",{
        "eleves":eleves_avec_classe, "classes":classes,
        "types_frais":types_frais, "modes":Paiement.MODES,
        "eleve_pre":eleve_pre, "annee":annee
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
            
    modele=ModeleDocument.objects.filter(etablissement=etab,type_document="recu",is_actif=True).first()
    return render(request,"finances/recu.html",{"paiement":paiement,"etablissement":etab,"modele":modele})

@login_required
@permission_required("finances")
@req
def rapport_financier(request):
    from django.db.models import Count
    from finances.models import Echeance
    
    etab=request.etablissement
    annee=AnneeScolaire.objects.filter(etablissement=etab,is_active=True).first()
    today=timezone.now().date()
    
    if not annee:
        return render(request,"finances/rapport.html",{"mois_data":[],"par_type":[],"eleves_en_retard":[],"total_annee":0,"annee":None,"today":today})

    # Ne pas filtrer par eleves_actifs_ids afin de conserver l'intégrité comptable des paiements encaissés
    base_paiements = Paiement.objects.filter(etablissement=etab, statut="valide")
    
    mois_data=[]
    for i in range(11,-1,-1):
        # Calcul du mois précis pour éviter les décalages de 30 jours
        target_month = (today.month - i - 1) % 12 + 1
        target_year = today.year + (today.month - i - 1) // 12
        
        t = base_paiements.filter(date_paiement__year=target_year, date_paiement__month=target_month).aggregate(t=Sum("montant"))["t"] or 0
        import calendar
        nom_mois = calendar.month_name[target_month][:3].capitalize()
        mois_data.append({"mois": f"{nom_mois} {target_year}", "total": float(t)})
        
    par_type = base_paiements.filter(annee=annee).values("type_frais__nom").annotate(total=Sum("montant"), nb=Count("id")).order_by("-total")
    
    # Calcul exact des retards (échéances dépassées)
    eleves_en_retard_ids = Echeance.objects.filter(
        etablissement=etab, annee=annee, statut__in=['a_payer', 'retard'], date_limite__lt=today
    ).values_list('eleve_id', flat=True).distinct()
    
    en_retard = Eleve.objects.filter(pk__in=eleves_en_retard_ids)[:10]
    total = base_paiements.filter(annee=annee).aggregate(t=Sum("montant"))["t"] or 0
    
    return render(request,"finances/rapport.html",{"mois_data":mois_data,"par_type":par_type,"eleves_en_retard":en_retard,"total_annee":total,"annee":annee,"today":today})

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
