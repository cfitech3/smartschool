"""
SmartSchool ERP — Setup complet avec nouvelles règles 1er cycle
===============================================================
NOUVELLES RÈGLES :
  - 1er cycle fondamental : modèle Composition (pas NotePeriode)
  - Notes sur 10  (note_max = 10)
  - Coefficient = 1 pour toutes les matières du 1er cycle
  - 3 compositions par trimestre
  - Seuil de passage = 5/10

Usage : python setup_nouveau.py
"""
import os, sys, django, random, datetime
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'smartschool.settings')
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
django.setup()

from decimal import Decimal
from django.utils import timezone

from accounts.models import User
from etablissements.models import (
    Etablissement, AnneeScolaire, Niveau, Classe, Enseignant,
    AffectationMatiere, ParametreEtablissement, ModeleDocument,
    Cycle, SerieLycee, MatiereCycle, CycleActif, Division, UEUniversite
)
from eleves.models import Eleve, Tuteur, Inscription, Presence
from finances.models import TypeFrais, Paiement
from notes.models import Matiere, Periode, NotePeriode, EmploiDuTemps, Composition

random.seed(2025)

print("=" * 60)
print("  SmartSchool ERP — Setup avec règles 1er cycle /10")
print("=" * 60)

# ══════════════════════════════════════════════════════════════
# [1] NETTOYAGE COMPLET
# ══════════════════════════════════════════════════════════════
print("\n[1/14] Nettoyage complet de la base de données...")
Composition.objects.all().delete()
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
CycleActif.objects.all().delete()
Division.objects.all().delete()
MatiereCycle.objects.all().delete()
Cycle.objects.filter(etablissement__isnull=False).delete()
Etablissement.objects.all().delete()
User.objects.filter(is_superuser=False).delete()
User.objects.filter(username='admin').delete()
print("   ✅ Nettoyage terminé")

# ══════════════════════════════════════════════════════════════
# [2] ETABLISSEMENT
# ══════════════════════════════════════════════════════════════
print("\n[2/14] Établissement...")
etab = Etablissement.objects.create(
    nom="Ecole Fondamentale Babemba Traore", type='ecole', code='EFBT',
    adresse='Bamako, Commune III, Quartier Hippodrome', telephone='+223 20 22 33 44',
    email='contact@efbt.edu.ml', directeur='M. Mamadou Coulibaly',
    slogan="L'excellence au service de la jeunesse malienne",
    couleur_principale='#1565C0', couleur_secondaire='#0D47A1',
)
print(f"   ✅ {etab.nom}")

# ══════════════════════════════════════════════════════════════
# [3] ANNÉE SCOLAIRE
# ══════════════════════════════════════════════════════════════
print("\n[3/14] Année scolaire...")
annee = AnneeScolaire.objects.create(
    etablissement=etab, libelle='2024-2025',
    date_debut=datetime.date(2024, 10, 1),
    date_fin=datetime.date(2025, 6, 30),
    is_active=True
)
print(f"   ✅ {annee.libelle}")

# ══════════════════════════════════════════════════════════════
# [4] CYCLES — 1er cycle avec compositions /10, coef=1
# ══════════════════════════════════════════════════════════════
print("\n[4/14] Cycles scolaires (1er cycle : compo /10, coef=1, passage=5)...")

cycle_1er = Cycle.objects.create(
    etablissement=etab,
    type_cycle='premier_cycle',
    nom='1er Cycle Fondamental',
    mode_calcul='compo',
    note_passage=Decimal('5'),    # ← passage à 5/10
    note_max=Decimal('10'),       # ← sur 10
    nb_compositions_trimestre=3,  # ← 3 compositions par trimestre
    diplome_prepare='Certificat de Fin de 1er Cycle',
    ordre=1,
)

cycle_2nd = Cycle.objects.create(
    etablissement=etab,
    type_cycle='second_cycle',
    nom='2ème Cycle Fondamental',
    mode_calcul='compo',
    note_passage=Decimal('10'),
    note_max=Decimal('20'),
    nb_compositions_trimestre=1,
    diplome_prepare="DEF (Diplôme d'Études Fondamentales)",
    ordre=2,
)

cycle_lycee = Cycle.objects.create(
    etablissement=etab,
    type_cycle='lycee',
    nom='Lycée',
    mode_calcul='direct',
    note_passage=Decimal('10'),
    note_max=Decimal('20'),
    diplome_prepare='Baccalauréat',
    ordre=3,
)

