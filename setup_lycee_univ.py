import os, sys, django, random, datetime
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'smartschool.settings')
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
django.setup()

from accounts.models import User
from etablissements.models import (
    Etablissement, AnneeScolaire, Cycle, Niveau, Classe, CycleActif, Division,
    MatiereCycle, ParametreEtablissement, SerieLycee, UEUniversite
)
from eleves.models import Eleve, Inscription
from notes.models import Matiere, Periode

print("="*50)
print("Création des données de test : Lycée et Université")
print("="*50)

# ==========================================
# 1. LYCÉE
# ==========================================
print("\nCréation du Lycée...")
lycee, _ = Etablissement.objects.get_or_create(
    code='LYC-EXC',
    defaults={
        'nom': "Lycée d'Excellence", 
        'type': 'lycee',
        'adresse': 'Bamako ACI 2000', 
        'telephone': '20 00 00 01'
    }
)

ParametreEtablissement.objects.get_or_create(etablissement=lycee)

annee_lyc, _ = AnneeScolaire.objects.get_or_create(
    etablissement=lycee, libelle='2024-2025',
    defaults={'date_debut': datetime.date(2024, 10, 1), 'date_fin': datetime.date(2025, 6, 30), 'is_active': True}
)
if annee_lyc.is_active:
    AnneeScolaire.objects.filter(etablissement=lycee).exclude(pk=annee_lyc.pk).update(is_active=False)

cycle_lyc, _ = Cycle.objects.get_or_create(
    etablissement=lycee, type_cycle='lycee',
    defaults={'nom': 'Lycée', 'mode_calcul': 'compo', 'note_max': 20, 'diplome_prepare': 'Baccalauréat'}
)
CycleActif.objects.get_or_create(etablissement=lycee, cycle=cycle_lyc, defaults={'is_active': True})

niv_sec, _ = Niveau.objects.get_or_create(etablissement=lycee, nom='Seconde', defaults={'cycle': cycle_lyc, 'ordre': 10})
niv_prem, _ = Niveau.objects.get_or_create(etablissement=lycee, nom='Première', defaults={'cycle': cycle_lyc, 'ordre': 11})
niv_term, _ = Niveau.objects.get_or_create(etablissement=lycee, nom='Terminale', defaults={'cycle': cycle_lyc, 'ordre': 12})

classe_sec, _ = Classe.objects.get_or_create(etablissement=lycee, annee=annee_lyc, nom='10ème Commune A', defaults={'niveau': niv_sec})
classe_prem, _ = Classe.objects.get_or_create(etablissement=lycee, annee=annee_lyc, nom='11ème Lettres', defaults={'niveau': niv_prem})

# Matières Lycée
mat_math, _ = Matiere.objects.get_or_create(etablissement=lycee, nom='Mathématiques', defaults={'code': 'MATH'})
mat_phys, _ = Matiere.objects.get_or_create(etablissement=lycee, nom='Physique-Chimie', defaults={'code': 'PC'})

# ==========================================
# 2. UNIVERSITÉ
# ==========================================
print("Création de l'Université...")
univ, _ = Etablissement.objects.get_or_create(
    code='UNIV-SCI',
    defaults={
        'nom': "Université des Sciences", 
        'type': 'universite',
        'adresse': 'Colline de Badalabougou', 
        'telephone': '20 00 00 02'
    }
)

ParametreEtablissement.objects.get_or_create(etablissement=univ, defaults={'type_periode': 'semestre'})

annee_univ, _ = AnneeScolaire.objects.get_or_create(
    etablissement=univ, libelle='2024-2025',
    defaults={'date_debut': datetime.date(2024, 10, 1), 'date_fin': datetime.date(2025, 6, 30), 'is_active': True}
)
if annee_univ.is_active:
    AnneeScolaire.objects.filter(etablissement=univ).exclude(pk=annee_univ.pk).update(is_active=False)

cycle_univ, _ = Cycle.objects.get_or_create(
    etablissement=univ, type_cycle='universite',
    defaults={'nom': 'Licence', 'mode_calcul': 'credit', 'note_max': 20, 'diplome_prepare': 'Licence'}
)
CycleActif.objects.get_or_create(etablissement=univ, cycle=cycle_univ, defaults={'is_active': True})

niv_l1, _ = Niveau.objects.get_or_create(etablissement=univ, nom='Licence 1', defaults={'cycle': cycle_univ, 'ordre': 1})
niv_l2, _ = Niveau.objects.get_or_create(etablissement=univ, nom='Licence 2', defaults={'cycle': cycle_univ, 'ordre': 2})

classe_l1, _ = Classe.objects.get_or_create(etablissement=univ, annee=annee_univ, nom='L1 Informatique', defaults={'niveau': niv_l1})
classe_l2, _ = Classe.objects.get_or_create(etablissement=univ, annee=annee_univ, nom='L2 Informatique', defaults={'niveau': niv_l2})

# ==========================================
# 3. DIRECTEURS
# ==========================================
print("Création des directeurs...")
dir_lycee, created = User.objects.get_or_create(
    username='dir_lycee',
    defaults={'role': 'admin', 'etablissement': lycee, 'first_name': 'Directeur', 'last_name': 'Lycée'}
)
if created:
    dir_lycee.set_password('passer123')
    dir_lycee.save()

dir_univ, created = User.objects.get_or_create(
    username='dir_univ',
    defaults={'role': 'admin', 'etablissement': univ, 'first_name': 'Doyen', 'last_name': 'Université'}
)
if created:
    dir_univ.set_password('passer123')
    dir_univ.save()

print("\nOpération terminée avec succès ! ✅")
print("-" * 40)
print("COMPTES CRÉÉS :")
print("- Directeur Lycée      : dir_lycee / passer123")
print("- Doyen Université     : dir_univ / passer123")
print("-" * 40)
