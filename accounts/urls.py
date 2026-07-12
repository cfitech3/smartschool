from django.urls import path
from . import views, views_comptes
urlpatterns = [
    path('login/', views.login_view, name='login'),
    path('portail/<str:code_etab>/', views.login_portail, name='login_portail'),
    path('logout/', views.logout_view, name='logout'),
    path('profil/', views.profil, name='profil'),
    path('utilisateurs/', views_comptes.liste_utilisateurs, name='liste_utilisateurs'),
    path('utilisateurs/acces/<int:eleve_pk>/', views_comptes.generer_acces_eleve, name='generer_acces_eleve'),
    path('utilisateurs/acces-classe/<int:classe_pk>/', views_comptes.generer_acces_classe, name='generer_acces_classe'),
]