cycle_univ = Cycle.objects.create(
    etablissement=etab,
    type_cycle='universite',
    nom='Université',
    mode_calcul='credit',
    note_passage=Decimal('10'),
    note_max=Decimal('20'),
    diplome_prepare='Licence / Master / Doctorat',
    ordre=4,
)

# Séries lycée malien
for code, nom, ordre in [('A','Lettres et Sciences Humaines',1),('B','Sciences Économiques et Sociales',2),
                          ('C','Mathématiques et Physique',3),('D','Sciences de la Nature et de la Vie',4),('T','Technique',5)]:
    SerieLycee.objects.create(cycle=cycle_lycee, code=code, nom=nom, ordre=ordre)

print(f"   ✅ 1er cycle : {cycle_1er.nb_compositions_trimestre} compositions/trimestre, "
      f"note_max={cycle_1er.note_max}, passage={cycle_1er.note_passage}")
print(f"   ✅ 2ème cycle, Lycée, Université créés")

# ══════════════════════════════════════════════════════════════
# [5] PÉRIODES
# ══════════════════════════════════════════════════════════════
print("\n[5/14] Périodes (trimestres)...")
p1 = Periode.objects.create(etablissement=etab, annee=annee, type='trimestre', numero=1,
    libelle='1er Trimestre', date_debut=datetime.date(2024,10,1), date_fin=datetime.date(2024,12,20), is_active=True)
p2 = Periode.objects.create(etablissement=etab, annee=annee, type='trimestre', numero=2,
    libelle='2ème Trimestre', date_debut=datetime.date(2025,1,6), date_fin=datetime.date(2025,3,28))
p3 = Periode.objects.create(etablissement=etab, annee=annee, type='trimestre', numero=3,
    libelle='3ème Trimestre', date_debut=datetime.date(2025,4,7), date_fin=datetime.date(2025,6,30))
periodes = [p1, p2, p3]
print(f"   ✅ 3 trimestres créés")

# ══════════════════════════════════════════════════════════════
# [6] COMPTES UTILISATEURS
# ══════════════════════════════════════════════════════════════
print("\n[6/14] Comptes utilisateurs...")
superadmin = User.objects.create_superuser('admin', 'admin@smartschool.ml', 'admin123')
superadmin.role = 'super_admin'; superadmin.first_name = 'Super'; superadmin.last_name = 'Admin'; superadmin.save()

directeur = User.objects.create_user('directeur', 'directeur@efbt.ml', 'admin123')
directeur.role = 'admin'; directeur.first_name = 'Mamadou'; directeur.last_name = 'Coulibaly'
directeur.etablissement = etab; directeur.save()

comptable = User.objects.create_user('comptable', 'compta@efbt.ml', 'admin123')
comptable.role = 'comptable'; comptable.first_name = 'Fatoumata'; comptable.last_name = 'Diallo'
comptable.etablissement = etab; comptable.telephone = '+223 76 11 22 33'; comptable.save()

surveillant = User.objects.create_user('surveillant', 'surveillant@efbt.ml', 'admin123')
surveillant.role = 'surveillant'; surveillant.first_name = 'Ibrahim'; surveillant.last_name = 'Sangare'
surveillant.etablissement = etab; surveillant.telephone = '+223 77 22 33 44'; surveillant.save()

secretaire = User.objects.create_user('secretaire', 'secretaire@efbt.ml', 'admin123')
secretaire.role = 'secretariat'; secretaire.first_name = 'Aminata'; secretaire.last_name = 'Kone'
secretaire.etablissement = etab; secretaire.save()

print("   ✅ admin / directeur / comptable / surveillant / secretaire (mdp: admin123)")

# ══════════════════════════════════════════════════════════════
# [7] MATIÈRES
# ══════════════════════════════════════════════════════════════
print("\n[7/14] Matières...")
# IMPORTANT pour 1er cycle : coefficient = 1 pour toutes les matières
# (La règle coef=1 est appliquée dans le service, mais on garde coef=1 ici aussi)
matieres_data = [
    # (nom, code, coef_global, is_conduite)
    ('Lecture',          'LEC',  1, False),
    ('Recitation',       'REC',  1, False),
    ('Redaction',        'RED',  1, False),
    ('Dictee/Questions', 'DIC',  1, False),
    ('Mathematiques',    'MATH', 1, False),
    ('Sciences',         'SCI',  1, False),
    ('Histoire/Geo',     'HG',   1, False),
    ('ECM',              'ECM',  1, False),
    ('EPS',              'EPS',  1, False),
    ('Dessin',           'DES',  1, False),
    # 2ème cycle et plus
    ('Physique/Chimie',  'PC',   2, False),
    ('Biologie',         'BIO',  2, False),
    ('Anglais',          'ANG',  2, False),
    # Conduite (tous cycles)
    ('Conduite',         'CON',  1, True),
]
matieres = {}
for nom, code, coef, is_c in matieres_data:
    matieres[nom] = Matiere.objects.create(
        etablissement=etab, nom=nom, code=code, coefficient=coef, is_conduite=is_c
    )
