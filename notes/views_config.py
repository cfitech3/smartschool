
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from .models import Matiere, Periode
from accounts.permissions import admin_etab_required as req
from etablissements.models import AnneeScolaire

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
        try:
            coef=max(1, int(request.POST.get("coefficient",1)))
        except (ValueError, TypeError):
            coef=1
        is_c=bool(request.POST.get("is_conduite"))
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
        if request.POST.get("action")=="supprimer":
            from .models import NotePeriode, Composition
            nb_notes = NotePeriode.objects.filter(matiere=m).count() + Composition.objects.filter(matiere=m).count()
            if nb_notes > 0:
                messages.error(request, f"Impossible de supprimer la matière « {m.nom} » : {nb_notes} note(s) y sont rattachées.")
                return redirect("liste_matieres")
            m.delete(); messages.success(request,"Matiere supprimee."); return redirect("liste_matieres")
        nouveau_nom=request.POST.get("nom",m.nom).strip()
        if Matiere.objects.filter(etablissement=etab, nom=nouveau_nom).exclude(pk=m.pk).exists():
            messages.error(request, f"Une matière nommée '{nouveau_nom}' existe déjà.")
            return redirect("liste_matieres")
        m.nom=nouveau_nom; m.code=request.POST.get("code","").strip().upper()
        try:
            m.coefficient=max(1, int(request.POST.get("coefficient",1)))
        except (ValueError, TypeError):
            pass
        m.is_conduite=bool(request.POST.get("is_conduite"))
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
        tp=request.POST.get("type","trimestre")
        try:
            num=max(1, int(request.POST.get("numero",1)))
        except (ValueError, TypeError):
            num=1
        dd=request.POST.get("date_debut"); df=request.POST.get("date_fin"); ia=bool(request.POST.get("is_active"))
        if not lib or not aid or not dd or not df: messages.error(request,"Champs obligatoires manquants.")
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
        if request.POST.get("action")=="supprimer":
            from .models import NotePeriode, NoteUE, Bulletin
            nb_lies = (
                NotePeriode.objects.filter(periode=p).count()
                + NoteUE.objects.filter(periode=p).count()
                + Bulletin.objects.filter(periode=p).count()
            )
            if nb_lies > 0:
                messages.error(request, f"Impossible de supprimer la période « {p.libelle} » : {nb_lies} note(s) ou bulletin(s) y sont rattachés.")
                return redirect("liste_periodes")
            p.delete(); messages.success(request,"Periode supprimee."); return redirect("liste_periodes")
        if request.POST.get("action")=="activer":
            Periode.objects.filter(etablissement=etab,annee=p.annee).update(is_active=False)
            p.is_active=True; p.save(); messages.success(request,f"{p.libelle} activee."); return redirect("liste_periodes")
        if request.POST.get("action")=="toggle_cloture":
            from django.utils import timezone
            p.saisie_cloturee = not p.saisie_cloturee
            p.date_cloture = timezone.now() if p.saisie_cloturee else None
            p.cloture_par = request.user if p.saisie_cloturee else None
            p.save(update_fields=["saisie_cloturee", "date_cloture", "cloture_par"])
            etat = "clôturée (saisie verrouillée)" if p.saisie_cloturee else "réouverte à la saisie"
            messages.success(request, f"Période {p.libelle} {etat}.")
            return redirect("liste_periodes")
        p.libelle=request.POST.get("libelle",p.libelle).strip() or p.libelle
        p.type=request.POST.get("type","trimestre")
        try:
            nouveau_num=max(1, int(request.POST.get("numero",p.numero)))
        except (ValueError, TypeError):
            nouveau_num=p.numero
        if Periode.objects.filter(etablissement=etab, annee=p.annee, numero=nouveau_num).exclude(pk=p.pk).exists():
            messages.error(request, f"Une période numéro {nouveau_num} existe déjà pour cette année.")
            return redirect("liste_periodes")
        p.numero=nouveau_num
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
        from decimal import Decimal, InvalidOperation
        nom=request.POST.get("nom","").strip()
        try:
            montant=max(Decimal("0"), Decimal(str(request.POST.get("montant_defaut",0) or 0)))
        except (InvalidOperation, ValueError, TypeError):
            montant=Decimal("0")
        oblig=bool(request.POST.get("is_obligatoire")); desc=request.POST.get("description","")
        periodicite=request.POST.get("periodicite","unique")
        try:
            nb_tranches=max(1, int(request.POST.get("nombre_tranches",1) or 1))
        except (ValueError, TypeError):
            nb_tranches=1
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
        from decimal import Decimal, InvalidOperation
        if request.POST.get("action")=="supprimer":
            from finances.models import Paiement
            nb_paiements = Paiement.objects.filter(type_frais=tf).count()
            if nb_paiements > 0:
                messages.error(request, f"Impossible de supprimer le frais « {tf.nom} » : {nb_paiements} paiement(s) comptabilisé(s) y sont rattachés.")
                return redirect("liste_types_frais")
            tf.delete(); messages.success(request,"Supprime."); return redirect("liste_types_frais")
        tf.nom=request.POST.get("nom",tf.nom).strip() or tf.nom
        try:
            tf.montant_defaut=max(Decimal("0"), Decimal(str(request.POST.get("montant_defaut",tf.montant_defaut) or 0)))
        except (InvalidOperation, ValueError, TypeError):
            pass
        tf.is_obligatoire=bool(request.POST.get("is_obligatoire")); tf.description=request.POST.get("description","")
        tf.periodicite=request.POST.get("periodicite",tf.periodicite)
        try:
            tf.nombre_tranches=max(1, int(request.POST.get("nombre_tranches",tf.nombre_tranches) or 1))
        except (ValueError, TypeError):
            pass
        # Permettre de lier/délier l'année active
        lier_annee=request.POST.get("lier_annee_active")
        if lier_annee=="oui" and annee_active and tf.annee is None:
            tf.annee=annee_active
        tf.save(); messages.success(request,"Mis a jour."); return redirect("liste_types_frais")
    return render(request,"notes/config/form_type_frais.html",{"mode":"modifier","tf":tf,"annee_active":annee_active})
