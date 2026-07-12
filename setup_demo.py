"""SmartSchool ERP — Donnees de demonstration completes (v1.6)"""
import os, sys, django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'smartschool.settings')
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
django.setup()

from accounts.models import User
from etablissements.models import Etablissement, AnneeScolaire, Niveau, Classe, Enseignant, AffectationMatiere, ParametreEtablissement, ModeleDocument
from eleves.models import Eleve, Tuteur, Inscription, Presence
from finances.models import TypeFrais, Paiement
from notes.models import Matiere, Periode, NotePeriode, EmploiDuTemps
from django.utils import timezone
import datetime, random
from decimal import Decimal

print("="*55); print("  SmartSchool ERP — Donnees de demonstration v1.6"); print("="*55)

print("\n[1/14] Nettoyage...")
EmploiDuTemps.objects.all().delete()
NotePeriode.objects.all().delete()
Paiement.objects.all().delete()
Presence.objects.all().delete()
AffectationMatiere.objects.all().delete()
Inscription.objects.all().delete()
Eleve.objects.all().delete()
Tuteur.objects.all().delete()
Enseignant.objects.all().delete()
Classe.objects.all().delete()
Niveau.objects.all().delete()
Matiere.objects.all().delete()
Periode.objects.all().delete()
TypeFrais.objects.all().delete()
ModeleDocument.objects.all().delete()
ParametreEtablissement.objects.all().delete()
AnneeScolaire.objects.all().delete()
Etablissement.objects.all().delete()
User.objects.filter(is_superuser=False).delete()
User.objects.filter(username='admin').delete()
print("   OK")

print("\n[2/14] Etablissement...")
etab = Etablissement.objects.create(
    nom="Ecole Fondamentale Babemba Traore", type='ecole', code='EFBT',
    adresse='Bamako, Commune III, Quartier Hippodrome', telephone='+223 20 22 33 44',
    email='contact@efbt.edu.ml', directeur='M. Mamadou Coulibaly',
    slogan="L'excellence au service de la jeunesse malienne",
    couleur_principale='#1565C0', couleur_secondaire='#0D47A1',
)
print(f"   {etab.nom}")

print("\n[3/14] Annee scolaire...")
annee = AnneeScolaire.objects.create(etablissement=etab, libelle='2024-2025',
    date_debut=datetime.date(2024,10,1), date_fin=datetime.date(2025,6,30), is_active=True)
print(f"   {annee.libelle}")

print("\n[2b/14] Cycles scolaires maliens...")
from etablissements.models import Cycle, SerieLycee, MatiereCycle, UEUniversite
Cycle.objects.filter(etablissement=etab).delete()

cycle_1er = Cycle.objects.create(
    etablissement=etab, type_cycle='premier_cycle', nom='1er Cycle Fondamental',
    mode_calcul='compo', note_passage=10, note_max=20,
    diplome_prepare='Certificat de Fin de 1er Cycle', ordre=1
)
cycle_2nd = Cycle.objects.create(
    etablissement=etab, type_cycle='second_cycle', nom='2ème Cycle Fondamental',
    mode_calcul='compo', note_passage=10, note_max=20,
    diplome_prepare='DEF (Diplôme d\'Études Fondamentales)', ordre=2
)
cycle_lycee = Cycle.objects.create(
    etablissement=etab, type_cycle='lycee', nom='Lycée',
    mode_calcul='direct', note_passage=10, note_max=20,
    diplome_prepare='Baccalauréat', ordre=3
)
cycle_univ = Cycle.objects.create(
    etablissement=etab, type_cycle='universite', nom='Université',
    mode_calcul='credit', note_passage=10, note_max=20,
    diplome_prepare='Licence / Master / Doctorat', ordre=4
)