print(f"   ✅ {len(matieres)} matières (coef=1 pour 1er cycle)")

# ══════════════════════════════════════════════════════════════
# [7b] MATIÈRES PAR CYCLE
# ══════════════════════════════════════════════════════════════
print("\n[7b/14] Matières par cycle...")

# 1ER CYCLE : coef=1 pour TOUTES les matières (règle métier)
mats_1er = [
    ('Lecture', 1), ('Recitation', 1), ('Redaction', 1), ('Dictee/Questions', 1),
    ('Mathematiques', 1), ('Sciences', 1), ('Histoire/Geo', 1), ('ECM', 1),
    ('EPS', 1), ('Dessin', 1), ('Conduite', 1),
]
for ordre, (nom, coef) in enumerate(mats_1er, 1):
    if nom in matieres:
        MatiereCycle.objects.create(
            cycle=cycle_1er, matiere=matieres[nom],
            coefficient=1,  # ← coef TOUJOURS 1 pour le 1er cycle
            est_obligatoire=True, ordre=ordre
        )

# 2ÈME CYCLE
mats_2nd = [
    ('Redaction', 3), ('Dictee/Questions', 2), ('Mathematiques', 3),
    ('Physique/Chimie', 3), ('Biologie', 2), ('Anglais', 2),
    ('Histoire/Geo', 2), ('ECM', 1), ('EPS', 1), ('Dessin', 1), ('Conduite', 1),
]
for ordre, (nom, coef) in enumerate(mats_2nd, 1):
    if nom in matieres:
        MatiereCycle.objects.create(
            cycle=cycle_2nd, matiere=matieres[nom],
            coefficient=coef, est_obligatoire=True, ordre=ordre
        )

print(f"   ✅ 1er cycle : {len(mats_1er)} matières (toutes coef=1)")
print(f"   ✅ 2ème cycle : {len(mats_2nd)} matières (coefs officiels)")

# ══════════════════════════════════════════════════════════════
# [7c] CYCLES ACTIFS + DIVISIONS
# ══════════════════════════════════════════════════════════════
print("\n[7c/14] Cycles actifs + Divisions...")
CycleActif.objects.create(etablissement=etab, cycle=cycle_1er, ordre=1)
CycleActif.objects.create(etablissement=etab, cycle=cycle_2nd, ordre=2)

div_1er = Division.objects.create(
    etablissement=etab, nom="1er Cycle Fondamental", code="FOND1",
    directeur_nom="M. Mamadou Coulibaly", directeur_user=directeur,
    entete_ligne1="Ecole Fondamentale Babemba Traore",
    entete_ligne2="1er Cycle — Bamako, Mali", couleur_principale="#1565C0", ordre=1
)
div_1er.cycles.set([cycle_1er])

div_2nd = Division.objects.create(
    etablissement=etab, nom="2ème Cycle Fondamental", code="FOND2",
    directeur_nom="M. Mamadou Coulibaly", directeur_user=directeur,
    entete_ligne1="Ecole Fondamentale Babemba Traore",
    entete_ligne2="2ème Cycle — Bamako, Mali", couleur_principale="#0D47A1", ordre=2
)
div_2nd.cycles.set([cycle_2nd])
print(f"   ✅ 2 cycles actifs (1er + 2ème) | 2 divisions")

# ══════════════════════════════════════════════════════════════
# [8] NIVEAUX ET CLASSES
# ══════════════════════════════════════════════════════════════
print("\n[8/14] Niveaux et classes...")
niveaux_data = [
    ('1ère Année', 1, cycle_1er), ('2ème Année', 2, cycle_1er),
    ('3ème Année', 3, cycle_1er), ('4ème Année', 4, cycle_1er),
    ('5ème Année', 5, cycle_1er), ('6ème Année', 6, cycle_1er),
    ('7ème Année', 7, cycle_2nd), ('8ème Année', 8, cycle_2nd),
    ('9ème Année', 9, cycle_2nd),
]
niveaux = {}
for nom, ordre, cycle_obj in niveaux_data:
    niveaux[nom] = Niveau.objects.create(etablissement=etab, nom=nom, ordre=ordre, cycle=cycle_obj)

