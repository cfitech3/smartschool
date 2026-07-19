
from django.shortcuts import render, redirect, get_object_or_404
from core.cycle_filter import get_cycles_actifs_ids, get_eleves_actifs
from accounts.permissions import permission_required, role_required
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import Sum, Q
from django.utils import timezone
from django.http import JsonResponse, HttpResponse
from django.core.paginator import Paginator
from .models import Paiement, TypeFrais
from eleves.models import Eleve
from etablissements.models import AnneeScolaire, ModeleDocument
from decimal import Decimal
import datetime
from core.cycle_filter import get_cycles_actifs_ids, get_classes_actives, get_eleves_actifs, get_inscriptions_actives

def req(fn):
    def w(request,*a,**k):
        if not request.etablissement: return redirect("dashboard")
        return fn(request,*a,**k)
    w.__name__=fn.__name__; return w

@login_required
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
    paiements=Paiement.objects.filter(etablissement=etab).select_related("eleve","type_frais","encaisse_par")
    q=request.GET.get("q",""); statut=request.GET.get("statut",""); mode=request.GET.get("mode","")
    dd=request.GET.get("date_debut",""); df=request.GET.get("date_fin","")
    if q: paiements=paiements.filter(Q(eleve__nom__icontains=q)|Q(eleve__prenom__icontains=q)|Q(reference__icontains=q))
    if statut: paiements=paiements.filter(statut=statut)
    if mode: paiements=paiements.filter(mode_paiement=mode)
    if dd: paiements=paiements.filter(date_paiement__date__gte=dd)
    if df: paiements=paiements.filter(date_paiement__date__lte=df)
    paiements=paiements.order_by("-date_paiement")
    today=timezone.now().date()
    stats={
        "total_jour":paiements.filter(date_paiement__date=today,statut="valide").aggregate(t=Sum("montant"))["t"] or 0,
        "total_mois":paiements.filter(date_paiement__month=today.month,date_paiement__year=today.year,statut="valide").aggregate(t=Sum("montant"))["t"] or 0,
        "nb_jour":paiements.filter(date_paiement__date=today).count(),
        "total_valide":paiements.filter(statut="valide").aggregate(t=Sum("montant"))["t"] or 0,
    }
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
        eid=request.POST.get("eleve"); fid=request.POST.get("type_frais")
        montant=request.POST.get("montant","").replace(" ",""); mode=request.POST.get("mode_paiement","especes")
        try:
            val_montant = Decimal(montant.replace(",","."))
            if val_montant <= 0:
                raise ValueError("Le montant doit être strictement positif.")
            
            eleve=get_object_or_404(Eleve,pk=eid,etablissement=etab)
            tf=get_object_or_404(TypeFrais,pk=fid,etablissement=etab)
            periode_payee=request.POST.get("periode_payee", "")
            p=Paiement.objects.create(etablissement=etab,eleve=eleve,annee=annee,type_frais=tf,
                montant=val_montant,mode_paiement=mode,statut="valide", periode_payee=periode_payee,
                encaisse_par=request.user,notes=request.POST.get("notes",""))
            messages.success(request,f"Paiement {p.montant:,.0f} FCFA enregistre. Ref: {p.reference}")
            if request.POST.get("imprimer_recu"): return redirect("recu_paiement",pk=p.pk)
            return redirect("liste_paiements")
        except Exception as e: messages.error(request,f"Erreur: {e}")
    eleves=get_eleves_actifs(etab).order_by("nom","prenom")
    return render(request,"finances/enregistrer_paiement.html",{"eleves":eleves,"types_frais":types_frais,"modes":Paiement.MODES,"eleve_pre":eleve_pre,"annee":annee})