# Séries du lycée malien
SerieLycee.objects.create(cycle=cycle_lycee, code='A',  nom='Lettres et Sciences Humaines', ordre=1)
SerieLycee.objects.create(cycle=cycle_lycee, code='B',  nom='Sciences Économiques et Sociales', ordre=2)
SerieLycee.objects.create(cycle=cycle_lycee, code='C',  nom='Mathématiques et Physique', ordre=3)
SerieLycee.objects.create(cycle=cycle_lycee, code='D',  nom='Sciences de la Nature et de la Vie', ordre=4)
SerieLycee.objects.create(cycle=cycle_lycee, code='T',  nom='Technique', ordre=5)
print(f"   4 cycles + 5 séries lycée créés")

print("\n[4/14] Periodes...")
p1 = Periode.objects.create(etablissement=etab, annee=annee, type='trimestre', numero=1,
    libelle='1er Trimestre', date_debut=datetime.date(2024,10,1), date_fin=datetime.date(2024,12,20), is_active=True)
p2 = Periode.objects.create(etablissement=etab, annee=annee, type='trimestre', numero=2,
    libelle='2eme Trimestre', date_debut=datetime.date(2025,1,6), date_fin=datetime.date(2025,3,28), is_active=False)
p3 = Periode.objects.create(etablissement=etab, annee=annee, type='trimestre', numero=3,
    libelle='3eme Trimestre', date_debut=datetime.date(2025,4,7), date_fin=datetime.date(2025,6,30), is_active=False)
print(f"   3 periodes")

print("\n[3b/14] Configuration cycles actifs + divisions...")
from etablissements.models import CycleActif, Division

# Cycles actifs pour cet établissement (fondamental complet = 1er + 2ème)
# On crée les cycles actifs APRÈS que les cycles ont été créés (étape 2b)
# Donc on les crée ici en cherchant les cycles déjà créés
# (sera complété après l'étape 2b - voir plus bas)
_div_placeholder = True  # signaler qu'on doit créer les divisions plus tard

print("\n[5/14] Comptes utilisateurs (avec Surveillant General)...")
superadmin = User.objects.create_superuser('admin','admin@smartschool.ml','admin123')
superadmin.role='super_admin'; superadmin.first_name='Super'; superadmin.last_name='Admin'; superadmin.save()

directeur = User.objects.create_user('directeur','directeur@efbt.ml','admin123')
directeur.role='admin'; directeur.first_name='Mamadou'; directeur.last_name='Coulibaly'; directeur.etablissement=etab; directeur.save()

comptable = User.objects.create_user('comptable','compta@efbt.ml','admin123')
comptable.role='comptable'; comptable.first_name='Fatoumata'; comptable.last_name='Diallo'; comptable.etablissement=etab; comptable.telephone='+223 76 11 22 33'; comptable.save()

surveillant = User.objects.create_user('surveillant','surveillant@efbt.ml','admin123')
surveillant.role='surveillant'; surveillant.first_name='Ibrahim'; surveillant.last_name='Sangare'; surveillant.etablissement=etab; surveillant.telephone='+223 77 22 33 44'; surveillant.save()

# Compte parent (rattaché au premier tuteur)
# On le crée APRES les eleves pour pouvoir le rattacher

# Compte secrétariat
secretaire = User.objects.create_user('secretaire', 'secretaire@efbt.ml', 'admin123')
secretaire.role = 'secretariat'; secretaire.first_name = 'Aminata'; secretaire.last_name = 'Kone'
secretaire.etablissement = etab; secretaire.save()
print("   admin / directeur / comptable / surveillant / secretaire — mdp: admin123")
print("   + 1 compte parent + 1 compte eleve (crees apres les eleves)")

