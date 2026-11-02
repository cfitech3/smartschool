
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from accounts.permissions import permission_required
from .models import Eleve, Tuteur, Inscription
from etablissements.models import Classe, AnneeScolaire, Niveau
from core.cycle_filter import get_cycles_actifs_ids, get_classes_actives, get_eleves_actifs, get_inscriptions_actives

def req(fn):
    def w(request,*a,**k):
        if not request.etablissement: return redirect("dashboard")
        return fn(request,*a,**k)
    w.__name__=fn.__name__; return w

@login_required
@permission_required("eleves")
@req
def modifier_eleve_complet(request,pk):
    etab=request.etablissement
    eleve=get_object_or_404(Eleve,pk=pk,etablissement=etab)
    annee=AnneeScolaire.objects.filter(etablissement=etab,is_active=True).first()
    inscription=eleve.get_inscription_active()
    classes=get_classes_actives(etab, annee, user=request.user).select_related("niveau").order_by("niveau__ordre","nom") if annee else []
    if request.method=="POST":
        eleve.nom=request.POST.get("nom",eleve.nom).strip()
        eleve.prenom=request.POST.get("prenom",eleve.prenom).strip()
        eleve.sexe=request.POST.get("sexe",eleve.sexe)
        dob=request.POST.get("date_naissance")
        if dob: eleve.date_naissance=dob
        eleve.lieu_naissance=request.POST.get("lieu_naissance","").strip()
        eleve.adresse=request.POST.get("adresse","").strip()
        eleve.telephone=request.POST.get("telephone","").strip()
        if request.FILES.get("photo"):
            from etablissements.views import _valider_photo
            err_photo = _valider_photo(request.FILES["photo"])
            if err_photo:
                messages.error(request, err_photo)
                return redirect("modifier_eleve_complet", pk=eleve.pk)
            eleve.photo=request.FILES["photo"]
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
            tprenom = request.POST.get("tut_prenom", "").strip()
            ttel = request.POST.get("tut_telephone", "").strip()
            tlien = request.POST.get("tut_lien", "pere")
            if eleve.tuteur:
                t = eleve.tuteur
                est_partage = Eleve.objects.filter(tuteur=t).exclude(pk=eleve.pk).exists()
                identite_changee = (t.nom != tnom or t.prenom != tprenom or (ttel and t.telephone != ttel))
                if est_partage and identite_changee:
                    nouv_t = Tuteur.objects.create(
                        etablissement=etab, nom=tnom, prenom=tprenom,
                        telephone=ttel, lien=tlien
                    )
                    eleve.tuteur = nouv_t
                    eleve.save(update_fields=['tuteur'])
                else:
                    t.nom = tnom
                    t.prenom = tprenom
                    t.telephone = ttel
                    t.lien = tlien
                    t.save()
            else:
                t=Tuteur.objects.create(etablissement=etab,nom=tnom,prenom=tprenom,
                    telephone=ttel,lien=tlien)
                eleve.tuteur=t; eleve.save(update_fields=['tuteur'])
        messages.success(request,f"{eleve.nom_complet} mis a jour.")
        return redirect("detail_eleve",pk=eleve.pk)
    return render(request,"eleves/modifier_complet.html",{"eleve":eleve,"inscription":inscription,"classes":classes,"annee":annee})
