from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from eleves.models import Eleve, Inscription
from etablissements.models import Classe, AnneeScolaire
from core.cycle_filter import get_classes_actives

@login_required
def assistant_fin_annee(request):
    if not request.user.role in ['admin', 'super_admin', 'secretariat']:
        messages.error(request, "Accès refusé.")
        return redirect('dashboard')
        
    etab = request.etablissement
    annees = AnneeScolaire.objects.filter(etablissement=etab).order_by('-date_debut')
    annee_active = annees.filter(is_active=True).first()
    classes = get_classes_actives(etab, annee_active) if annee_active else []
    
    classe_actuelle_id = request.GET.get('classe_actuelle')
    annee_suivante_id = request.GET.get('annee_suivante')
    
    classe_actuelle = None
    annee_suivante = None
    eleves_data = []
    
    if classe_actuelle_id and annee_suivante_id:
        classe_actuelle = get_object_or_404(Classe, pk=classe_actuelle_id, etablissement=etab)
        annee_suivante = get_object_or_404(AnneeScolaire, pk=annee_suivante_id, etablissement=etab)
        
        # Récupérer les élèves inscrits dans cette classe pour l'année active
        inscriptions = classe_actuelle.inscriptions.filter(annee=annee_active, is_active=True).select_related('eleve')
        
        for insc in inscriptions:
            # Vérifier si l'élève a déjà une inscription pour l'année suivante
            deja_inscrit = Inscription.objects.filter(eleve=insc.eleve, annee=annee_suivante).exists()
            eleves_data.append({
                'inscription': insc,
                'eleve': insc.eleve,
                'deja_inscrit': deja_inscrit
            })

    if request.method == "POST":
        classe_suivante_id = request.POST.get('classe_suivante_globale')
        try:
            with transaction.atomic():
                nb_admis = 0
                for data in eleves_data:
                    eleve = data['eleve']
                    if data['deja_inscrit']:
                        continue
                        
                    decision = request.POST.get(f"decision_{eleve.pk}")
                    
                    if decision == "admis" and classe_suivante_id:
                        classe_dest = get_object_or_404(Classe, pk=classe_suivante_id, etablissement=etab)
                        Inscription.objects.create(eleve=eleve, classe=classe_dest, annee=annee_suivante, statut='actif')
                        nb_admis += 1
                        
                    elif decision == "redouble":
                        Inscription.objects.create(eleve=eleve, classe=classe_actuelle, annee=annee_suivante, statut='actif')
                        nb_admis += 1
                        
                messages.success(request, f"L'assistant a traité {nb_admis} passage(s) avec succès pour l'année {annee_suivante.libelle}.")
                return redirect('assistant_fin_annee')
                
        except Exception as e:
            messages.error(request, f"Une erreur s'est produite : {str(e)}")
            
    return render(request, 'eleves/assistant_fin_annee.html', {
        'annees': annees,
        'annee_active': annee_active,
        'classes': classes,
        'classe_actuelle': classe_actuelle,
        'annee_suivante': annee_suivante,
        'eleves_data': eleves_data,
        'classe_actuelle_id': classe_actuelle_id,
        'annee_suivante_id': annee_suivante_id
    })