classes_data = [
    # (nom_classe, niveau, capacite)
    ('1A', '1ère Année', 42), ('1B', '1ère Année', 40),
    ('2A', '2ème Année', 38), ('2B', '2ème Année', 36),
    ('3A', '3ème Année', 41), ('3B', '3ème Année', 39),
    ('4A', '4ème Année', 40), ('5A', '5ème Année', 38),
    ('6A', '6ème Année', 35),
    ('7A', '7ème Année', 40), ('8A', '8ème Année', 38), ('9A', '9ème Année', 33),
]
classes = {}
for nom, niv_nom, cap in classes_data:
    classes[nom] = Classe.objects.create(
        etablissement=etab, annee=annee,
        niveau=niveaux[niv_nom], nom=nom, capacite_max=cap
    )
print(f"   ✅ {len(niveaux)} niveaux, {len(classes)} classes")

# ══════════════════════════════════════════════════════════════
# [9] ENSEIGNANTS
# ══════════════════════════════════════════════════════════════
print("\n[9/14] Enseignants...")
enseignants_data = [
    ('Diallo',    'Boubacar', 'bdiallo',    'Mathématiques',    'Master Maths',     180000),
    ('Keita',     'Mariam',   'mkeita',     'Français-Lettres', 'Licence Lettres',  155000),
    ('Sangare',   'Ousmane',  'osangare',   'Sciences',         'Master Sciences',  165000),
    ('Traore',    'Seydou',   'straore',    'Histoire-Géo',     'Licence Histoire', 145000),
    ('Camara',    'Aminata',  'acamara',    'Anglais',          'Master Anglais',   158000),
    ('Coulibaly', 'Bourama',  'bcoulibaly', 'EPS',              'STAPS',            140000),
]
ens_objects = []
for nom, prenom, username, spec, diplome, salaire in enseignants_data:
    u = User.objects.create_user(username, f'{username}@efbt.ml', 'admin123')
    u.first_name = prenom; u.last_name = nom; u.role = 'enseignant'
    u.etablissement = etab; u.save()
    ens = Enseignant.objects.create(
        user=u, etablissement=etab, specialite=spec, diplome=diplome,
        date_embauche=datetime.date(2020, 9, 1), salaire=salaire, statut='actif'
    )
    ens_objects.append(ens)
print(f"   ✅ {len(ens_objects)} enseignants")

# ══════════════════════════════════════════════════════════════
# [10] AFFECTATIONS MATIÈRE/CLASSE
# ══════════════════════════════════════════════════════════════
print("\n[10/14] Affectations matière/classe...")
affectations_map = [
    (ens_objects[0], ['Mathematiques']),
    (ens_objects[1], ['Redaction', 'Dictee/Questions', 'Lecture', 'Recitation']),
    (ens_objects[2], ['Sciences', 'Biologie', 'Physique/Chimie']),
    (ens_objects[3], ['Histoire/Geo', 'ECM']),
    (ens_objects[4], ['Anglais']),
    (ens_objects[5], ['EPS', 'Dessin']),
]
nb_aff = 0
for ens, mats_list in affectations_map:
    for cl in classes.values():
        for mat_nom in mats_list:
            if mat_nom in matieres:
                try:
                    AffectationMatiere.objects.create(
                        enseignant=ens, classe=cl,
                        matiere=matieres[mat_nom], annee=annee,
                        heures_semaine=random.choice([2, 3, 4])
                    )
                    nb_aff += 1
                except Exception:
                    pass
print(f"   ✅ {nb_aff} affectations")