print("\n[6/14] Niveaux et classes...")
niveaux_data = [
    ('1ere Annee',1,'premier_cycle'),('2eme Annee',2,'premier_cycle'),
    ('3eme Annee',3,'premier_cycle'),('4eme Annee',4,'premier_cycle'),
    ('5eme Annee',5,'premier_cycle'),('6eme Annee',6,'premier_cycle'),
    ('7eme Annee',7,'second_cycle'),('8eme Annee',8,'second_cycle'),
    ('9eme Annee',9,'second_cycle'),
    ('Licence 1',10,'universite'),('Licence 2',11,'universite'),('Licence 3',12,'universite'),
    ('Master 1',13,'universite'),('Master 2',14,'universite'),
    ('Doctorat 1',15,'universite'),
]
cycles_map = {c.type_cycle:c for c in Cycle.objects.filter(etablissement=etab)}
niveaux = {nom: Niveau.objects.create(
    etablissement=etab, nom=nom, ordre=ordre,
    cycle=cycles_map.get(type_cycle)
) for nom,ordre,type_cycle in niveaux_data}
classes_data = [('1A','1ere Annee',42),('1B','1ere Annee',40),('2A','2eme Annee',38),('2B','2eme Annee',36),('3A','3eme Annee',41),('3B','3eme Annee',39),('6A','6eme Annee',35),('9A','9eme Annee',33)]
classes = {nom: Classe.objects.create(etablissement=etab, annee=annee, niveau=niveaux[niv], nom=nom, capacite_max=cap) for nom,niv,cap in classes_data}
print(f"   {len(niveaux)} niveaux, {len(classes)} classes")

print("\n[7/14] Matieres (avec Conduite pour le surveillant)...")
matieres_data = [
    ('Redaction','RED',3,False),('Dictee/Questions','DIC',2,False),('Mathematiques','MATH',3,False),
    ('Physique/Chimie','PC',3,False),('Anglais','ANG',2,False),('Biologie','BIO',2,False),
    ('Histoire/Geo','HG',2,False),('ECM','ECM',1,False),('EPS','EPS',1,False),
    ('Dessin','DES',1,False),('Lecture','LEC',1,False),('Recitation','REC',1,False),
    ('Conduite','CON',1,True),
]
matieres = {}
for nom,code,coef,is_c in matieres_data:
    matieres[nom] = Matiere.objects.create(etablissement=etab, nom=nom, code=code, coefficient=coef, is_conduite=is_c)
print(f"   {len(matieres)} matieres (dont Conduite geree par le surveillant)")

print("\n[7b/14] Matieres par cycle (config officielle Mali)...")
cycles_map = {c.type_cycle:c for c in Cycle.objects.filter(etablissement=etab)}
from etablissements.models import MatiereCycle

# 1ER CYCLE : Lecture, Récitation, Rédaction, Dictée, Calcul, Sciences, Hist/Géo, ECM, EPS, Dessin, Conduite
mats_1er = [
    ('Redaction',3),('Dictee/Questions',2),('Mathematiques',3),
    ('Lecture',2),('Recitation',1),('Biologie',1),
    ('Histoire/Geo',2),('ECM',1),('EPS',1),('Dessin',1),('Conduite',1),
]
for nom,coef in mats_1er:
    if nom in matieres:
        MatiereCycle.objects.get_or_create(
            cycle=cycles_map['premier_cycle'], matiere=matieres[nom],
            defaults={'coefficient':coef, 'est_obligatoire':True,
                      'ordre':mats_1er.index((nom,coef))+1}
        )

# 2EME CYCLE : Rédaction, Dictée, Maths, PC, SVT, Anglais, HG, ECM, EPS, Dessin, Conduite
mats_2nd = [
    ('Redaction',3),('Dictee/Questions',2),('Mathematiques',3),
    ('Physique/Chimie',3),('Biologie',2),('Anglais',2),
    ('Histoire/Geo',2),('ECM',1),('EPS',1),('Dessin',1),('Conduite',1),
]
for nom,coef in mats_2nd:
    if nom in matieres:
        MatiereCycle.objects.get_or_create(
            cycle=cycles_map['second_cycle'], matiere=matieres[nom],
            defaults={'coefficient':coef, 'est_obligatoire':True,
                      'ordre':mats_2nd.index((nom,coef))+1}
        )

print(f"   Config 1er cycle: {len(mats_1er)} matieres")

print("\n[7c/14] Cycles actifs + Divisions de l'etablissement...")
from etablissements.models import CycleActif, Division

# Nettoyer
CycleActif.objects.filter(etablissement=etab).delete()
Division.objects.filter(etablissement=etab).delete()

