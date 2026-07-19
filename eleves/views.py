from accounts.permissions import permission_required

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import Q, Count
from django.core.paginator import Paginator
from .models import Eleve, Tuteur, Inscription
from etablissements.models import Classe, AnneeScolaire, Niveau
from .forms import EleveForm, InscriptionForm, TuteurForm
from core.cycle_filter import get_cycles_actifs_ids, get_classes_actives, get_eleves_actifs, get_inscriptions_actives

def req(fn):
    def w(request,*a,**k):
        if not request.etablissement: return redirect("dashboard")
        return fn(request,*a,**k)
    w.__name__=fn.__name__; return w

@login_required
@permission_required('eleves')
@req
def liste_eleves(request):
    from core.cycle_filter import get_eleves_actifs, get_classes_actives
    etab=request.etablissement
    annee=AnneeScolaire.objects.filter(etablissement=etab,is_active=True).first()
    eleves=get_eleves_actifs(etab).select_related("tuteur").prefetch_related("inscriptions__classe__niveau").order_by("nom","prenom")
    q=request.GET.get("q",""); classe_id=request.GET.get("classe",""); sexe=request.GET.get("sexe","")
    if q: eleves=eleves.filter(Q(nom__icontains=q)|Q(prenom__icontains=q)|Q(matricule__icontains=q))
    if classe_id: eleves=eleves.filter(inscriptions__classe_id=classe_id,inscriptions__is_active=True)
    if sexe: eleves=eleves.filter(sexe=sexe)
    classes=get_classes_actives(etab, annee) if annee else []
    paginator=Paginator(eleves,25); page=request.GET.get("page",1); eleves_page=paginator.get_page(page)
    return render(request,"eleves/liste.html",{"eleves":eleves_page,"classes":classes,"annee":annee,"q":q,"classe_id":classe_id,"sexe":sexe,"total":paginator.count})

@login_required
@req
def detail_eleve(request,pk):
    etab=request.etablissement
    eleve=get_object_or_404(Eleve,pk=pk,etablissement=etab)
    inscriptions=eleve.inscriptions.select_related("classe__niveau","annee").order_by("-annee__libelle")
    paiements=eleve.paiements.select_related("type_frais").order_by("-date_paiement")[:10]
    return render(request,"eleves/detail.html",{"eleve":eleve,"inscriptions":inscriptions,"paiements":paiements,"inscription_active":eleve.get_inscription_active()})

@login_required
@permission_required('eleves')
@req
def ajouter_eleve(request):
    etab=request.etablissement
    annee=AnneeScolaire.objects.filter(etablissement=etab,is_active=True).first()
    ef=EleveForm(request.POST or None,request.FILES or None,etablissement=etab)
    tf=TuteurForm(request.POST or None,prefix="tuteur",etablissement=etab)
    inf=InscriptionForm(request.POST or None,prefix="insc",etablissement=etab,annee=annee)
    if request.method=="POST":
        ev=ef.is_valid(); iv=inf.is_valid()
        tuteur=None
        if request.POST.get("tuteur-nom","").strip() and tf.is_valid():
            tuteur=tf.save(commit=False); tuteur.etablissement=etab; tuteur.save()
        if ev and iv:
            eleve=ef.save(commit=False); eleve.etablissement=etab
            if tuteur: eleve.tuteur=tuteur
            eleve.save()
            insc=inf.save(commit=False); insc.eleve=eleve; insc.annee=annee; insc.save()
            messages.success(request,f"Eleve {eleve.nom_complet} inscrit ! Matricule: {eleve.matricule}")
            if request.POST.get("ajouter_autre"): return redirect("ajouter_eleve")
            return redirect("detail_eleve",pk=eleve.pk)
    return render(request,"eleves/ajouter.html",{"eleve_form":ef,"tuteur_form":tf,"inscription_form":inf,"annee":annee})

@login_required
@permission_required('eleves')
@req
def supprimer_eleve(request,pk):
    etab=request.etablissement
    eleve=get_object_or_404(Eleve,pk=pk,etablissement=etab)
    if request.method=="POST":
        nom=eleve.nom_complet; eleve.is_active=False; eleve.save()
        messages.success(request,f"Eleve {nom} archive.")
        return redirect("liste_eleves")
    return render(request,"eleves/confirmer_suppression.html",{"eleve":eleve})