# ══════════════════════════════════════════════════════════════
# [11] ÉLÈVES + TUTEURS + INSCRIPTIONS
# ══════════════════════════════════════════════════════════════
print("\n[11/14] Élèves, tuteurs, inscriptions...")
eleves_data = [
    # 1ère Année — classe 1A (4 élèves)
    ('Traore',    'Awa',       'F', '2016-03-14', '1A', 'Traore Moussa',     '+223 76 11 22 33'),
    ('Coulibaly', 'Ibrahim',   'M', '2016-07-22', '1A', 'Coulibaly Seydou',  '+223 70 22 33 44'),
    ('Diallo',    'Kadiatou',  'F', '2016-11-05', '1A', 'Diallo Amadou',     '+223 65 33 44 55'),
    ('Kone',      'Lassana',   'M', '2016-08-18', '1A', 'Kone Bakary',       '+223 79 44 55 66'),
    # 1B (4 élèves)
    ('Bah',       'Mariama',   'F', '2016-01-30', '1B', 'Bah Ibrahima',      '+223 72 55 66 77'),
    ('Camara',    'Seydou',    'M', '2016-05-12', '1B', 'Camara Fanta',      '+223 66 66 77 88'),
    ('Sidibe',    'Aminata',   'F', '2016-09-25', '1B', 'Sidibe Modibo',     '+223 75 77 88 99'),
    ('Dembele',   'Oumar',     'M', '2016-02-08', '1B', 'Dembele Issa',      '+223 78 88 99 00'),
    # 2A (4 élèves)
    ('Toure',     'Aissata',   'F', '2015-06-17', '2A', 'Toure Salif',       '+223 71 99 00 11'),
    ('Sangare',   'Bourama',   'M', '2015-11-03', '2A', 'Sangare Hawa',      '+223 74 00 11 22'),
    ('Keita',     'Fatoumata', 'F', '2015-04-22', '2A', 'Keita Mamadou',     '+223 77 11 22 33'),
    ('Doumbia',   'Souleymane','M', '2015-09-15', '2A', 'Doumbia Rokia',     '+223 73 22 33 44'),
    # 3A (4 élèves)
    ('Fofana',    'Adama',     'M', '2014-08-11', '3A', 'Fofana Tenin',      '+223 79 66 77 88'),
    ('Diarra',    'Djeneba',   'F', '2014-05-23', '3A', 'Diarra Moussa',     '+223 72 77 88 99'),
    ('Konate',    'Cheick',    'M', '2014-10-14', '3A', 'Konate Fatoumata',  '+223 66 88 99 00'),
    ('Ndiaye',    'Aminata',   'F', '2014-02-06', '3A', 'Ndiaye Oumar',      '+223 75 99 00 11'),
    # 6A (4 élèves — fin du 1er cycle)
    ('Cisse',     'Rokia',     'F', '2012-04-18', '6A', 'Cisse Boubacar',    '+223 71 11 22 33'),
    ('Sylla',     'Aboubacar', 'M', '2012-09-07', '6A', 'Sylla Mariam',      '+223 74 22 33 44'),
    ('Barry',     'Kadidiatou','F', '2012-12-25', '6A', 'Barry Ibrahima',    '+223 77 33 44 55'),
    ('Maiga',     'Salimata',  'F', '2012-03-20', '6A', 'Maiga Ousmane',     '+223 76 55 66 77'),
    # 7A (3 élèves — 2ème cycle)
    ('Sissoko',   'Mariam',    'F', '2011-07-08', '7A', 'Sissoko Drissa',    '+223 76 33 44 55'),
    ('Bagayoko',  'Ousmane',   'M', '2011-12-19', '7A', 'Bagayoko Sali',     '+223 70 44 55 66'),
    ('Coulibaly', 'Hawa',      'F', '2011-03-27', '7A', 'Coulibaly Bakari',  '+223 65 55 66 77'),
    # 9A (3 élèves — fin 2ème cycle)
    ('Harouna',   'Dagnon',    'M', '2010-06-13', '9A', 'Harouna Bakary',    '+223 73 44 55 66'),
    ('Barry2',    'Moussa',    'M', '2010-09-08', '9A', 'Barry Boubacar',    '+223 71 66 77 88'),
    ('Sanogo',    'Fatoumata', 'F', '2010-11-15', '9A', 'Sanogo Drissa',     '+223 74 77 88 99'),
]

eleve_objects = []
for nom, prenom, sexe, dob, cl_nom, tut_nom, tut_tel in eleves_data:
    tut_parts = tut_nom.split(' ', 1)
    tuteur = Tuteur.objects.create(
        etablissement=etab,
        nom=tut_parts[0], prenom=tut_parts[1] if len(tut_parts) > 1 else '',
        lien=random.choice(['pere', 'mere', 'tuteur']), telephone=tut_tel
    )
    eleve = Eleve.objects.create(
        etablissement=etab, nom=nom, prenom=prenom, sexe=sexe,
        date_naissance=datetime.date.fromisoformat(dob),
        lieu_naissance=random.choice(['Bamako', 'Mopti', 'Segou', 'Kayes', 'Sikasso']),
        tuteur=tuteur
    )
    Inscription.objects.create(eleve=eleve, classe=classes[cl_nom], annee=annee, statut='actif')
    eleve_objects.append(eleve)

