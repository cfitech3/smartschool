import os, sys, django, random, datetime
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'smartschool.settings')
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
django.setup()

from etablissements.models import Etablissement, Classe
from eleves.models import Eleve, Tuteur, Inscription

print("Ajout des élèves pour le Lycée et l'Université...")

lycee = Etablissement.objects.filter(code='LYC-EXC').first()
univ = Etablissement.objects.filter(code='UNIV-SCI').first()

if lycee:
    tuteur_lycee, _ = Tuteur.objects.get_or_create(
        etablissement=lycee, nom="Traore", prenom="Moussa", telephone="70000001",
        profession="Commerçant"
    )
    
    classes_lycee = list(Classe.objects.filter(etablissement=lycee))
    if classes_lycee:
        for i in range(1, 11):
            eleve = Eleve.objects.create(
                etablissement=lycee, matricule=f"LYC2024-{i:03d}",
                nom="Diallo", prenom=f"EleveLycée {i}", sexe=random.choice(["M", "F"]),
                date_naissance=datetime.date(2008, 5, 10),
                lieu_naissance="Bamako", tuteur=tuteur_lycee
            )
            classe = random.choice(classes_lycee)
            Inscription.objects.create(
                eleve=eleve, classe=classe, annee=classe.annee,
                date_inscription=datetime.date.today(), is_active=True
            )
        print("10 élèves ajoutés au Lycée.")

if univ:
    tuteur_univ, _ = Tuteur.objects.get_or_create(
        etablissement=univ, nom="Sidibe", prenom="Oumar", telephone="70000002",
        profession="Fonctionnaire"
    )
    
    classes_univ = list(Classe.objects.filter(etablissement=univ))
    if classes_univ:
        for i in range(1, 11):
            eleve = Eleve.objects.create(
                etablissement=univ, matricule=f"UNI2024-{i:03d}",
                nom="Keita", prenom=f"EtudiantUniv {i}", sexe=random.choice(["M", "F"]),
                date_naissance=datetime.date(2003, 2, 20),
                lieu_naissance="Ségou", tuteur=tuteur_univ
            )
            classe = random.choice(classes_univ)
            Inscription.objects.create(
                eleve=eleve, classe=classe, annee=classe.annee,
                date_inscription=datetime.date.today(), is_active=True
            )
        print("10 étudiants ajoutés à l'Université.")

print("Opération terminée !")
