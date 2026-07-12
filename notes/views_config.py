
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from .models import Matiere, Periode
from etablissements.models import AnneeScolaire

def req(fn):
    def w(request,*a,**k):
        if not request.user.is_admin or not request.etablissement: return redirect("dashboard")
        return fn(request,*a,**k)
    w.__name__=fn.__name__; return w

@login_required
@req
def liste_matieres(request):
    etab=request.etablissement
    return render(request,"notes/config/matieres.html",{"matieres":Matiere.objects.filter(etablissement=etab).order_by("nom")})

@login_required
@req
def ajouter_matiere(request):
    etab=request.etablissement
    if request.method=="POST":
        nom=request.POST.get("nom","").strip(); code=request.POST.get("code","").strip().upper()
        coef=int(request.POST.get("coefficient",1)); is_c=bool(request.POST.get("is_conduite"))
        if not nom: messages.error(request,"Nom obligatoire.")
        elif Matiere.objects.filter(etablissement=etab,nom=nom).exists(): messages.error(request,f"{nom} existe deja.")
        else:
            Matiere.objects.create(etablissement=etab,nom=nom,code=code,coefficient=coef,is_conduite=is_c)
            messages.success(request,f"Matiere {nom} creee."); return redirect("liste_matieres")
    return render(request,"notes/config/form_matiere.html",{"mode":"ajouter"})

@login_required
@req
def modifier_matiere(request,pk):
    etab=request.etablissement; m=get_object_or_404(Matiere,pk=pk,etablissement=etab)
    if request.method=="POST":
        if request.POST.get("action")=="supprimer": m.delete(); messages.success(request,"Matiere supprimee."); return redirect("liste_matieres")
        m.nom=request.POST.get("nom",m.nom).strip(); m.code=request.POST.get("code","").strip().upper()
        m.coefficient=int(request.POST.get("coefficient",1)); m.is_conduite=bool(request.POST.get("is_conduite"))
        m.save(); messages.success(request,"Matiere mise a jour."); return redirect("liste_matieres")
    return render(request,"notes/config/form_matiere.html",{"mode":"modifier","matiere":m})

@login_required
@req
def liste_periodes(request):
    etab=request.etablissement; annees=AnneeScolaire.objects.filter(etablissement=etab).order_by("-libelle")
    periodes=Periode.objects.filter(etablissement=etab).select_related("annee").order_by("-annee__libelle","numero")
    return render(request,"notes/config/periodes.html",{"periodes":periodes,"annees":annees})

@login_required
@req
def ajouter_periode(request):
    etab=request.etablissement; annees=AnneeScolaire.objects.filter(etablissement=etab).order_by("-libelle")
    if request.method=="POST":
        aid=request.POST.get("annee"); lib=request.POST.get("libelle","").strip()
        tp=request.POST.get("type","trimestre"); num=int(request.POST.get("numero",1))
        dd=request.POST.get("date_debut"); df=request.POST.get("date_fin"); ia=bool(request.POST.get("is_active"))
        if not lib or not aid: messages.error(request,"Champs obligatoires manquants.")
        else:
            annee=get_object_or_404(AnneeScolaire,pk=aid,etablissement=etab)
            if Periode.objects.filter(etablissement=etab,annee=annee,numero=num).exists():
                messages.error(request,f"Periode numero {num} existe deja.")
            else:
                if ia: Periode.objects.filter(etablissement=etab,annee=annee).update(is_active=False)
                Periode.objects.create(etablissement=etab,annee=annee,type=tp,numero=num,libelle=lib,date_debut=dd,date_fin=df,is_active=ia)
                messages.success(request,f"Periode {lib} creee."); return redirect("liste_periodes")
    return render(request,"notes/config/form_periode.html",{"mode":"ajouter","annees":annees})