# Activer 1er + 2ème cycle (établissement fondamental)
for i, tc in enumerate(['premier_cycle','second_cycle'],1):
    c_obj = cycles_map.get(tc)
    if c_obj:
        CycleActif.objects.create(etablissement=etab, cycle=c_obj, ordre=i)

# Créer 2 divisions : Fondamental 1er cycle + Fondamental 2ème cycle
div_1er = Division.objects.create(
    etablissement=etab,
    nom="1er Cycle Fondamental",
    code="FOND1",
    directeur_nom="M. Mamadou Coulibaly",
    directeur_user=directeur,
    entete_ligne1="Ecole Fondamentale Babemba Traore",
    entete_ligne2="1er Cycle — Bamako, Mali",
    couleur_principale="#1565C0",
    ordre=1
)
div_1er.cycles.set([cycles_map['premier_cycle']])

div_2nd = Division.objects.create(
    etablissement=etab,
    nom="2ème Cycle Fondamental",
    code="FOND2",
    directeur_nom="M. Mamadou Coulibaly",
    directeur_user=directeur,
    entete_ligne1="Ecole Fondamentale Babemba Traore",
    entete_ligne2="2ème Cycle — Bamako, Mali",
    couleur_principale="#0D47A1",
    ordre=2
)
div_2nd.cycles.set([cycles_map['second_cycle']])

# NOTE: Pour la démo on garde 1er + 2ème cycle fondamental
# L'université est disponible mais non activée par défaut
# (établissement = école fondamentale)
print(f"   2 cycles actifs (1er + 2ème cycle fondamental)")
print(f"   [Université disponible — à activer dans /etablissements/divisions/]")
print(f"   2 divisions créées : {div_1er.nom} | {div_2nd.nom}")
print(f"   Config 2eme cycle: {len(mats_2nd)} matieres")

# UNIVERSITÉ : UEs Licence 1 Informatique (exemple)
from etablissements.models import UEUniversite
UEUniversite.objects.filter(cycle=cycles_map['universite']).delete()
ues_l1 = [
    # Semestre 1
    ('INFO-101','Algorithmique et Programmation',4,1,2),
    ('MATH-101','Mathématiques Générales',4,1,2),
    ('PHIS-101','Physique Générale',3,1,1),
    ('ANG-101','Anglais Technique',2,1,1),
    ('INFO-102','Architecture des Ordinateurs',3,1,1),
    # Semestre 2
    ('INFO-201','Structures de Données',4,2,2),
    ('MATH-201','Algèbre Linéaire',4,2,2),
    ('INFO-202','Systemes d Exploitation',3,2,1),
    ('ANG-201','Communication Professionnelle',2,2,1),
    ('INFO-203','Base de Données',3,2,1),
]
for code,nom,credits,semestre,coef in ues_l1:
    UEUniversite.objects.create(
        cycle=cycles_map['universite'],code=code,nom=nom,
        credits=credits,semestre=semestre,coefficient=coef,est_obligatoire=True
    )
print(f"   Config université: {len(ues_l1)} UEs (Licence 1 Informatique, S1+S2)")

print("\n[8/14] Enseignants...")
enseignants_data = [
    ('Diallo','Boubacar','bdiallo','Mathematiques','Master Maths',180000),
    ('Keita','Mariam','mkeita','Francais-Lettres','Licence Lettres',155000),
    ('Sangare','Ousmane','osangare','Sciences','Master Sciences',165000),
    ('Traore','Seydou','straore','Histoire-Geo','Licence Histoire',145000),
    ('Camara','Aminata','acamara','Anglais','Master Anglais',158000),
    ('Coulibaly','Bourama','bcoulibaly','EPS','STAPS',140000),
]
ens_objects = []
for nom,prenom,username,spec,diplome,salaire in enseignants_data:
    u = User.objects.create_user(username, f'{username}@efbt.ml', 'admin123')
    u.first_name=prenom; u.last_name=nom; u.role='enseignant'; u.etablissement=etab; u.save()
    ens = Enseignant.objects.create(user=u, etablissement=etab, specialite=spec, diplome=diplome,
        date_embauche=datetime.date(2020,9,1), salaire=salaire, statut='actif')
    ens_objects.append(ens)