@login_required
@req
def liste_classes(request):
    etab=request.etablissement
    annee=AnneeScolaire.objects.filter(etablissement=etab,is_active=True).first()
    classes=get_classes_actives(etab, annee).select_related("niveau","niveau__cycle").annotate(nb=Count("inscriptions",filter=Q(inscriptions__is_active=True))).order_by("niveau__cycle__ordre","niveau__ordre","nom") if annee else []
    return render(request,"eleves/classes.html",{"classes":classes,"annee":annee})

@login_required
@req
def detail_classe(request,pk):
    etab=request.etablissement
    annee=AnneeScolaire.objects.filter(etablissement=etab,is_active=True).first()
    classe=get_object_or_404(Classe,pk=pk,etablissement=etab)
    inscriptions=classe.inscriptions.filter(is_active=True).select_related("eleve__tuteur").order_by("eleve__nom")
    return render(request,"eleves/detail_classe.html",{"classe":classe,"inscriptions":inscriptions,"annee":annee})

@login_required
@permission_required('eleves')
@req
def ajouter_classe(request):
    etab=request.etablissement
    annee=AnneeScolaire.objects.filter(etablissement=etab,is_active=True).first()
    if request.method=="POST":
        nom=request.POST.get("nom","").strip()
        niv_id=request.POST.get("niveau",""); niv_libre=request.POST.get("niveau_libre","").strip()
        cap=request.POST.get("capacite_max",40); salle=request.POST.get("salle","")
        niveau=None
        if niv_libre:
            niveau,_=Niveau.objects.get_or_create(etablissement=etab,nom=niv_libre,defaults={"ordre":Niveau.objects.filter(etablissement=etab).count()+1})
        elif niv_id:
            niveau=get_object_or_404(Niveau,pk=niv_id,etablissement=etab)
        if nom and niveau and annee:
            if Classe.objects.filter(etablissement=etab,annee=annee,nom=nom).exists():
                messages.error(request,f"Classe {nom} existe deja.")
            else:
                from etablissements.models import SerieLycee
                serie_pk=request.POST.get('serie')
                serie=SerieLycee.objects.filter(pk=serie_pk).first() if serie_pk else None
                
                try:
                    capacite_entier = int(cap)
                except ValueError:
                    capacite_entier = 40
                
                c=Classe.objects.create(etablissement=etab,annee=annee,niveau=niveau,nom=nom,
                    capacite_max=capacite_entier,salle=salle,serie=serie)
                messages.success(request,f"Classe {c.nom} creee.")
                if request.POST.get('ajouter_autre'): return redirect('ajouter_classe')
                return redirect("liste_classes")
        else:
            messages.error(request,"Remplissez tous les champs obligatoires.")
    from etablissements.models import Cycle, SerieLycee
    niveaux=Niveau.objects.filter(etablissement=etab)
    cycles=Cycle.objects.filter(etablissement=etab).prefetch_related('niveaux').order_by('ordre')
    series=SerieLycee.objects.filter(cycle__etablissement=etab)
    return render(request,"eleves/ajouter_classe.html",{
        "niveaux":niveaux,"annee":annee,
        "cycles":cycles,"series":series,
    })

@login_required
@permission_required('eleves')
@req
def modifier_classe(request,pk):
    etab=request.etablissement
    classe=get_object_or_404(Classe,pk=pk,etablissement=etab)
    niveaux=Niveau.objects.filter(etablissement=etab).select_related('cycle')
    if request.method=="POST":
        if request.POST.get("action")=="supprimer":
            nom=classe.nom; classe.delete()
            messages.success(request,f"Classe {nom} supprimee."); return redirect("liste_classes")
        classe.nom=request.POST.get("nom",classe.nom)
        niv_id=request.POST.get("niveau"); 
        if niv_id: classe.niveau=get_object_or_404(Niveau,pk=niv_id,etablissement=etab)
        try:
            classe.capacite_max = int(request.POST.get("capacite_max", classe.capacite_max))
        except ValueError:
            messages.warning(request, "Capacité invalide ignorée.")
            
        classe.salle=request.POST.get("salle",""); classe.save()
        messages.success(request,"Classe mise a jour."); return redirect("detail_classe",pk=classe.pk)
    return render(request,"eleves/modifier_classe.html",{"classe":classe,"niveaux":niveaux})
