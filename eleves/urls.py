from django.urls import path
from . import views, views_presences, views_modifier

urlpatterns = [
    # Elèves
    path('', views.liste_eleves, name='liste_eleves'),
    path('ajouter/', views.ajouter_eleve, name='ajouter_eleve'),
    path('<int:pk>/', views.detail_eleve, name='detail_eleve'),
    path('<int:pk>/modifier/', views_modifier.modifier_eleve_complet, name='modifier_eleve'),
    path('<int:pk>/supprimer/', views.supprimer_eleve, name='supprimer_eleve'),
    # Classes
    path('classes/', views.liste_classes, name='liste_classes'),
    path('classes/ajouter/', views.ajouter_classe, name='ajouter_classe'),
    path('classes/<int:pk>/', views.detail_classe, name='detail_classe'),
    path('classes/<int:pk>/modifier/', views.modifier_classe, name='modifier_classe'),
    # Présences
    path('presences/', views_presences.appel_presences, name='appel_presences'),
    path('presences/historique/', views_presences.historique_presences, name='historique_presences'),
    path('presences/fiche/<int:eleve_pk>/', views_presences.fiche_absences_eleve, name='fiche_absences_eleve'),
]