print(f"   {len(ens_objects)} enseignants")

print("\n[9/14] Affectations matiere/classe (necessaire pour saisie de notes)...")
# Diallo -> Maths sur toutes les classes
# Keita -> Redaction + Dictee
# Sangare -> Physique/Chimie + Biologie
# Traore -> Histoire/Geo
# Camara -> Anglais
# Coulibaly -> EPS
affectations_map = [
    (ens_objects[0], ['Mathematiques']),
    (ens_objects[1], ['Redaction','Dictee/Questions','Lecture','Recitation']),
    (ens_objects[2], ['Physique/Chimie','Biologie']),
    (ens_objects[3], ['Histoire/Geo','ECM']),
    (ens_objects[4], ['Anglais']),
    (ens_objects[5], ['EPS','Dessin']),
]
nb_aff = 0
for ens, mats in affectations_map:
    for cl in classes.values():
        for mat_nom in mats:
            AffectationMatiere.objects.create(enseignant=ens, classe=cl, matiere=matieres[mat_nom], annee=annee, heures_semaine=random.choice([2,3,4]))
            nb_aff += 1
print(f"   {nb_aff} affectations creees")

print("\n[10/14] Types de frais...")
frais_data = [("Frais d'inscription",25000,True),('Scolarite mensuelle',15000,True),('Cantine mensuelle',8000,False),('Transport mensuel',6000,False),('Frais examen',10000,True),('Tenue scolaire',5000,False)]
types_frais = {nom: TypeFrais.objects.create(etablissement=etab, annee=annee, nom=nom, montant_defaut=m, is_obligatoire=o) for nom,m,o in frais_data}
print(f"   {len(types_frais)} types de frais")

print("\n[11/14] Eleves + tuteurs + inscriptions...")
eleves_data = [
    ('Traore','Awa','F','2014-03-14','1A','Traore Moussa','+223 76 11 22 33'),('Coulibaly','Ibrahim','M','2014-07-22','1A','Coulibaly Seydou','+223 70 22 33 44'),
    ('Diallo','Kadiatou','F','2014-11-05','1A','Diallo Amadou','+223 65 33 44 55'),('Kone','Lassana','M','2014-08-18','1A','Kone Bakary','+223 79 44 55 66'),
    ('Bah','Mariama','F','2014-01-30','1B','Bah Ibrahima','+223 72 55 66 77'),('Camara','Seydou','M','2014-05-12','1B','Camara Fanta','+223 66 66 77 88'),
    ('Sidibe','Aminata','F','2014-09-25','1B','Sidibe Modibo','+223 75 77 88 99'),('Dembele','Oumar','M','2014-02-08','1B','Dembele Issa','+223 78 88 99 00'),
    ('Toure','Aissata','F','2013-06-17','2A','Toure Salif','+223 71 99 00 11'),('Sangare','Bourama','M','2013-11-03','2A','Sangare Hawa','+223 74 00 11 22'),
    ('Keita','Fatoumata','F','2013-04-22','2A','Keita Mamadou','+223 77 11 22 33'),('Doumbia','Souleymane','M','2013-09-15','2A','Doumbia Rokia','+223 73 22 33 44'),
    ('Sissoko','Mariam','F','2013-07-08','2B','Sissoko Drissa','+223 76 33 44 55'),('Bagayoko','Ousmane','M','2013-12-19','2B','Bagayoko Sali','+223 70 44 55 66'),
    ('Coulibaly','Hawa','F','2013-03-27','2B','Coulibaly Bakari','+223 65 55 66 77'),('Fofana','Adama','M','2013-08-11','3A','Fofana Tenin','+223 79 66 77 88'),
    ('Diarra','Djeneba','F','2012-05-23','3A','Diarra Moussa','+223 72 77 88 99'),('Konate','Cheick','M','2012-10-14','3A','Konate Fatoumata','+223 66 88 99 00'),
    ('Ndiaye','Aminata','F','2012-02-06','3B','Ndiaye Oumar','+223 75 99 00 11'),('Thiam','Mamadou','M','2012-07-30','3B','Thiam Rokiatou','+223 78 00 11 22'),
    ('Cisse','Rokia','F','2011-04-18','6A','Cisse Boubacar','+223 71 11 22 33'),('Sylla','Aboubacar','M','2011-09-07','6A','Sylla Mariam','+223 74 22 33 44'),
    ('Barry','Kadidiatou','F','2010-12-25','9A','Barry Ibrahima','+223 77 33 44 55'),('Harouna','Dagnon','M','2010-06-13','9A','Harouna Bakary','+223 73 44 55 66'),
    ('Maiga','Salimata','F','2010-03-20','9A','Maiga Ousmane','+223 76 55 66 77'),
]
eleve_objects = []
for nom,prenom,sexe,dob,cl_nom,tut_nom,tut_tel in eleves_data:
    tut_parts = tut_nom.split(' ',1)
    tuteur = Tuteur.objects.create(etablissement=etab, nom=tut_parts[0], prenom=tut_parts[1] if len(tut_parts)>1 else '',
        lien=random.choice(['pere','mere','tuteur']), telephone=tut_tel)
    eleve = Eleve.objects.create(etablissement=etab, nom=nom, prenom=prenom, sexe=sexe,
        date_naissance=datetime.date.fromisoformat(dob), lieu_naissance=random.choice(['Bamako','Mopti','Segou','Kayes','Sikasso']), tuteur=tuteur)
    Inscription.objects.create(eleve=eleve, classe=classes[cl_nom], annee=annee, statut='actif')
    eleve_objects.append(eleve)