@login_required
@req
def recu_paiement(request,pk):
    etab=request.etablissement
    paiement=get_object_or_404(Paiement,pk=pk,etablissement=etab)
    
    # Sécurité IDOR Famille
    if request.user.role in ['parent', 'eleve']:
        from core.views_espace_famille import get_eleves_accessibles
        eleves_ok = get_eleves_accessibles(request.user).values_list('pk', flat=True)
        if paiement.eleve.pk not in eleves_ok:
            messages.error(request, "Accès refusé. Ce reçu ne vous appartient pas.")
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

    eleves_actifs_ids = list(get_eleves_actifs(etab, annee).values_list('pk', flat=True))
    base_paiements = Paiement.objects.filter(etablissement=etab, statut="valide", eleve_id__in=eleves_actifs_ids)
    
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
    annee=AnneeScolaire.objects.filter(etablissement=etab,is_active=True).first()
    paiements=eleve.paiements.filter(annee=annee).select_related("type_frais").order_by("-date_paiement") if annee else []
    total_paye = paiements.filter(statut="valide").aggregate(t=Sum("montant"))["t"] or Decimal('0')
    
    # P3.1 : Prise en compte des réductions
    from .models import TypeFrais, ReductionFrais
    reductions = ReductionFrais.objects.filter(eleve=eleve, annee=annee).select_related("type_frais")
    total_reductions = reductions.aggregate(t=Sum("montant"))["t"] or Decimal('0')
    
    # Calcul du reste à payer basé sur les frais obligatoires
    types_obligatoires = TypeFrais.objects.filter(etablissement=etab, is_obligatoire=True).filter(Q(annee=annee) | Q(annee__isnull=True))
    total_obligatoire = types_obligatoires.aggregate(t=Sum("montant_defaut"))["t"] or Decimal('0')
    
    total_exige = total_obligatoire - total_reductions
    if total_exige < 0: total_exige = Decimal('0')
    reste_a_payer = total_exige - total_paye

    return render(request, "finances/situation_eleve.html", {
        "eleve": eleve, "paiements": paiements, "total_paye": total_paye, "annee": annee,
        "reductions": reductions, "total_reductions": total_reductions,
        "total_exige": total_exige, "reste_a_payer": reste_a_payer
    })

@login_required
@permission_required("paiements")
@req
def ajouter_reduction(request):
    etab=request.etablissement
    annee=AnneeScolaire.objects.filter(etablissement=etab,is_active=True).first()
    types_frais=TypeFrais.objects.filter(etablissement=etab).filter(Q(annee=annee)|Q(annee__isnull=True))
    eleve_id=request.GET.get("eleve")
    eleve_pre=get_object_or_404(Eleve,pk=eleve_id,etablissement=etab) if eleve_id else None

    if request.method=="POST":
        eid=request.POST.get("eleve"); fid=request.POST.get("type_frais")
        montant=request.POST.get("montant","").replace(" ","")
        try:
            val_montant = Decimal(montant.replace(",","."))
            if val_montant <= 0: raise ValueError("Le montant doit être positif.")
            eleve=get_object_or_404(Eleve,pk=eid,etablissement=etab)
            tf=get_object_or_404(TypeFrais,pk=fid,etablissement=etab)
            
            from .models import ReductionFrais
            ReductionFrais.objects.update_or_create(
                etablissement=etab, eleve=eleve, annee=annee, type_frais=tf,
                defaults={'montant': val_montant, 'motif': request.POST.get('motif', '')}
            )
            messages.success(request, f"Réduction de {val_montant} FCFA enregistrée pour {eleve.nom_complet}.")
            return redirect("situation_eleve", pk=eleve.pk)
        except Exception as e: messages.error(request,f"Erreur: {e}")

    eleves=get_eleves_actifs(etab).order_by("nom")
    return render(request,"finances/ajouter_reduction.html",{"eleves":eleves,"types_frais":types_frais,"eleve_pre":eleve_pre})

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
                    
                    # Restaurer les échéances liées
                    echeances = paiement.echeances_liees.all()
                    for e in echeances:
                        e.statut = 'a_payer'
                        e.paiement = None
                        e.date_paiement = None
                        e.save()
                        
                messages.success(request, f"Paiement {paiement.reference} annulé avec succès. Les échéances ont été remises en attente.")
                
    return redirect("liste_paiements")

@login_required
@req
def get_montant_frais(request):
    etab=request.etablissement
    try:
        f=TypeFrais.objects.get(pk=request.GET.get("id"),etablissement=etab)
        return JsonResponse({"montant":float(f.montant_defaut),"nom":f.nom})
    except: return JsonResponse({"error":"Non trouve"},status=404)