@login_required
@req
def modifier_periode(request,pk):
    etab=request.etablissement; p=get_object_or_404(Periode,pk=pk,etablissement=etab)
    annees=AnneeScolaire.objects.filter(etablissement=etab).order_by("-libelle")
    if request.method=="POST":
        if request.POST.get("action")=="supprimer": p.delete(); messages.success(request,"Periode supprimee."); return redirect("liste_periodes")
        if request.POST.get("action")=="activer":
            Periode.objects.filter(etablissement=etab,annee=p.annee).update(is_active=False)
            p.is_active=True; p.save(); messages.success(request,f"{p.libelle} activee."); return redirect("liste_periodes")
        p.libelle=request.POST.get("libelle",p.libelle); p.type=request.POST.get("type","trimestre")
        p.numero=int(request.POST.get("numero",p.numero))
        dd=request.POST.get("date_debut"); df=request.POST.get("date_fin")
        if dd: p.date_debut=dd
        if df: p.date_fin=df
        p.save(); messages.success(request,"Periode mise a jour."); return redirect("liste_periodes")
    return render(request,"notes/config/form_periode.html",{"mode":"modifier","periode":p,"annees":annees})

@login_required
@req
def liste_types_frais(request):
    etab=request.etablissement
    from finances.models import TypeFrais
    from etablissements.models import AnneeScolaire
    from django.db.models import Q
    annee=AnneeScolaire.objects.filter(etablissement=etab,is_active=True).first()
    types=TypeFrais.objects.filter(etablissement=etab).filter(Q(annee=annee)|Q(annee__isnull=True))
    return render(request,"notes/config/types_frais.html",{"types":types,"annee":annee})

@login_required
@req
def ajouter_type_frais(request):
    etab=request.etablissement
    from finances.models import TypeFrais
    from etablissements.models import AnneeScolaire
    annee=AnneeScolaire.objects.filter(etablissement=etab,is_active=True).first()
    if request.method=="POST":
        nom=request.POST.get("nom","").strip(); montant=request.POST.get("montant_defaut",0)
        oblig=bool(request.POST.get("is_obligatoire")); desc=request.POST.get("description","")
        periodicite=request.POST.get("periodicite","unique")
        nb_tranches=int(request.POST.get("nombre_tranches",1) or 1)
        if not nom: messages.error(request,"Nom obligatoire.")
        elif TypeFrais.objects.filter(etablissement=etab,nom=nom,annee=annee).exists(): messages.error(request,f"{nom} existe deja pour cette annee.")
        else:
            TypeFrais.objects.create(etablissement=etab,annee=annee,nom=nom,montant_defaut=montant,is_obligatoire=oblig,description=desc,periodicite=periodicite,nombre_tranches=nb_tranches)
            messages.success(request,f"Type {nom} cree."); return redirect("liste_types_frais")
    return render(request,"notes/config/form_type_frais.html",{"mode":"ajouter","annee":annee})

@login_required
@req
def modifier_type_frais(request,pk):
    etab=request.etablissement
    from finances.models import TypeFrais
    from etablissements.models import AnneeScolaire
    tf=get_object_or_404(TypeFrais,pk=pk,etablissement=etab)
    annee_active=AnneeScolaire.objects.filter(etablissement=etab,is_active=True).first()
    if request.method=="POST":
        if request.POST.get("action")=="supprimer": tf.delete(); messages.success(request,"Supprime."); return redirect("liste_types_frais")
        tf.nom=request.POST.get("nom",tf.nom); tf.montant_defaut=request.POST.get("montant_defaut",tf.montant_defaut)
        tf.is_obligatoire=bool(request.POST.get("is_obligatoire")); tf.description=request.POST.get("description","")
        tf.periodicite=request.POST.get("periodicite",tf.periodicite)
        tf.nombre_tranches=int(request.POST.get("nombre_tranches",tf.nombre_tranches) or 1)
        # Permettre de lier/délier l'année active
        lier_annee=request.POST.get("lier_annee_active")
        if lier_annee=="oui" and annee_active and tf.annee is None:
            tf.annee=annee_active
        tf.save(); messages.success(request,"Mis a jour."); return redirect("liste_types_frais")
    return render(request,"notes/config/form_type_frais.html",{"mode":"modifier","tf":tf,"annee_active":annee_active})