print(f"   {len(eleve_objects)} eleves inscrits")

# Créer compte parent rattaché au tuteur du premier élève
premier_eleve = eleve_objects[0]
if premier_eleve.tuteur:
    parent_user = User.objects.create_user('parent1', 'parent1@efbt.ml', 'parent123')
    parent_user.role = 'parent'
    parent_user.first_name = premier_eleve.tuteur.prenom
    parent_user.last_name = premier_eleve.tuteur.nom
    parent_user.etablissement = etab
    parent_user.save()
    premier_eleve.tuteur.user_compte = parent_user
    premier_eleve.tuteur.save()
    print(f"   Compte parent cree : parent1 / parent123 → parent de {premier_eleve.nom_complet}")

# Créer compte eleve rattaché au dernier élève (Harouna Dagnon 9A)
eleve_harouna = next((e for e in eleve_objects if e.prenom == 'Dagnon'), eleve_objects[-1])
eleve_user = User.objects.create_user('eleve1', 'eleve1@efbt.ml', 'eleve123')
eleve_user.role = 'eleve'
eleve_user.first_name = eleve_harouna.prenom
eleve_user.last_name = eleve_harouna.nom
eleve_user.etablissement = etab
eleve_user.save()
eleve_harouna.user_compte = eleve_user
eleve_harouna.save()
print(f"   Compte eleve cree  : eleve1 / eleve123 → {eleve_harouna.nom_complet}")

print("\n[12/14] Emploi du temps (creneaux pour toutes les classes)...")
jours = ['lundi','mardi','mercredi','jeudi','vendredi']
nb_edt = 0
for cl_nom, classe_obj in classes.items():
    horaires = [('08:00','10:00'),('10:00','12:00'),('14:00','16:00')]
    mats_dispo = list(matieres.values())
    mats_dispo = [m for m in mats_dispo if not m.is_conduite]
    for j in jours[:4]:
        for hd, hf in horaires[:2]:
            mat = random.choice(mats_dispo)
            ens = random.choice(ens_objects)
            EmploiDuTemps.objects.create(etablissement=etab, classe=classe_obj, matiere=mat, enseignant=ens.user,
                jour=j, heure_debut=hd, heure_fin=hf, salle=f"Salle {random.randint(1,8):02d}")
            nb_edt += 1
