from django.urls import path
from . import views, views_export, views_rapports, views_tranches, views_impayes
urlpatterns = [
    path('', views.liste_paiements, name='liste_paiements'),
    path('ajouter/', views.enregistrer_paiement, name='enregistrer_paiement'),
    path('reduction/', views.ajouter_reduction, name='ajouter_reduction'),
    path('recu/<int:pk>/', views.recu_paiement, name='recu_paiement'),
    path('annuler/<int:pk>/', views.annuler_paiement, name='annuler_paiement'),
    path('rapport/', views.rapport_financier, name='rapport_financier'),
    path('eleve/<int:pk>/', views.situation_eleve, name='situation_eleve'),
    path('api/frais/', views.get_montant_frais, name='api_montant_frais'),
    path('api/frais/<int:pk>/periodes/', views.api_periodes_frais, name='api_periodes_frais'),
    path('export/', views_export.export_excel_finances, name='export_excel_finances'),
    path('rapports/retards/', views_rapports.rapport_retards, name='rapport_retards'),
    path('rapports/bilan/', views_rapports.rapport_bilan_annuel, name='rapport_bilan_annuel'),
    path('impayes/', views_impayes.liste_impayes, name='liste_impayes'),
    path('impayes/export/', views_impayes.export_impayes_excel, name='export_impayes_excel'),
    path('tranches/<int:type_frais_pk>/generer/', views_tranches.generer_echeances, name='generer_echeances'),
    path('tranches/<int:type_frais_pk>/', views_tranches.tableau_tranches, name='tableau_tranches'),
    path('tranches/payer/<int:echeance_pk>/', views_tranches.payer_tranche, name='payer_tranche'),
    path('tranches/eleve/<int:eleve_pk>/', views_tranches.situation_tranches_eleve, name='situation_tranches_eleve'),
]