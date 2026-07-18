from django.urls import path
from . import views, views_parametres, views_modeles, views_cycles, views_divisions, views_superadmin, views_saas

urlpatterns = [
    # Super Admin — Gestion des établissements
    path('saas/', views_saas.dashboard_saas, name='dashboard_saas'),
    path('saas/journal/', views_saas.journal_actions, name='journal_actions'),
    path('saas/stats/', views_saas.stats_commerciales, name='stats_commerciales'),
    path('saas/parametres/', views_saas.parametres_reseau, name='parametres_reseau'),
    path('saas/export/', views_saas.export_rapport_reseau, name='export_rapport_reseau'),
    path('gerer/<int:etab_pk>/directeur/', views_saas.creer_directeur, name='creer_directeur'),
    path('gerer/', views_superadmin.liste_etablissements, name='liste_etablissements'),
    path('gerer/creer/', views_superadmin.creer_etablissement, name='creer_etablissement'),
    path('gerer/<int:pk>/modifier/', views_superadmin.modifier_etablissement, name='modifier_etablissement'),
    path('gerer/<int:pk>/voir/', views_superadmin.voir_etablissement, name='voir_etablissement'),
    path('gerer/<int:pk>/comptes/', views_superadmin.gestion_comptes_etab, name='gestion_comptes_etab'),
    path('gerer/<int:pk>/toggle/', views_superadmin.toggle_etablissement, name='toggle_etablissement'),

    # Enseignants
    path('enseignants/', views.liste_enseignants, name='liste_enseignants'),
    path('enseignants/ajouter/', views.ajouter_enseignant, name='ajouter_enseignant'),
    path('enseignants/<int:pk>/', views.detail_enseignant, name='detail_enseignant'),
    path('enseignants/<int:pk>/modifier/', views.modifier_enseignant, name='modifier_enseignant'),
    path('enseignants/<int:pk>/affecter/', views.affecter_matiere, name='affecter_matiere'),

    # Paramètres, divisions, cycles, modèles
    path('parametres/', views_parametres.parametres, name='parametres'),
    path('divisions/', views_divisions.liste_divisions, name='liste_divisions'),
    path('divisions/creer/', views_divisions.creer_division, name='creer_division'),
    path('divisions/<int:pk>/modifier/', views_divisions.modifier_division, name='modifier_division'),
    path('cycles/', views_cycles.liste_cycles, name='liste_cycles'),
    path('cycles/<int:pk>/', views_cycles.detail_cycle, name='detail_cycle'),
    path('modeles/', views_modeles.liste_modeles, name='liste_modeles'),
    path('modeles/creer/', views_modeles.creer_modele, name='creer_modele'),
    path('modeles/creer/<str:type_doc>/', views_modeles.creer_modele, name='creer_modele_type'),
    path('modeles/<int:pk>/modifier/', views_modeles.modifier_modele, name='modifier_modele'),
    path('modeles/<int:pk>/activer/', views_modeles.activer_modele, name='activer_modele'),
    path('modeles/<int:pk>/apercu/', views_modeles.apercu_modele, name='apercu_modele'),
]