print(f"   {nb_edt} creneaux d'emploi du temps crees")

print("\n[13/14] Paiements, notes (incluant Conduite), presences...")
modes = ['especes','especes','especes','mobile_money']
nb_paiements = 0
today = timezone.now()
for eleve in eleve_objects:
    Paiement.objects.create(etablissement=etab, eleve=eleve, annee=annee, type_frais=types_frais["Frais d'inscription"],
        montant=25000, mode_paiement=random.choice(modes), statut='valide',
        date_paiement=today - datetime.timedelta(days=random.randint(60,90)), encaisse_par=comptable,
        reference=f"PAY-INSC-{eleve.matricule[-4:]}")
    nb_paiements += 1
    for mois_delta in [80,50,20,-10,-40]:
        if random.random() > 0.15:
            Paiement.objects.create(etablissement=etab, eleve=eleve, annee=annee, type_frais=types_frais['Scolarite mensuelle'],
                montant=15000, mode_paiement=random.choice(modes), statut='valide',
                date_paiement=today - datetime.timedelta(days=abs(mois_delta)+random.randint(0,5)), encaisse_par=comptable)
            nb_paiements += 1
print(f"   {nb_paiements} paiements")

matieres_list = list(matieres.values())
nb_notes = 0
for classe_nom, classe_obj in classes.items():
    inscriptions = classe_obj.inscriptions.filter(is_active=True).select_related('eleve')
    for insc in inscriptions:
        for mat in matieres_list:
            if mat.is_conduite:
                # Note de conduite saisie par le surveillant
                nb_absences_simulees = random.choice([0,0,0,1,1,2,3,4])
                nb_retards_simulees = random.choice([0,0,1,2])
                score = max(0, round(20 - (nb_absences_simulees*1.5) - (nb_retards_simulees*0.5), 1))
                NotePeriode.objects.create(eleve=insc.eleve, matiere=mat, classe=classe_obj, periode=p1,
                    note_conduite=Decimal(str(score)), saisi_par=surveillant)
            else:
                base = random.uniform(7,17)
                mc = round(min(20,max(0,base+random.uniform(-2,2))),2)
                mn = round(min(40,max(0,mc*2+random.uniform(-4,4))),2)
                NotePeriode.objects.create(eleve=insc.eleve, matiere=mat, classe=classe_obj, periode=p1,
                    moy_classe=Decimal(str(mc)), moy_compo=Decimal(str(mn)), note_max_classe=20, note_max_compo=40, saisi_par=directeur)
            nb_notes += 1
print(f"   {nb_notes} notes creees (incluant Conduite pour {len(eleve_objects)} eleves)")

nb_presences = 0
for delta in range(7):
    date_p = today.date() - datetime.timedelta(days=delta)
    if date_p.weekday() < 5:
        for classe_obj in list(classes.values())[:6]:
            for insc in classe_obj.inscriptions.filter(is_active=True):
                statut = random.choices(['present','absent','retard','justifie'], weights=[82,9,6,3])[0]
                Presence.objects.get_or_create(eleve=insc.eleve, classe=classe_obj, date=date_p,
                    defaults={'statut':statut,'enregistre_par':directeur if statut!='absent' else surveillant})
                nb_presences += 1
print(f"   {nb_presences} presences enregistrees (7 derniers jours)")

print("\n[14/14] Parametres et TOUS les modeles de documents...")
ParametreEtablissement.objects.create(etablissement=etab, devise='FCFA', type_periode='trimestre',
    note_passage=10, note_max=20, entete_bulletin="Republique du Mali\nMinistere de l'Education Nationale",
    pied_bulletin="Ce bulletin est certifie conforme par la direction.")