# Compte parent → premier élève
premier_eleve = eleve_objects[0]
parent_user = User.objects.create_user('parent1', 'parent1@efbt.ml', 'parent123')
parent_user.role = 'parent'; parent_user.first_name = premier_eleve.tuteur.prenom
parent_user.last_name = premier_eleve.tuteur.nom; parent_user.etablissement = etab; parent_user.save()
premier_eleve.tuteur.user_compte = parent_user; premier_eleve.tuteur.save()

# Compte élève → Harouna Dagnon (9A)
eleve_harouna = next((e for e in eleve_objects if e.prenom == 'Dagnon'), eleve_objects[-1])
eleve_user = User.objects.create_user('eleve1', 'eleve1@efbt.ml', 'eleve123')
eleve_user.role = 'eleve'; eleve_user.first_name = eleve_harouna.prenom
eleve_user.last_name = eleve_harouna.nom; eleve_user.etablissement = etab; eleve_user.save()
eleve_harouna.user_compte = eleve_user; eleve_harouna.save()

print(f"   ✅ {len(eleve_objects)} élèves inscrits")
print(f"   ✅ Compte parent : parent1 / parent123 → {premier_eleve.nom_complet}")
print(f"   ✅ Compte élève  : eleve1  / eleve123  → {eleve_harouna.nom_complet}")

# ══════════════════════════════════════════════════════════════
# [12] FINANCES
# ══════════════════════════════════════════════════════════════
print("\n[12/14] Types de frais et paiements...")
frais_data = [
    ("Frais d'inscription", 25000, True),
    ('Scolarite mensuelle', 15000, True),
    ('Cantine mensuelle', 8000, False),
    ('Frais examen', 10000, True),
    ('Tenue scolaire', 5000, False),
]
types_frais = {
    nom: TypeFrais.objects.create(etablissement=etab, annee=annee, nom=nom, montant_defaut=m, is_obligatoire=o)
    for nom, m, o in frais_data
}
modes = ['especes', 'especes', 'especes', 'mobile_money']
today = timezone.now()
nb_paiements = 0
for eleve in eleve_objects:
    Paiement.objects.create(
        etablissement=etab, eleve=eleve, annee=annee,
        type_frais=types_frais["Frais d'inscription"],
        montant=25000, mode_paiement=random.choice(modes), statut='valide',
        date_paiement=today - datetime.timedelta(days=random.randint(60, 90)),
        encaisse_par=comptable, reference=f"PAY-INSC-{eleve.matricule[-4:]}"
    )
    nb_paiements += 1
    for mois_delta in [80, 50, 20, -10, -40]:
        if random.random() > 0.15:
            Paiement.objects.create(
                etablissement=etab, eleve=eleve, annee=annee,
                type_frais=types_frais['Scolarite mensuelle'],
                montant=15000, mode_paiement=random.choice(modes), statut='valide',
                date_paiement=today - datetime.timedelta(days=abs(mois_delta) + random.randint(0, 5)),
                encaisse_par=comptable
            )
            nb_paiements += 1
print(f"   ✅ {nb_paiements} paiements")

# ══════════════════════════════════════════════════════════════
# [13] NOTES
# ══════════════════════════════════════════════════════════════
print("\n[13/14] Notes...")

# Profils de notes /10 pour le 1er cycle
def note_sur_10(profil='moyen'):
    if profil == 'excellent': return round(random.uniform(8.0, 10.0), 2)
    if profil == 'bien':      return round(random.uniform(6.5,  8.5), 2)
    if profil == 'moyen':     return round(random.uniform(4.0,  7.0), 2)
    if profil == 'faible':    return round(random.uniform(1.5,  4.5), 2)
    return None

profils_possibles = ['excellent', 'bien', 'bien', 'moyen', 'moyen', 'moyen', 'faible']

# Matières du 1er cycle (hors conduite)
mat_noms_1er = [nom for nom, _, _, is_c in matieres_data
                if nom in [m for m, _ in mats_1er] and not is_c]
matieres_1er = [matieres[nom] for nom in mat_noms_1er if nom in matieres]

# ─── 1ER CYCLE : Modèle Composition /10, coef=1 ─────────────
nb_compos = cycle_1er.nb_compositions_trimestre  # = 3
nb_compositions_crees = 0

classes_1er = [cl for cl_nom, cl in classes.items()
               if cl.niveau.cycle and cl.niveau.cycle.type_cycle == 'premier_cycle']

