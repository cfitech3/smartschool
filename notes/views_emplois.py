
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from .models import EmploiDuTemps, Matiere
from etablissements.models import Classe, AnneeScolaire, Enseignant
from core.cycle_filter import get_cycles_actifs_ids, get_classes_actives, get_eleves_actifs, get_inscriptions_actives

HEURES=["07:00","07:30","08:00","08:30","09:00","09:30","10:00","10:30","11:00","11:30","12:00","12:30","13:00","13:30","14:00","14:30","15:00","15:30","16:00","16:30","17:00","17:30","18:00"]
JOURS_ORDRE=["lundi","mardi","mercredi","jeudi","vendredi","samedi"]

def req(fn):
    def w(request,*a,**k):
        if not request.etablissement: return redirect("dashboard")
        return fn(request,*a,**k)
    w.__name__=fn.__name__; return w

@login_required
@req
def emploi_du_temps(request):
    etab=request.etablissement; annee=AnneeScolaire.objects.filter(etablissement=etab,is_active=True).first()
    classes=get_classes_actives(etab, annee) if annee else []
    matieres=Matiere.objects.filter(etablissement=etab); enseignants=Enseignant.objects.filter(etablissement=etab).select_related("user")
    classe_id=request.GET.get("classe"); classe=get_object_or_404(Classe,pk=classe_id,etablissement=etab) if classe_id else None
    creneaux={}
    if classe:
        edts=EmploiDuTemps.objects.filter(etablissement=etab,classe=classe).select_related("matiere","enseignant").order_by("jour","heure_debut")
        for j in JOURS_ORDRE: creneaux[j]=[e for e in edts if e.jour==j]
    if request.method=="POST" and classe:
        jour=request.POST.get("jour"); mat_id=request.POST.get("matiere"); ens_id=request.POST.get("enseignant") or None
        hd=request.POST.get("heure_debut"); hf=request.POST.get("heure_fin"); salle=request.POST.get("salle","")
        if jour and mat_id and hd and hf:
            ens_user=None
            if ens_id:
                try: ens_user=Enseignant.objects.get(pk=ens_id,etablissement=etab).user
                except: pass
            EmploiDuTemps.objects.create(etablissement=etab,classe=classe,matiere_id=mat_id,enseignant=ens_user,jour=jour,heure_debut=hd,heure_fin=hf,salle=salle)
            messages.success(request,"Creneau ajoute.")
        return redirect(f"/notes/emplois/?classe={classe_id}")
    return render(request,"notes/emploi_du_temps.html",{"classes":classes,"classe":classe,"matieres":matieres,"enseignants":enseignants,"creneaux":creneaux,"jours":EmploiDuTemps.JOURS,"jours_ordre":JOURS_ORDRE,"heures":HEURES,"classe_id":classe_id})

@login_required
@req
def supprimer_creneau(request,pk):
    etab=request.etablissement; c=get_object_or_404(EmploiDuTemps,pk=pk,etablissement=etab)
    cid=c.classe.pk; c.delete(); messages.success(request,"Creneau supprime.")
    return redirect(f"/notes/emplois/?classe={cid}")