ModeleDocument.objects.create(etablissement=etab, type_document='bulletin', nom='Bulletin Standard Mali', is_actif=True,
    ligne1_gauche=etab.nom, ligne2_gauche='Bamako — Mali', ligne1_droite='Republique du Mali', ligne2_droite='Un Peuple — Un But — Une Foi',
    titre_document='BULLETIN DE NOTES', couleur_titre_bg='#555555', couleur_titre_texte='#ffffff',
    label_signature_gauche='Le Directeur', label_signature_droite='Le Parent ou Tuteur',
    texte_pied_page='Ce bulletin est certifie conforme.', afficher_rang=True, afficher_moy_premier=True,
    note_max_classe=20, note_max_compo=40)

ModeleDocument.objects.create(etablissement=etab, type_document='recu', nom='Recu Standard', is_actif=True,
    titre_document='RECU DE PAIEMENT', couleur_titre_bg='#1565C0', format_recu='A5', couleur_accent_recu='#FF6F00')

ModeleDocument.objects.create(etablissement=etab, type_document='certificat', nom='Certificat de Scolarite', is_actif=True,
    ligne1_gauche='Republique du Mali', ligne2_gauche=etab.nom, ligne1_droite='Un Peuple — Un But — Une Foi',
    titre_document='CERTIFICAT DE SCOLARITE', couleur_titre_bg='#1565C0')

ModeleDocument.objects.create(etablissement=etab, type_document='carte_scolaire', nom='Carte Scolaire', is_actif=True,
    titre_document='CARTE SCOLAIRE', couleur_titre_bg='#0D47A1', couleur_titre_texte='#ffffff')

ModeleDocument.objects.create(etablissement=etab, type_document='attestation', nom='Attestation de Frequentation', is_actif=True,
    ligne1_gauche='Republique du Mali', ligne2_gauche=etab.nom, ligne1_droite='Un Peuple — Un But — Une Foi',
    titre_document='ATTESTATION DE FREQUENTATION', couleur_titre_bg='#1565C0', couleur_bordure='#333333',
    label_signature_gauche='Le Directeur', texte_pied_page='Delivre pour servir et valoir ce que de droit.')

ModeleDocument.objects.create(etablissement=etab, type_document='releve_notes', nom='Releve de Notes', is_actif=True,
    ligne1_gauche=etab.nom, ligne1_droite='Republique du Mali', titre_document='RELEVE DE NOTES',
    couleur_titre_bg='#2E7D32', label_signature_gauche='Le Directeur')

print("   6 modeles de documents crees (tous types)")

print("\n"+"="*55); print("  INSTALLATION TERMINEE !"); print("="*55)
print(f"\n  Etablissement : {etab.nom}")
print(f"  Annee active  : {annee.libelle}")
print(f"  Classes       : {Classe.objects.count()}")
print(f"  Eleves        : {Eleve.objects.count()}")
print(f"  Enseignants   : {Enseignant.objects.count()}")
print(f"  Affectations  : {AffectationMatiere.objects.count()}")
print(f"  Emploi du temps: {EmploiDuTemps.objects.count()} creneaux")
print(f"  Paiements     : {Paiement.objects.count()}")
print(f"  Notes         : {NotePeriode.objects.count()}")
print(f"  Presences     : {Presence.objects.count()}")
print(f"  Matieres      : {Matiere.objects.count()} (dont Conduite)")
print(f"  Modeles docs  : {ModeleDocument.objects.count()}")
print("\n  COMPTES DE CONNEXION :")
print("  +--------------+-----------+--------------------------+")
print("  | Identifiant  | Mot passe | Role                     |")
print("  +--------------+-----------+--------------------------+")
print("  | admin        | admin123  | Super Administrateur     |")
print("  | directeur    | admin123  | Admin etablissement      |")
print("  | comptable    | admin123  | Comptable                |")
print("  | surveillant  | admin123  | Surveillant General      |")
print("  | bdiallo      | admin123  | Enseignant (Maths)       |")
print("  | mkeita       | admin123  | Enseignant (Francais)    |")
print("  | parent1      | parent123 | Parent (Traore Awa)      |")
print("  | eleve1       | eleve123  | Eleve (Harouna/Dagnon)   |")
print("  +--------------+-----------+--------------------------+")
print("\n  Ouvrir : http://127.0.0.1:8000")
print("="*55)
