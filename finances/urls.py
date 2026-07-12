from django.urls import path
from . import views
urlpatterns = [
    path('', views.liste_paiements, name='liste_paiements'),
    path('ajouter/', views.enregistrer_paiement, name='enregistrer_paiement'),
    path('reduction/', views.ajouter_reduction, name='ajouter_reduction'),
    path('recu/<int:pk>/', views.recu_paiement, name='recu_paiement'),
    path('annuler/<int:pk>/', views.annuler_paiement, name='annuler_paiement'),
    path('rapport/', views.rapport_financier, name='rapport_financier'),
    path('eleve/<int:pk>/', views.situation_eleve, name='situation_eleve'),
    path('api/frais/', views.get_montant_frais, name='api_montant_frais'),
]
