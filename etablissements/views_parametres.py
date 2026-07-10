
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from .models import Etablissement, ParametreEtablissement, AnneeScolaire, Niveau

@login_required
def parametres(request):
    etab = request.etablissement
    if not etab: return redirect("dashboard")
    if not request.user.is_admin: return redirect("dashboard")
    params,_=ParametreEtablissement.objects.get_or_create(etablissement=etab)
    annees=AnneeScolaire.objects.filter(etablissement=etab).order_by("-libelle")
    niveaux=Niveau.objects.filter(etablissement=etab).order_by("ordre")
    if request.method=="POST":
        action=request.POST.get("action")
        if action=="infos":
            etab.nom=request.POST.get("nom",etab.nom)
            etab.type=request.POST.get("type",etab.type)
            etab.adresse=request.POST.get("adresse","")
            etab.telephone=request.POST.get("telephone","")
            etab.email=request.POST.get("email","")
            etab.directeur=request.POST.get("directeur","")
            etab.slogan=request.POST.get("slogan","")
            etab.couleur_principale=request.POST.get("couleur_principale","#1565C0")
            etab.couleur_secondaire=request.POST.get("couleur_secondaire","#0D47A1")
            if request.FILES.get("logo"):
                etab.logo=request.FILES["logo"]
            elif request.POST.get("supprimer_logo") and etab.logo:
                import os
                if os.path.exists(etab.logo.path):
                    os.remove(etab.logo.path)
                etab.logo=None
            etab.save(); messages.success(request,"Informations mises a jour.")
        elif action=="params":
            params.devise=request.POST.get("devise","FCFA")
            params.type_periode=request.POST.get("type_periode","trimestre")
            params.note_passage=request.POST.get("note_passage",10)
            params.entete_bulletin=request.POST.get("entete_bulletin","")
            params.pied_bulletin=request.POST.get("pied_bulletin","")
            params.save(); messages.success(request,"Parametres mis a jour.")
        elif action=="annee":
            lib=request.POST.get("libelle","").strip(); dd=request.POST.get("date_debut"); df=request.POST.get("date_fin")
            if lib and dd and df:
                _,c=AnneeScolaire.objects.get_or_create(etablissement=etab,libelle=lib,defaults={"date_debut":dd,"date_fin":df})
                messages.success(request,f"Annee {lib} creee." if c else "Annee deja existante.")
        elif action=="activer_annee":
            aid=request.POST.get("annee_id")
            AnneeScolaire.objects.filter(etablissement=etab).update(is_active=False)
            AnneeScolaire.objects.filter(pk=aid,etablissement=etab).update(is_active=True)
            messages.success(request,"Annee activee.")
        elif action=="niveau":
            nom=request.POST.get("nom","").strip(); ordre=request.POST.get("ordre",0)
            if nom:
                Niveau.objects.get_or_create(etablissement=etab,nom=nom,defaults={"ordre":ordre})
                messages.success(request,f"Niveau {nom} ajoute.")
        return redirect("parametres")
    return render(request,"etablissements/parametres.html",{
        "etab":etab,"params":params,"annees":annees,"niveaux":niveaux,
        "types_etab":Etablissement.TYPES,
    })