for classe_obj in classes_1er:
    inscriptions = classe_obj.inscriptions.filter(is_active=True).select_related('eleve')
    for insc in inscriptions:
        profil = random.choice(profils_possibles)
        for mat in matieres_1er:
            for numero in range(1, nb_compos + 1):
                note_val = note_sur_10(profil)
                # Légère variation par composition
                if note_val is not None:
                    note_val = max(0, min(10, round(note_val + random.uniform(-0.5, 0.5), 2)))
                Composition.objects.create(
                    eleve=insc.eleve,
                    matiere=mat,
                    classe=classe_obj,
                    annee=annee,
                    # periode = None  ← le 1er cycle n'utilise pas la période
                    numero=numero,
                    note=Decimal(str(note_val)) if note_val is not None else None,
                    note_max=Decimal('10'),  # ← /10 OBLIGATOIRE
                    saisi_par=directeur,
                )
                nb_compositions_crees += 1

print(f"   ✅ 1er cycle — {nb_compositions_crees} compositions /10 créées")
print(f"      ({len(classes_1er)} classes × ~{nb_compos} compos × {len(matieres_1er)} matières)")

# ─── 2ÈME CYCLE : NotePeriode classique (Moy.Classe /20 + Moy.Compo /40) ─
mat_noms_2nd = [nom for nom, _ in mats_2nd if nom != 'Conduite']
matieres_2nd_list = [matieres[nom] for nom in mat_noms_2nd if nom in matieres]
mat_conduite = matieres.get('Conduite')

classes_2nd = [cl for cl_nom, cl in classes.items()
               if cl.niveau.cycle and cl.niveau.cycle.type_cycle == 'second_cycle']

nb_notes_2nd = 0
for classe_obj in classes_2nd:
    inscriptions = classe_obj.inscriptions.filter(is_active=True).select_related('eleve')
    for insc in inscriptions:
        # Notes académiques
        for mat in matieres_2nd_list:
            base = random.uniform(7, 16)
            mc = round(min(20, max(0, base + random.uniform(-2, 2))), 2)
            mn = round(min(40, max(0, mc * 2 + random.uniform(-4, 4))), 2)
            NotePeriode.objects.create(
                eleve=insc.eleve, matiere=mat, classe=classe_obj, periode=p1,
                moy_classe=Decimal(str(mc)), moy_compo=Decimal(str(mn)),
                note_max_classe=20, note_max_compo=40, saisi_par=directeur
            )
            nb_notes_2nd += 1
        # Conduite
        if mat_conduite:
            nb_abs = random.choice([0, 0, 0, 1, 1, 2, 3])
            score = max(0, round(18 - (nb_abs * 1.5), 1))
            NotePeriode.objects.create(
                eleve=insc.eleve, matiere=mat_conduite, classe=classe_obj, periode=p1,
                note_conduite=Decimal(str(score)), saisi_par=surveillant
            )
            nb_notes_2nd += 1

print(f"   ✅ 2ème cycle — {nb_notes_2nd} NotePeriode /20 créées")

# ─── PRÉSENCES ────────────────────────────────────────────────
nb_presences = 0
for delta in range(10):
    date_p = today.date() - datetime.timedelta(days=delta)
    if date_p.weekday() < 5:
        for classe_obj in list(classes.values())[:8]:
            for insc in classe_obj.inscriptions.filter(is_active=True):
                statut = random.choices(
                    ['present', 'absent', 'retard', 'justifie'],
                    weights=[82, 9, 6, 3]
                )[0]
                Presence.objects.get_or_create(
                    eleve=insc.eleve, classe=classe_obj, date=date_p,
                    defaults={'statut': statut,
                              'enregistre_par': directeur if statut != 'absent' else surveillant}
                )
                nb_presences += 1
print(f"   ✅ {nb_presences} présences (10 derniers jours)")

# ══════════════════════════════════════════════════════════════
# [14] PARAMÈTRES ET MODÈLES DE DOCUMENTS
# ══════════════════════════════════════════════════════════════
print("\n[14/14] Paramètres et modèles de documents...")
ParametreEtablissement.objects.create(
    etablissement=etab, devise='FCFA', type_periode='trimestre',
    note_passage=5, note_max=10,
    entete_bulletin="Republique du Mali\nMinistere de l'Education Nationale",
    pied_bulletin="Ce bulletin est certifie conforme par la direction."
)

ModeleDocument.objects.create(
    etablissement=etab, type_document='bulletin', nom='Bulletin 1er Cycle /10', is_actif=True,
    ligne1_gauche=etab.nom, ligne2_gauche='Bamako — Mali',
    ligne1_droite='Republique du Mali', ligne2_droite='Un Peuple — Un But — Une Foi',
    titre_document='BULLETIN DE COMPOSITION', couleur_titre_bg='#1565C0', couleur_titre_texte='#ffffff',
    label_signature_gauche='Le Directeur', label_signature_droite='Le Parent ou Tuteur',
    texte_pied_page='Ce bulletin est certifie conforme.',
    afficher_rang=True, afficher_moy_premier=True,
    note_max_classe=10, note_max_compo=10,  # ← /10 pour le 1er cycle
)

