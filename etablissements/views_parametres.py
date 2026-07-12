
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
            # WARN 5 : Invalider le cache de l'année active immédiatement
            from django.core.cache import cache
            cache.delete(f"annee_active_{etab.pk}")
            messages.success(request,"Annee activee.")
        elif action=="dupliquer_annee":
            # P3.2 : Duplication d'année scolaire complète
            from django.db import transaction
            from etablissements.models import Classe
            from finances.models import TypeFrais
            from notes.models import Periode
            import datetime
            
            aid = request.POST.get("annee_id")
            nouv_lib = request.POST.get("nouveau_libelle", "").strip()
            nouv_dd = request.POST.get("nouvelle_date_debut")
            nouv_df = request.POST.get("nouvelle_date_fin")
            
            try:
                if not (nouv_lib and nouv_dd and nouv_df):
                    raise ValueError("Tous les champs sont obligatoires.")
                
                annee_source = get_object_or_404(AnneeScolaire, pk=aid, etablissement=etab)
                if AnneeScolaire.objects.filter(etablissement=etab, libelle=nouv_lib).exists():
                    raise ValueError("Une année avec ce libellé existe déjà.")
                
                with transaction.atomic():
                    # 1. Créer la nouvelle année
                    nouvelle_annee = AnneeScolaire.objects.create(
                        etablissement=etab, libelle=nouv_lib,
                        date_debut=nouv_dd, date_fin=nouv_df, is_active=False
                    )
                    
                    # 2. Dupliquer les Types de Frais liés à l'année source
                    # On inclut aussi les TypeFrais sans année (annee=NULL) créés manuellement
                    from django.db.models import Q as _Q
                    for tf in TypeFrais.objects.filter(
                        etablissement=etab
                    ).filter(_Q(annee=annee_source) | _Q(annee__isnull=True)):
                        # Eviter les doublons si un TypeFrais global est déjà lié à la nouvelle annee
                        if not TypeFrais.objects.filter(
                            etablissement=etab, annee=nouvelle_annee, nom=tf.nom
                        ).exists():
                            TypeFrais.objects.create(
                                etablissement=etab, annee=nouvelle_annee, nom=tf.nom,
                                montant_defaut=tf.montant_defaut, is_obligatoire=tf.is_obligatoire,
                                description=tf.description
                            )
                        
                    # 3. Dupliquer les classes
                    nb_classes = 0
                    for classe in Classe.objects.filter(etablissement=etab, annee=annee_source):
                        Classe.objects.create(
                            etablissement=etab, annee=nouvelle_annee, niveau=classe.niveau,
                            nom=classe.nom, capacite_max=classe.capacite_max,
                            salle=classe.salle,
                        )
                        nb_classes += 1

                    # 4. Dupliquer les Périodes de l'année source vers la nouvelle année
                    # (Periode est liée à etablissement+annee, pas à une classe)
                    nb_periodes = 0
                    for periode in Periode.objects.filter(etablissement=etab, annee=annee_source):
                        if not Periode.objects.filter(
                            etablissement=etab, annee=nouvelle_annee, numero=periode.numero
                        ).exists():
                            Periode.objects.create(
                                etablissement=etab, annee=nouvelle_annee,
                                type=periode.type, numero=periode.numero,
                                libelle=periode.libelle,
                                date_debut=periode.date_debut,
                                date_fin=periode.date_fin,
                                is_active=False,  # Toujours ré-ouvrir les périodes par défaut
                            )
                            nb_periodes += 1

                messages.success(request, f"Année {nouv_lib} créée avec succès. {nb_classes} classes et {nb_periodes} périodes dupliquées.")
            except Exception as e:
                messages.error(request, f"Erreur lors de la duplication : {e}")
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
