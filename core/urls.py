from django.urls import path
from . import views, views_documents, views_espace_famille, views_dashboard
urlpatterns = [
    path('', views.dashboard, name='home'),
    path('dashboard/', views_dashboard.dashboard, name='dashboard'),
    path('changer-etablissement/<int:etab_id>/', views.changer_etablissement, name='changer_etablissement'),
    path('recherche/', views_documents.recherche_globale, name='recherche'),
    path('documents/', views_documents.liste_documents, name='liste_documents'),
    path('documents/<int:eleve_pk>/<str:type_doc>/', views_documents.generer_document, name='generer_document'),
    path('carte-scolaire/<int:eleve_pk>/', views_documents.carte_scolaire, name='carte_scolaire'),
    path('export/eleves/', views_documents.export_eleves_excel, name='export_eleves'),
    path('export/paiements/', views_documents.export_paiements_excel, name='export_paiements'),
    path('notifications/', views.notifications, name='notifications'),
    path('notifications/<int:pk>/lire/', views.marquer_notif_lue, name='marquer_notif_lue'),
    # Espace famille (parents et eleves)
    path('espace/', views_espace_famille.espace_accueil, name='espace_accueil'),
    path('espace/<int:eleve_pk>/', views_espace_famille.espace_eleve_detail, name='espace_eleve_detail'),
    path('espace/<int:eleve_pk>/notes/', views_espace_famille.espace_notes, name='espace_notes'),
    path('espace/<int:eleve_pk>/absences/', views_espace_famille.espace_absences, name='espace_absences'),
    path('espace/<int:eleve_pk>/bulletin/<int:periode_pk>/', views_espace_famille.espace_bulletin, name='espace_bulletin'),
    path('espace/<int:eleve_pk>/reclamations/', views_espace_famille.espace_reclamations, name='espace_reclamations'),
    path('espace/<int:eleve_pk>/paiements/', views_espace_famille.espace_paiements, name='espace_paiements'),
    path('espace/<int:eleve_pk>/emploi-du-temps/', views_espace_famille.espace_emploi_du_temps, name='espace_emploi_du_temps'),
    path('espace/<int:eleve_pk>/reclamer/<int:note_pk>/', views_espace_famille.creer_reclamation, name='creer_reclamation'),
    # Administration des reclamations
    path('reclamations/', views_espace_famille.liste_reclamations_admin, name='liste_reclamations_admin'),
    path('reclamations/<int:pk>/', views_espace_famille.traiter_reclamation, name='traiter_reclamation'),
    # Messagerie famille
    path('espace/<int:eleve_pk>/messages/', views_espace_famille.espace_messages, name='espace_messages'),
    path('espace/<int:eleve_pk>/messages/nouveau/', views_espace_famille.envoyer_message, name='envoyer_message'),
    # Admin messagerie
    path('messages/', views_espace_famille.admin_messages, name='admin_messages'),
    path('messages/<int:pk>/', views_espace_famille.admin_repondre_message, name='admin_repondre_message'),
]
