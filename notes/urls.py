from django.urls import path
from . import views, views_notes, views_universite, views_emplois, views_config, views_surveillant, views_bulletin_mali

urlpatterns = [
    # Notes
    path('saisie/', views_notes.saisie_notes_mali, name='saisie_notes_mali'),
    path('releve/', views_notes.releve_notes_classe, name='releve_notes_classe'),
    path('bulletins/', views_notes.bulletins_classe_mali, name='bulletins_classe_mali'),
    path('bulletin/<int:eleve_pk>/<int:periode_pk>/', views_notes.bulletin_eleve, name='bulletin_eleve'),
    path('bulletin/<int:eleve_pk>/<int:periode_pk>/<int:modele_pk>/', views_notes.bulletin_eleve, name='bulletin_eleve_modele'),
    path('bulletin/<int:eleve_pk>/<int:periode_pk>/pdf/', views_bulletin_mali.telecharger_bulletin_pdf_mali, name='telecharger_bulletin_pdf_mali'),
    path('logs/', views_notes.logs_modifications, name='logs_modifications'),
    # Surveillant
    path('conduite/', views_surveillant.saisie_conduite, name='saisie_conduite'),
    path('absences/', views_surveillant.rapport_absences, name='rapport_absences'),
    # Emplois du temps
    path('emplois/', views_emplois.emploi_du_temps, name='emploi_du_temps'),
    path('emplois/supprimer/<int:pk>/', views_emplois.supprimer_creneau, name='supprimer_creneau'),
    # Config
    path('matieres/', views_config.liste_matieres, name='liste_matieres'),
    path('matieres/ajouter/', views_config.ajouter_matiere, name='ajouter_matiere'),
    path('matieres/<int:pk>/', views_config.modifier_matiere, name='modifier_matiere'),
    path('periodes/', views_config.liste_periodes, name='liste_periodes'),
    path('periodes/ajouter/', views_config.ajouter_periode, name='ajouter_periode'),
    path('periodes/<int:pk>/', views_config.modifier_periode, name='modifier_periode'),
    path('frais/', views_config.liste_types_frais, name='liste_types_frais'),
    path('frais/ajouter/', views_config.ajouter_type_frais, name='ajouter_type_frais'),
    path('frais/<int:pk>/', views_config.modifier_type_frais, name='modifier_type_frais'),
    path('universite/saisie/', views_universite.saisie_notes_ue, name='saisie_notes_ue'),
    path('universite/releve/<int:eleve_pk>/<int:periode_pk>/', views_universite.releve_notes_lmd, name='releve_notes_lmd'),
]