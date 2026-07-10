
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from .models import Eleve, Tuteur, Inscription
from etablissements.models import Classe, AnneeScolaire, Niveau
from core.cycle_filter import get_cycles_actifs_ids, get_classes_actives, get_eleves_actifs, get_inscriptions_actives

def req(fn):
    def w(request,*a,**k):
        if not request.etablissement: return redirect("dashboard")
        return fn(request,*a,**k)
    w.__name__=fn.__name__; return w

@login_required
@req
def modifier_eleve_complet(request,pk):
    etab=request.etablissement
    eleve=get_object_or_404(Eleve,pk=pk,etablissement=etab)
    annee=AnneeScolaire.objects.filter(etablissement=etab,is_active=True).first()
    inscription=eleve.get_inscription_active()
    classes=get_classes_actives(etab, annee).select_related("niveau").order_by("niveau__ordre","nom") if annee else []
    if request.method=="POST":
        eleve.nom=request.POST.get("nom",eleve.nom).strip()
        eleve.prenom=request.POST.get("prenom",eleve.prenom).strip()
        eleve.sexe=request.POST.get("sexe",eleve.sexe)
        dob=request.POST.get("date_naissance")
        if dob: eleve.date_naissance=dob
        eleve.lieu_naissance=request.POST.get("lieu_naissance","").strip()
        eleve.adresse=request.POST.get("adresse","").strip()
        eleve.telephone=request.POST.get("telephone","").strip()
        if request.FILES.get("photo"): eleve.photo=request.FILES["photo"]
        eleve.save()
        # Changer classe
        nv_cl=request.POST.get("classe")
        if nv_cl and annee:
            nc=get_object_or_404(Classe,pk=nv_cl,etablissement=etab)
            if inscription:
                if inscription.classe.pk!=nc.pk:
                    inscription.classe=nc; inscription.save()
                    messages.success(request,f"Classe changee vers {nc.nom}.")
            else:
                Inscription.objects.create(eleve=eleve,classe=nc,annee=annee,statut="actif")
                messages.success(request,f"Eleve affecte a {nc.nom}.")
        # Tuteur
        tnom=request.POST.get("tut_nom","").strip()
        if tnom:
            if eleve.tuteur:
                t=eleve.tuteur; t.nom=tnom; t.prenom=request.POST.get("tut_prenom","")
                t.telephone=request.POST.get("tut_telephone",""); t.lien=request.POST.get("tut_lien","pere"); t.save()
            else:
                t=Tuteur.objects.create(etablissement=etab,nom=tnom,prenom=request.POST.get("tut_prenom",""),
                    telephone=request.POST.get("tut_telephone",""),lien=request.POST.get("tut_lien","pere"))
                eleve.tuteur=t; eleve.save()
        messages.success(request,f"{eleve.nom_complet} mis a jour.")
        return redirect("detail_eleve",pk=eleve.pk)
    return render(request,"eleves/modifier_complet.html",{"eleve":eleve,"inscription":inscription,"classes":classes,"annee":annee})
