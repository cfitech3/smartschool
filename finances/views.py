
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
    types_frais=TypeFrais.objects.filter(etablissement=etab)
    eleve_id=request.GET.get("eleve")
    eleve_pre=get_object_or_404(Eleve,pk=eleve_id,etablissement=etab) if eleve_id else None
    if request.method=="POST":
        eid=request.POST.get("eleve"); fid=request.POST.get("type_frais")
        montant=request.POST.get("montant","").replace(" ",""); mode=request.POST.get("mode_paiement","especes")
        try:
            eleve=get_object_or_404(Eleve,pk=eid,etablissement=etab)
            tf=get_object_or_404(TypeFrais,pk=fid,etablissement=etab)
            p=Paiement.objects.create(etablissement=etab,eleve=eleve,annee=annee,type_frais=tf,
                montant=Decimal(montant.replace(",",".")),mode_paiement=mode,statut="valide",
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
    modele=ModeleDocument.objects.filter(etablissement=etab,type_document="recu",is_actif=True).first()
    return render(request,"finances/recu.html",{"paiement":paiement,"etablissement":etab,"modele":modele})

@login_required
@permission_required("finances")
@req
def rapport_financier(request):
    etab=request.etablissement; annee=AnneeScolaire.objects.filter(etablissement=etab,is_active=True).first()
    today=timezone.now().date()
    mois_data=[]
    for i in range(11,-1,-1):
        d=today.replace(day=1)-datetime.timedelta(days=i*30)
        t=Paiement.objects.filter(etablissement=etab,statut="valide",eleve__inscriptions__classe__niveau__cycle__in=get_cycles_actifs_ids(etab),eleve__inscriptions__is_active=True,date_paiement__year=d.year,date_paiement__month=d.month).aggregate(t=Sum("montant"))["t"] or 0
        mois_data.append({"mois":d.strftime("%b %Y"),"total":float(t)})
    par_type=Paiement.objects.filter(etablissement=etab,statut="valide",eleve__inscriptions__classe__niveau__cycle__in=get_cycles_actifs_ids(etab),eleve__inscriptions__is_active=True,annee=annee).values("type_frais__nom").annotate(total=Sum("montant"),nb=__import__("django.db.models",fromlist=["Count"]).Count("id")).order_by("-total") if annee else []
    payes=Paiement.objects.filter(etablissement=etab,statut="valide",eleve__inscriptions__classe__niveau__cycle__in=get_cycles_actifs_ids(etab),eleve__inscriptions__is_active=True,date_paiement__month=today.month,date_paiement__year=today.year).values_list("eleve_id",flat=True)
    en_retard=get_eleves_actifs(etab).exclude(pk__in=payes)[:10]
    total=Paiement.objects.filter(etablissement=etab,statut="valide",eleve__inscriptions__classe__niveau__cycle__in=get_cycles_actifs_ids(etab),eleve__inscriptions__is_active=True,annee=annee).aggregate(t=Sum("montant"))["t"] or 0
    return render(request,"finances/rapport.html",{"mois_data":mois_data,"par_type":par_type,"eleves_en_retard":en_retard,"total_annee":total,"annee":annee,"today":today})

@login_required
@req
def situation_eleve(request,pk):
    etab=request.etablissement
    eleve=get_object_or_404(Eleve,pk=pk,etablissement=etab)
    annee=AnneeScolaire.objects.filter(etablissement=etab,is_active=True).first()
    paiements=eleve.paiements.filter(annee=annee).select_related("type_frais").order_by("-date_paiement") if annee else []
    total=paiements.filter(statut="valide").aggregate(t=Sum("montant"))["t"] or 0
    return render(request,"finances/situation_eleve.html",{"eleve":eleve,"paiements":paiements,"total_paye":total,"annee":annee})

@login_required
@req
def get_montant_frais(request):
    etab=request.etablissement
    try:
        f=TypeFrais.objects.get(pk=request.GET.get("id"),etablissement=etab)
        return JsonResponse({"montant":float(f.montant_defaut),"nom":f.nom})
    except: return JsonResponse({"error":"Non trouve"},status=404)