ModeleDocument.objects.create(
    etablissement=etab, type_document='recu', nom='Recu Standard', is_actif=True,
    titre_document='RECU DE PAIEMENT', couleur_titre_bg='#1565C0',
    format_recu='A5', couleur_accent_recu='#FF6F00'
)

ModeleDocument.objects.create(
    etablissement=etab, type_document='certificat', nom='Certificat de Scolarite', is_actif=True,
    ligne1_gauche='Republique du Mali', ligne2_gauche=etab.nom,
    titre_document='CERTIFICAT DE SCOLARITE', couleur_titre_bg='#1565C0'
)

ModeleDocument.objects.create(
    etablissement=etab, type_document='carte_scolaire', nom='Carte Scolaire', is_actif=True,
    titre_document='CARTE SCOLAIRE', couleur_titre_bg='#0D47A1', couleur_titre_texte='#ffffff'
)

ModeleDocument.objects.create(
    etablissement=etab, type_document='attestation', nom='Attestation de Frequentation', is_actif=True,
    ligne1_gauche='Republique du Mali', ligne2_gauche=etab.nom,
    titre_document='ATTESTATION DE FREQUENTATION', couleur_titre_bg='#1565C0',
    label_signature_gauche='Le Directeur',
    texte_pied_page='Delivre pour servir et valoir ce que de droit.'
)

print(f"   ✅ Paramètres + 5 modèles de documents créés")

# ══════════════════════════════════════════════════════════════
# RÉSUMÉ FINAL
# ══════════════════════════════════════════════════════════════
print("\n" + "=" * 60)
print("  ✅  INSTALLATION TERMINÉE AVEC SUCCÈS")
print("=" * 60)
print(f"\n  Établissement : {etab.nom}")
print(f"  Année active  : {annee.libelle}")
print(f"\n  DONNÉES CRÉÉES :")
print(f"  ├─ Classes      : {Classe.objects.count()}")
print(f"  ├─ Élèves       : {Eleve.objects.count()}")
print(f"  ├─ Enseignants  : {Enseignant.objects.count()}")
print(f"  ├─ Affectations : {AffectationMatiere.objects.count()}")
print(f"  ├─ Paiements    : {Paiement.objects.count()}")
print(f"  ├─ Présences    : {Presence.objects.count()}")
print(f"  ├─ Compositions : {Composition.objects.count()} (/10, coef=1) [1er cycle]")
print(f"  └─ NotePériode  : {NotePeriode.objects.count()} (/20+/40) [2ème cycle]")

# Exemple d'URL pour tester le bulletin de composition
insc_1er = Inscription.objects.filter(
    classe__niveau__cycle__type_cycle='premier_cycle', is_active=True
).select_related('eleve').first()
if insc_1er:
    print(f"\n  🔗 TESTER LE BULLETIN DE COMPOSITION :")
    print(f"     /notes/bulletin-composition/{insc_1er.eleve.pk}/{annee.pk}/1/")
    print(f"     Élève : {insc_1er.eleve.nom_complet} — Classe : {insc_1er.classe.nom}")

print(f"\n  COMPTES DE CONNEXION :")
print(f"  ┌────────────────┬───────────┬──────────────────────────┐")
print(f"  │ Identifiant    │ Mot passe │ Rôle                     │")
print(f"  ├────────────────┼───────────┼──────────────────────────┤")
print(f"  │ admin          │ admin123  │ Super Administrateur      │")
print(f"  │ directeur      │ admin123  │ Admin établissement       │")
print(f"  │ comptable      │ admin123  │ Comptable                 │")
print(f"  │ surveillant    │ admin123  │ Surveillant Général       │")
print(f"  │ bdiallo        │ admin123  │ Enseignant (Maths)        │")
print(f"  │ mkeita         │ admin123  │ Enseignant (Français)     │")
print(f"  │ parent1        │ parent123 │ Parent (Traore Awa)       │")
print(f"  │ eleve1         │ eleve123  │ Élève (Harouna Dagnon)    │")
print(f"  └────────────────┴───────────┴──────────────────────────┘")
print(f"\n  Ouvrir : http://127.0.0.1:8000")
print("=" * 60)
