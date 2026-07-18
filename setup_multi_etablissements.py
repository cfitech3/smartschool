"""
SmartSchool ERP - Setup 4 Etablissements de test
=================================================
Cree 4 etablissements distincts avec donnees completes :
  1. Ecole Fondamentale Babemba Traore       (1er + 2eme cycle)
  2. Lycee Massa Makan Diabate               (Lycee - series A/C/D)
  3. Institut de Formation Professionnelle    (Centre de formation)
  4. Universite Privee Nelson Mandela        (Universite LMD)

Usage :
    python -X utf8 setup_multi_etablissements.py

ATTENTION : nettoie TOUTES les donnees existantes avant de recreer.
"""
import os, sys, django, datetime, random
from decimal import Decimal

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'smartschool.settings')
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
django.setup()

from django.utils import timezone
from accounts.models import User
from etablissements.models import (
    Etablissement, AnneeScolaire, Niveau, Classe, Enseignant,
    AffectationMatiere, ParametreEtablissement, ModeleDocument,
    Cycle, SerieLycee, MatiereCycle, UEUniversite, CycleActif, Division,
)
from eleves.models import Eleve, Tuteur, Inscription, Presence
from finances.models import TypeFrais, Paiement
from notes.models import Matiere, Periode, NotePeriode, EmploiDuTemps

# ─────────────────────────────────────────────────────────────────────────────
# NETTOYAGE COMPLET
# ─────────────────────────────────────────────────────────────────────────────
print("=" * 60)
print("  SmartSchool — Setup 4 Etablissements de test")
print("=" * 60)
print("\n[NETTOYAGE] Suppression de toutes les donnees existantes...")

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
Cycle.objects.all().delete()
Etablissement.objects.all().delete()
User.objects.filter(is_superuser=False).delete()
User.objects.filter(username='admin').delete()
print("   OK\n")

# ─────────────────────────────────────────────────────────────────────────────
# SUPER ADMIN COMMUN
# ─────────────────────────────────────────────────────────────────────────────
superadmin = User.objects.create_superuser('admin', 'admin@smartschool.ml', 'admin123')
superadmin.role = 'super_admin'
superadmin.first_name = 'Super'
superadmin.last_name = 'Admin'
superadmin.save()
print("  Super Admin cree : admin / admin123\n")

# ─────────────────────────────────────────────────────────────────────────────
# DONNEES COMMUNES
# ─────────────────────────────────────────────────────────────────────────────
NOMS_M = ['Traore', 'Coulibaly', 'Diallo', 'Keita', 'Sangare', 'Kone', 'Dembele',
          'Camara', 'Sidibe', 'Toure', 'Doumbia', 'Sissoko', 'Bagayoko', 'Cisse',
          'Sylla', 'Barry', 'Maiga', 'Fofana', 'Bah', 'Ndiaye']
PRENOMS_M = ['Moussa', 'Ibrahim', 'Boubacar', 'Ousmane', 'Mamadou', 'Seydou',
             'Modibo', 'Salif', 'Drissa', 'Bakary', 'Adama', 'Cheick', 'Souleymane']
PRENOMS_F = ['Awa', 'Fatoumata', 'Aminata', 'Mariam', 'Kadiatou', 'Aissata',
             'Djeneba', 'Hawa', 'Rokia', 'Salimata', 'Kadidiatou', 'Tenin']
VILLES = ['Bamako', 'Mopti', 'Segou', 'Kayes', 'Sikasso', 'Gao']
MODES = ['especes', 'especes', 'mobile_money']


def rand_eleve_data(n, classe_nom, annee_naissance_range=(2008, 2016)):
    data = []
    for _ in range(n):
        sexe = random.choice(['M', 'F'])
        prenom = random.choice(PRENOMS_M if sexe == 'M' else PRENOMS_F)
        nom = random.choice(NOMS_M)
        an = random.randint(*annee_naissance_range)
        dob = f"{an}-{random.randint(1,12):02d}-{random.randint(1,28):02d}"
        tut_nom = random.choice(NOMS_M)
        tut_prenom = random.choice(PRENOMS_M + PRENOMS_F)
        tut_tel = f"+223 {random.randint(60,79)} {random.randint(10,99)} {random.randint(10,99)} {random.randint(10,99)}"
        data.append((nom, prenom, sexe, dob, classe_nom, f"{tut_nom} {tut_prenom}", tut_tel))
    return data


def creer_eleves(etab, annee, classes_dict, eleves_data, comptable):
    eleve_objects = []
    for nom, prenom, sexe, dob, cl_nom, tut_nom, tut_tel in eleves_data:
        parts = tut_nom.split(' ', 1)
        tuteur = Tuteur.objects.create(
            etablissement=etab, nom=parts[0],
            prenom=parts[1] if len(parts) > 1 else '',
            lien=random.choice(['pere', 'mere', 'tuteur']), telephone=tut_tel
        )
        eleve = Eleve.objects.create(
            etablissement=etab, nom=nom, prenom=prenom, sexe=sexe,
            date_naissance=datetime.date.fromisoformat(dob),
            lieu_naissance=random.choice(VILLES), tuteur=tuteur
        )
        classe = classes_dict.get(cl_nom)
        if classe:
            Inscription.objects.create(eleve=eleve, classe=classe, annee=annee, statut='actif')
        eleve_objects.append(eleve)
    return eleve_objects


def creer_notes_presences(etab, eleve_objects, classes_dict, matieres_dict,
                           periode, directeur, surveillant):
    today = timezone.now()
    matieres_list = list(matieres_dict.values())
    nb_notes = 0
    for classe_obj in classes_dict.values():
        inscriptions = classe_obj.inscriptions.filter(is_active=True).select_related('eleve')
        for insc in inscriptions:
            for mat in matieres_list:
                if mat.is_conduite:
                    score = max(0, round(20 - random.choice([0, 0, 1, 2]) * 1.5, 1))
                    NotePeriode.objects.create(
                        eleve=insc.eleve, matiere=mat, classe=classe_obj, periode=periode,
                        note_conduite=Decimal(str(score)), saisi_par=surveillant
                    )
                else:
                    base = random.uniform(7, 17)
                    mc = round(min(20, max(0, base + random.uniform(-2, 2))), 2)
                    mn = round(min(40, max(0, mc * 2 + random.uniform(-4, 4))), 2)
                    NotePeriode.objects.create(
                        eleve=insc.eleve, matiere=mat, classe=classe_obj, periode=periode,
                        moy_classe=Decimal(str(mc)), moy_compo=Decimal(str(mn)),
                        note_max_classe=20, note_max_compo=40, saisi_par=directeur
                    )
                nb_notes += 1
    nb_pres = 0
    for delta in range(10):
        date_p = today.date() - datetime.timedelta(days=delta)
        if date_p.weekday() < 5:
            for classe_obj in list(classes_dict.values())[:4]:
                for insc in classe_obj.inscriptions.filter(is_active=True):
                    statut = random.choices(
                        ['present', 'absent', 'retard', 'justifie'],
                        weights=[80, 10, 7, 3]
                    )[0]
                    Presence.objects.get_or_create(
                        eleve=insc.eleve, classe=classe_obj, date=date_p,
                        defaults={'statut': statut, 'enregistre_par': directeur}
                    )
                    nb_pres += 1
    return nb_notes, nb_pres


def creer_modeles_documents(etab, couleur_bg='#1565C0'):
    docs = [
        ('bulletin',       'Bulletin Standard',       'BULLETIN DE NOTES'),
        ('recu',           'Recu Standard',           'RECU DE PAIEMENT'),
        ('certificat',     'Certificat de Scolarite', 'CERTIFICAT DE SCOLARITE'),
        ('carte_scolaire', 'Carte Scolaire',          'CARTE SCOLAIRE'),
        ('attestation',    'Attestation',             'ATTESTATION DE FREQUENTATION'),
        ('releve_notes',   'Releve de Notes',         'RELEVE DE NOTES'),
    ]
    for type_doc, nom, titre in docs:
        ModeleDocument.objects.create(
            etablissement=etab, type_document=type_doc, nom=nom,
            is_actif=True, titre_document=titre,
            couleur_titre_bg=couleur_bg, couleur_titre_texte='#ffffff',
            ligne1_droite='Republique du Mali',
            ligne2_droite='Un Peuple - Un But - Une Foi',
            label_signature_gauche='Le Directeur',
            label_signature_droite='Le Parent ou Tuteur',
            afficher_rang=True, afficher_moy_premier=True,
            note_max_classe=20, note_max_compo=40
        )


today = timezone.now()

# =============================================================================
# ETABLISSEMENT 1 : ECOLE FONDAMENTALE BABEMBA TRAORE (1er + 2eme cycle)
# =============================================================================
print("=" * 60)
print("  [1/4] Ecole Fondamentale Babemba Traore (EFBT)")
print("=" * 60)

etab1 = Etablissement.objects.create(
    nom="Ecole Fondamentale Babemba Traore", type='ecole', code='EFBT',
    adresse='Bamako, Commune III, Quartier Hippodrome',
    telephone='+223 20 22 33 44', email='contact@efbt.edu.ml',
    directeur='M. Mamadou Coulibaly',
    slogan="L'excellence au service de la jeunesse malienne",
    couleur_principale='#1565C0', couleur_secondaire='#0D47A1',
)
annee1 = AnneeScolaire.objects.create(
    etablissement=etab1, libelle='2024-2025',
    date_debut=datetime.date(2024, 10, 1),
    date_fin=datetime.date(2025, 6, 30), is_active=True
)
cyc1_1 = Cycle.objects.create(etablissement=etab1, type_cycle='premier_cycle',
    nom='1er Cycle Fondamental', mode_calcul='compo', note_passage=10,
    diplome_prepare='Certificat 1er Cycle', ordre=1)
cyc1_2 = Cycle.objects.create(etablissement=etab1, type_cycle='second_cycle',
    nom='2eme Cycle Fondamental', mode_calcul='compo', note_passage=10,
    diplome_prepare='DEF', ordre=2)
p1_1 = Periode.objects.create(etablissement=etab1, annee=annee1, type='trimestre',
    numero=1, libelle='1er Trimestre',
    date_debut=datetime.date(2024, 10, 1), date_fin=datetime.date(2024, 12, 20), is_active=True)

dir1 = User.objects.create_user('dir_efbt', 'dir@efbt.ml', 'admin123')
dir1.role = 'admin'; dir1.first_name = 'Mamadou'; dir1.last_name = 'Coulibaly'
dir1.etablissement = etab1; dir1.save()
cpt1 = User.objects.create_user('cpt_efbt', 'cpt@efbt.ml', 'admin123')
cpt1.role = 'comptable'; cpt1.first_name = 'Fatoumata'; cpt1.last_name = 'Diallo'
cpt1.etablissement = etab1; cpt1.save()
surv1 = User.objects.create_user('surv_efbt', 'surv@efbt.ml', 'admin123')
surv1.role = 'surveillant'; surv1.first_name = 'Ibrahim'; surv1.last_name = 'Sangare'
surv1.etablissement = etab1; surv1.save()

niveaux1 = {}
for nom, ordre, cyc in [
    ('1ere Annee',1,cyc1_1), ('2eme Annee',2,cyc1_1), ('3eme Annee',3,cyc1_1),
    ('4eme Annee',4,cyc1_1), ('5eme Annee',5,cyc1_1), ('6eme Annee',6,cyc1_1),
    ('7eme Annee',7,cyc1_2), ('8eme Annee',8,cyc1_2), ('9eme Annee',9,cyc1_2),
]:
    niveaux1[nom] = Niveau.objects.create(etablissement=etab1, nom=nom, ordre=ordre, cycle=cyc)

classes1 = {}
for nom_cl, nom_niv, cap in [
    ('1A','1ere Annee',42), ('1B','1ere Annee',40), ('2A','2eme Annee',38),
    ('3A','3eme Annee',41), ('6A','6eme Annee',35), ('7A','7eme Annee',34),
    ('9A','9eme Annee',33),
]:
    classes1[nom_cl] = Classe.objects.create(
        etablissement=etab1, annee=annee1, niveau=niveaux1[nom_niv], nom=nom_cl, capacite_max=cap)

mats1 = {nom: Matiere.objects.create(etablissement=etab1, nom=nom, code=code, coefficient=coef, is_conduite=is_c)
         for nom, code, coef, is_c in [
             ('Redaction','RED',3,False), ('Dictee','DIC',2,False),
             ('Mathematiques','MATH',3,False), ('Physique/Chimie','PC',3,False),
             ('Anglais','ANG',2,False), ('Biologie','BIO',2,False),
             ('Histoire/Geo','HG',2,False), ('ECM','ECM',1,False),
             ('EPS','EPS',1,False), ('Conduite','CON',1,True),
         ]}

ens1_list = []
for nom, prenom, uname, spec in [
    ('Diallo','Boubacar','ens1_efbt','Mathematiques'),
    ('Keita','Mariam','ens2_efbt','Lettres'),
    ('Sangare','Ousmane','ens3_efbt','Sciences'),
]:
    u = User.objects.create_user(uname, f'{uname}@efbt.ml', 'admin123')
    u.first_name = prenom; u.last_name = nom; u.role = 'enseignant'; u.etablissement = etab1; u.save()
    ens = Enseignant.objects.create(user=u, etablissement=etab1, specialite=spec,
        date_embauche=datetime.date(2020,9,1), salaire=160000, statut='actif')
    ens1_list.append(ens)

for ens, mat_noms in [
    (ens1_list[0], ['Mathematiques','Physique/Chimie']),
    (ens1_list[1], ['Redaction','Dictee']),
    (ens1_list[2], ['Biologie','Histoire/Geo','ECM']),
]:
    for cl in classes1.values():
        for mn in mat_noms:
            try:
                AffectationMatiere.objects.create(
                    enseignant=ens, classe=cl, matiere=mats1[mn], annee=annee1, heures_semaine=3)
            except Exception:
                pass

frais1 = {nom: TypeFrais.objects.create(etablissement=etab1, annee=annee1, nom=nom, montant_defaut=mnt, is_obligatoire=obl)
          for nom, mnt, obl in [
              ("Frais d'inscription",25000,True), ('Scolarite mensuelle',15000,True),
              ('Cantine mensuelle',8000,False), ('Frais examen',10000,True),
          ]}

eleves_data1 = []
for cl in classes1.keys():
    eleves_data1 += rand_eleve_data(5, cl, (2008, 2015))
eleves1 = creer_eleves(etab1, annee1, classes1, eleves_data1, cpt1)

for eleve in eleves1:
    Paiement.objects.create(
        etablissement=etab1, eleve=eleve, annee=annee1,
        type_frais=frais1["Frais d'inscription"], montant=25000,
        mode_paiement=random.choice(MODES), statut='valide',
        date_paiement=today - datetime.timedelta(days=random.randint(60,90)),
        encaisse_par=cpt1)

CycleActif.objects.create(etablissement=etab1, cycle=cyc1_1, ordre=1)
CycleActif.objects.create(etablissement=etab1, cycle=cyc1_2, ordre=2)
div1a = Division.objects.create(etablissement=etab1, nom="1er Cycle", code="FOND1",
    directeur_nom="M. Mamadou Coulibaly", directeur_user=dir1,
    entete_ligne1=etab1.nom, entete_ligne2="Bamako, Mali", ordre=1)
div1a.cycles.set([cyc1_1])
div1b = Division.objects.create(etablissement=etab1, nom="2eme Cycle", code="FOND2",
    directeur_nom="M. Mamadou Coulibaly", directeur_user=dir1,
    entete_ligne1=etab1.nom, entete_ligne2="Bamako, Mali", ordre=2)
div1b.cycles.set([cyc1_2])

nb_n1, nb_p1 = creer_notes_presences(etab1, eleves1, classes1, mats1, p1_1, dir1, surv1)
ParametreEtablissement.objects.create(etablissement=etab1, devise='FCFA',
    type_periode='trimestre', note_passage=10, note_max=20)
creer_modeles_documents(etab1, '#1565C0')
print(f"   OK — {len(classes1)} classes | {len(eleves1)} eleves | {nb_n1} notes | {nb_p1} presences")
print(f"   Comptes : dir_efbt / cpt_efbt / surv_efbt  (mdp: admin123)\n")


# =============================================================================
# ETABLISSEMENT 2 : LYCEE MASSA MAKAN DIABATE
# =============================================================================
print("=" * 60)
print("  [2/4] Lycee Massa Makan Diabate (LMMD)")
print("=" * 60)

etab2 = Etablissement.objects.create(
    nom="Lycee Massa Makan Diabate", type='lycee', code='LMMD',
    adresse='Bamako, Commune IV, Quartier Lafiabougou',
    telephone='+223 20 28 44 55', email='contact@lmmd.edu.ml',
    directeur='Mme. Aissata Coulibaly',
    slogan="Former les leaders de demain",
    couleur_principale='#2E7D32', couleur_secondaire='#1B5E20',
)
annee2 = AnneeScolaire.objects.create(
    etablissement=etab2, libelle='2024-2025',
    date_debut=datetime.date(2024, 10, 1),
    date_fin=datetime.date(2025, 6, 30), is_active=True
)
cyc2 = Cycle.objects.create(etablissement=etab2, type_cycle='lycee',
    nom='Lycee', mode_calcul='direct', note_passage=10,
    diplome_prepare='Baccalaureat', ordre=1)
series2 = {}
for code, nom_s, ord_s in [('A','Lettres et Sciences Humaines',1),
                             ('C','Mathematiques et Physique',2),
                             ('D','Sciences de la Nature et de la Vie',3)]:
    series2[code] = SerieLycee.objects.create(cycle=cyc2, code=code, nom=nom_s, ordre=ord_s)
p2_1 = Periode.objects.create(etablissement=etab2, annee=annee2, type='trimestre',
    numero=1, libelle='1er Trimestre',
    date_debut=datetime.date(2024, 10, 1), date_fin=datetime.date(2024, 12, 20), is_active=True)

dir2 = User.objects.create_user('dir_lmmd', 'dir@lmmd.ml', 'admin123')
dir2.role = 'admin'; dir2.first_name = 'Aissata'; dir2.last_name = 'Coulibaly'
dir2.etablissement = etab2; dir2.save()
cpt2 = User.objects.create_user('cpt_lmmd', 'cpt@lmmd.ml', 'admin123')
cpt2.role = 'comptable'; cpt2.first_name = 'Seydou'; cpt2.last_name = 'Traore'
cpt2.etablissement = etab2; cpt2.save()
surv2 = User.objects.create_user('surv_lmmd', 'surv@lmmd.ml', 'admin123')
surv2.role = 'surveillant'; surv2.first_name = 'Oumar'; surv2.last_name = 'Kone'
surv2.etablissement = etab2; surv2.save()

niveaux2 = {}
for nom, ordre in [('Seconde',10), ('Premiere',11), ('Terminale',12)]:
    niveaux2[nom] = Niveau.objects.create(etablissement=etab2, nom=nom, ordre=ordre, cycle=cyc2)

classes2 = {}
for nom_cl, nom_niv, serie_code, cap in [
    ('Seconde A',  'Seconde',   'A', 45),
    ('Seconde C',  'Seconde',   'C', 42),
    ('Premiere A', 'Premiere',  'A', 40),
    ('Premiere C', 'Premiere',  'C', 38),
    ('Terminale A','Terminale', 'A', 35),
    ('Terminale D','Terminale', 'D', 36),
]:
    classes2[nom_cl] = Classe.objects.create(
        etablissement=etab2, annee=annee2, niveau=niveaux2[nom_niv],
        serie=series2[serie_code], nom=nom_cl, capacite_max=cap)

mats2 = {nom: Matiere.objects.create(etablissement=etab2, nom=nom, code=code, coefficient=coef, is_conduite=is_c)
         for nom, code, coef, is_c in [
             ('Mathematiques','MATH',4,False), ('Physique-Chimie','PC',3,False),
             ('Sciences Nat.','SVT',3,False), ('Philosophie','PHILO',2,False),
             ('Histoire-Geo','HG',2,False), ('Francais','FR',3,False),
             ('Anglais','ANG',2,False), ('EPS','EPS',1,False), ('Conduite','CON',1,True),
         ]}

ens2_list = []
for nom, prenom, uname, spec in [
    ('Barry','Aliou','ens1_lmmd','Mathematiques'),
    ('Sissoko','Mariam','ens2_lmmd','Philosophie-Lettres'),
    ('Toure','Amadou','ens3_lmmd','Sciences Naturelles'),
    ('Dembele','Sophie','ens4_lmmd','Anglais'),
]:
    u = User.objects.create_user(uname, f'{uname}@lmmd.ml', 'admin123')
    u.first_name = prenom; u.last_name = nom; u.role = 'enseignant'; u.etablissement = etab2; u.save()
    ens = Enseignant.objects.create(user=u, etablissement=etab2, specialite=spec,
        date_embauche=datetime.date(2019,9,1), salaire=200000, statut='actif')
    ens2_list.append(ens)

for ens, mat_noms in [
    (ens2_list[0], ['Mathematiques','Physique-Chimie']),
    (ens2_list[1], ['Philosophie','Histoire-Geo','Francais']),
    (ens2_list[2], ['Sciences Nat.']),
    (ens2_list[3], ['Anglais']),
]:
    for cl in classes2.values():
        for mn in mat_noms:
            try:
                AffectationMatiere.objects.create(
                    enseignant=ens, classe=cl, matiere=mats2[mn], annee=annee2, heures_semaine=4)
            except Exception:
                pass

frais2 = {nom: TypeFrais.objects.create(etablissement=etab2, annee=annee2, nom=nom, montant_defaut=mnt, is_obligatoire=obl)
          for nom, mnt, obl in [
              ("Frais d'inscription",35000,True), ('Scolarite mensuelle',25000,True),
              ('Frais BAC blanc',15000,True), ('Transport mensuel',8000,False),
          ]}

eleves_data2 = []
for cl in classes2.keys():
    eleves_data2 += rand_eleve_data(6, cl, (2005, 2009))
eleves2 = creer_eleves(etab2, annee2, classes2, eleves_data2, cpt2)

for eleve in eleves2:
    Paiement.objects.create(
        etablissement=etab2, eleve=eleve, annee=annee2,
        type_frais=frais2["Frais d'inscription"], montant=35000,
        mode_paiement=random.choice(MODES), statut='valide',
        date_paiement=today - datetime.timedelta(days=random.randint(60,90)),
        encaisse_par=cpt2)

CycleActif.objects.create(etablissement=etab2, cycle=cyc2, ordre=1)
nb_n2, nb_p2 = creer_notes_presences(etab2, eleves2, classes2, mats2, p2_1, dir2, surv2)
ParametreEtablissement.objects.create(etablissement=etab2, devise='FCFA',
    type_periode='trimestre', note_passage=10, note_max=20)
creer_modeles_documents(etab2, '#2E7D32')
print(f"   OK — {len(classes2)} classes | {len(eleves2)} eleves | {nb_n2} notes | {nb_p2} presences")
print(f"   Comptes : dir_lmmd / cpt_lmmd / surv_lmmd  (mdp: admin123)\n")


# =============================================================================
# ETABLISSEMENT 3 : INSTITUT DE FORMATION PROFESSIONNELLE IBN BATOUTA
# =============================================================================
print("=" * 60)
print("  [3/4] Institut de Formation Professionnelle Ibn Batouta (IFPIB)")
print("=" * 60)

etab3 = Etablissement.objects.create(
    nom="Institut de Formation Professionnelle Ibn Batouta", type='institut', code='IFPIB',
    adresse='Bamako, Commune II, Zone Industrielle',
    telephone='+223 20 35 66 77', email='contact@ifpib.edu.ml',
    directeur='M. Oumar Sidibe',
    slogan="Apprendre un metier, construire un avenir",
    couleur_principale='#E65100', couleur_secondaire='#BF360C',
)
annee3 = AnneeScolaire.objects.create(
    etablissement=etab3, libelle='2024-2025',
    date_debut=datetime.date(2024, 10, 1),
    date_fin=datetime.date(2025, 6, 30), is_active=True
)
cyc3 = Cycle.objects.create(etablissement=etab3, type_cycle='second_cycle',
    nom='Formation Professionnelle', mode_calcul='direct', note_passage=12,
    diplome_prepare='BT (Brevet de Technicien)', ordre=1)
p3_1 = Periode.objects.create(etablissement=etab3, annee=annee3, type='semestre',
    numero=1, libelle='1er Semestre',
    date_debut=datetime.date(2024, 10, 1), date_fin=datetime.date(2025, 2, 28), is_active=True)

dir3 = User.objects.create_user('dir_ifpib', 'dir@ifpib.ml', 'admin123')
dir3.role = 'admin'; dir3.first_name = 'Oumar'; dir3.last_name = 'Sidibe'
dir3.etablissement = etab3; dir3.save()
cpt3 = User.objects.create_user('cpt_ifpib', 'cpt@ifpib.ml', 'admin123')
cpt3.role = 'comptable'; cpt3.first_name = 'Rokia'; cpt3.last_name = 'Camara'
cpt3.etablissement = etab3; cpt3.save()
surv3 = User.objects.create_user('surv_ifpib', 'surv@ifpib.ml', 'admin123')
surv3.role = 'surveillant'; surv3.first_name = 'Modibo'; surv3.last_name = 'Kante'
surv3.etablissement = etab3; surv3.save()

niveaux3 = {}
for nom, ordre in [
    ('BT1 Informatique',1), ('BT2 Informatique',2),
    ('BT1 Gestion',3), ('BT2 Gestion',4), ('BT1 Batiment',5),
]:
    niveaux3[nom] = Niveau.objects.create(etablissement=etab3, nom=nom, ordre=ordre, cycle=cyc3)

classes3 = {}
for nom_cl, nom_niv, cap in [
    ('INFO-1A','BT1 Informatique',30), ('INFO-2A','BT2 Informatique',28),
    ('GEST-1A','BT1 Gestion',32), ('GEST-2A','BT2 Gestion',30),
    ('BAT-1A','BT1 Batiment',25),
]:
    classes3[nom_cl] = Classe.objects.create(
        etablissement=etab3, annee=annee3, niveau=niveaux3[nom_niv], nom=nom_cl, capacite_max=cap)

mats3 = {nom: Matiere.objects.create(etablissement=etab3, nom=nom, code=code, coefficient=coef, is_conduite=is_c)
         for nom, code, coef, is_c in [
             ('Algorithmique','ALGO',3,False), ('Reseaux','RES',3,False),
             ('Comptabilite','COMPTA',4,False), ('Droit Commercial','DROIT',2,False),
             ('Topographie','TOPO',3,False), ('Resistance Materiaux','RM',3,False),
             ('Mathematiques','MATH',2,False), ('Anglais Tech.','ANGT',1,False),
             ('Conduite','CON',1,True),
         ]}

ens3_list = []
for nom, prenom, uname, spec in [
    ('Coulibaly','Bakary','ens1_ifpib','Informatique'),
    ('Diarra','Fatoumata','ens2_ifpib','Gestion-Comptabilite'),
    ('Fofana','Issa','ens3_ifpib','Genie Civil'),
]:
    u = User.objects.create_user(uname, f'{uname}@ifpib.ml', 'admin123')
    u.first_name = prenom; u.last_name = nom; u.role = 'enseignant'; u.etablissement = etab3; u.save()
    ens = Enseignant.objects.create(user=u, etablissement=etab3, specialite=spec,
        date_embauche=datetime.date(2021,9,1), salaire=185000, statut='actif')
    ens3_list.append(ens)

for ens, mat_noms in [
    (ens3_list[0], ['Algorithmique','Reseaux']),
    (ens3_list[1], ['Comptabilite','Droit Commercial']),
    (ens3_list[2], ['Topographie','Resistance Materiaux']),
]:
    for cl in classes3.values():
        for mn in mat_noms:
            try:
                AffectationMatiere.objects.create(
                    enseignant=ens, classe=cl, matiere=mats3[mn], annee=annee3, heures_semaine=3)
            except Exception:
                pass

frais3 = {nom: TypeFrais.objects.create(etablissement=etab3, annee=annee3, nom=nom, montant_defaut=mnt, is_obligatoire=obl)
          for nom, mnt, obl in [
              ("Frais d'inscription",50000,True), ('Scolarite semestrielle',75000,True),
              ('Frais TP',20000,True), ('Kit outils',30000,False),
          ]}

eleves_data3 = []
for cl in classes3.keys():
    eleves_data3 += rand_eleve_data(7, cl, (2000, 2006))
eleves3 = creer_eleves(etab3, annee3, classes3, eleves_data3, cpt3)

for eleve in eleves3:
    Paiement.objects.create(
        etablissement=etab3, eleve=eleve, annee=annee3,
        type_frais=frais3["Frais d'inscription"], montant=50000,
        mode_paiement=random.choice(MODES), statut='valide',
        date_paiement=today - datetime.timedelta(days=random.randint(50,80)),
        encaisse_par=cpt3)

CycleActif.objects.create(etablissement=etab3, cycle=cyc3, ordre=1)
nb_n3, nb_p3 = creer_notes_presences(etab3, eleves3, classes3, mats3, p3_1, dir3, surv3)
ParametreEtablissement.objects.create(etablissement=etab3, devise='FCFA',
    type_periode='semestre', note_passage=12, note_max=20)
creer_modeles_documents(etab3, '#E65100')
print(f"   OK — {len(classes3)} classes | {len(eleves3)} eleves | {nb_n3} notes | {nb_p3} presences")
print(f"   Comptes : dir_ifpib / cpt_ifpib / surv_ifpib  (mdp: admin123)\n")


# =============================================================================
# ETABLISSEMENT 4 : UNIVERSITE PRIVEE NELSON MANDELA
# =============================================================================
print("=" * 60)
print("  [4/4] Universite Privee Nelson Mandela (UPNM)")
print("=" * 60)

etab4 = Etablissement.objects.create(
    nom="Universite Privee Nelson Mandela", type='universite', code='UPNM',
    adresse='Bamako, ACI 2000, Avenue de la Liberte',
    telephone='+223 20 44 55 66', email='contact@upnm.edu.ml',
    directeur='Pr. Cheick Diallo',
    slogan="Savoir, Innover, Servir",
    couleur_principale='#6A1B9A', couleur_secondaire='#4A148C',
)
annee4 = AnneeScolaire.objects.create(
    etablissement=etab4, libelle='2024-2025',
    date_debut=datetime.date(2024, 10, 1),
    date_fin=datetime.date(2025, 6, 30), is_active=True
)
cyc4 = Cycle.objects.create(etablissement=etab4, type_cycle='universite',
    nom='Universite LMD', mode_calcul='credit', note_passage=10,
    diplome_prepare='Licence / Master / Doctorat', ordre=1)
p4_1 = Periode.objects.create(etablissement=etab4, annee=annee4, type='semestre',
    numero=1, libelle='Semestre 1',
    date_debut=datetime.date(2024, 10, 1), date_fin=datetime.date(2025, 1, 31), is_active=True)

dir4 = User.objects.create_user('dir_upnm', 'dir@upnm.ml', 'admin123')
dir4.role = 'admin'; dir4.first_name = 'Cheick'; dir4.last_name = 'Diallo'
dir4.etablissement = etab4; dir4.save()
cpt4 = User.objects.create_user('cpt_upnm', 'cpt@upnm.ml', 'admin123')
cpt4.role = 'comptable'; cpt4.first_name = 'Aminata'; cpt4.last_name = 'Bah'
cpt4.etablissement = etab4; cpt4.save()
surv4 = User.objects.create_user('surv_upnm', 'surv@upnm.ml', 'admin123')
surv4.role = 'surveillant'; surv4.first_name = 'Salif'; surv4.last_name = 'Toure'
surv4.etablissement = etab4; surv4.save()

niveaux4 = {}
for nom, ordre in [
    ('Licence 1 Informatique',1), ('Licence 2 Informatique',2),
    ('Licence 3 Informatique',3), ('Licence 1 Droit',4),
    ('Licence 2 Droit',5), ('Master 1 Informatique',6),
]:
    niveaux4[nom] = Niveau.objects.create(etablissement=etab4, nom=nom, ordre=ordre, cycle=cyc4)

classes4 = {}
for nom_cl, nom_niv, cap in [
    ('L1-INFO','Licence 1 Informatique',60), ('L2-INFO','Licence 2 Informatique',50),
    ('L3-INFO','Licence 3 Informatique',40), ('L1-DROIT','Licence 1 Droit',70),
    ('L2-DROIT','Licence 2 Droit',55), ('M1-INFO','Master 1 Informatique',25),
]:
    classes4[nom_cl] = Classe.objects.create(
        etablissement=etab4, annee=annee4, niveau=niveaux4[nom_niv],
        nom=nom_cl, capacite_max=cap, semestre_actif=1)

# UEs
for code, nom, credits, sem, coef in [
    ('INFO101','Algorithmique et Prog.',4,1,2), ('MATH101','Analyse Mathematique',4,1,2),
    ('INFO102','Architecture Ordi.',3,1,1), ('ANG101','Anglais Academique',2,1,1),
    ('DROIT101','Intro au Droit',4,1,2), ('METH101','Methodologie Recherche',2,1,1),
]:
    UEUniversite.objects.create(
        cycle=cyc4, code=code, nom=nom, credits=credits,
        semestre=sem, coefficient=coef, est_obligatoire=True)

mats4 = {nom: Matiere.objects.create(etablissement=etab4, nom=nom, code=code, coefficient=coef, is_conduite=is_c)
         for nom, code, coef, is_c in [
             ('Algorithmique','ALGO',4,False), ('Analyse Math.','AMATH',4,False),
             ('Architecture Ordi.','ARCHI',3,False), ('Anglais Acad.','ANGL',2,False),
             ('Intro au Droit','DROIT',4,False), ('Methodologie Rech.','METH',2,False),
             ('Conduite','CON',1,True),
         ]}

ens4_list = []
for nom, prenom, uname, spec in [
    ('Keita','Moussa','ens1_upnm','Informatique'),
    ('Diallo','Hawa','ens2_upnm','Mathematiques'),
    ('Sangare','Mamadou','ens3_upnm','Sciences Juridiques'),
]:
    u = User.objects.create_user(uname, f'{uname}@upnm.ml', 'admin123')
    u.first_name = prenom; u.last_name = nom; u.role = 'enseignant'; u.etablissement = etab4; u.save()
    ens = Enseignant.objects.create(user=u, etablissement=etab4, specialite=spec,
        diplome='Doctorat', date_embauche=datetime.date(2018,9,1), salaire=350000, statut='actif')
    ens4_list.append(ens)

for ens, mat_noms in [
    (ens4_list[0], ['Algorithmique','Architecture Ordi.']),
    (ens4_list[1], ['Analyse Math.','Methodologie Rech.']),
    (ens4_list[2], ['Intro au Droit']),
]:
    for cl in classes4.values():
        for mn in mat_noms:
            try:
                AffectationMatiere.objects.create(
                    enseignant=ens, classe=cl, matiere=mats4[mn], annee=annee4, heures_semaine=4)
            except Exception:
                pass

frais4 = {nom: TypeFrais.objects.create(etablissement=etab4, annee=annee4, nom=nom, montant_defaut=mnt, is_obligatoire=obl)
          for nom, mnt, obl in [
              ("Frais d'inscription",80000,True), ('Scolarite semestrielle',200000,True),
              ('Frais examens',25000,True), ('Assurance etudiante',10000,True),
          ]}

eleves_data4 = []
for cl in classes4.keys():
    eleves_data4 += rand_eleve_data(8, cl, (1998, 2006))
eleves4 = creer_eleves(etab4, annee4, classes4, eleves_data4, cpt4)

for eleve in eleves4:
    Paiement.objects.create(
        etablissement=etab4, eleve=eleve, annee=annee4,
        type_frais=frais4["Frais d'inscription"], montant=80000,
        mode_paiement=random.choice(MODES), statut='valide',
        date_paiement=today - datetime.timedelta(days=random.randint(40,70)),
        encaisse_par=cpt4)

CycleActif.objects.create(etablissement=etab4, cycle=cyc4, ordre=1)
nb_n4, nb_p4 = creer_notes_presences(etab4, eleves4, classes4, mats4, p4_1, dir4, surv4)
ParametreEtablissement.objects.create(etablissement=etab4, devise='FCFA',
    type_periode='semestre', note_passage=10, note_max=20)
creer_modeles_documents(etab4, '#6A1B9A')
print(f"   OK — {len(classes4)} classes | {len(eleves4)} eleves | {nb_n4} notes | {nb_p4} presences")
print(f"   Comptes : dir_upnm / cpt_upnm / surv_upnm  (mdp: admin123)\n")


# =============================================================================
# RESUME FINAL
# =============================================================================
print("=" * 60)
print("  INSTALLATION MULTI-ETABLISSEMENTS TERMINEE !")
print("=" * 60)
print(f"""
  Etablissements : {Etablissement.objects.count()}  |  Classes  : {Classe.objects.count()}
  Eleves         : {Eleve.objects.count()}  |  Enseignants : {Enseignant.objects.count()}
  Notes          : {NotePeriode.objects.count()}  |  Presences   : {Presence.objects.count()}
  Paiements      : {Paiement.objects.count()}

  COMPTES DE CONNEXION :
  +-------------------+-----------+-------------------------------+
  | Identifiant       | Mot passe | Role / Etablissement          |
  +-------------------+-----------+-------------------------------+
  | admin             | admin123  | Super Admin (tous etabs)      |
  +-------------------+-----------+-------------------------------+
  | dir_efbt          | admin123  | Directeur  — Ecole EFBT       |
  | cpt_efbt          | admin123  | Comptable  — Ecole EFBT       |
  | surv_efbt         | admin123  | Surveillant— Ecole EFBT       |
  +-------------------+-----------+-------------------------------+
  | dir_lmmd          | admin123  | Directeur  — Lycee LMMD       |
  | cpt_lmmd          | admin123  | Comptable  — Lycee LMMD       |
  | surv_lmmd         | admin123  | Surveillant— Lycee LMMD       |
  +-------------------+-----------+-------------------------------+
  | dir_ifpib         | admin123  | Directeur  — Institut IFPIB   |
  | cpt_ifpib         | admin123  | Comptable  — Institut IFPIB   |
  | surv_ifpib        | admin123  | Surveillant— Institut IFPIB   |
  +-------------------+-----------+-------------------------------+
  | dir_upnm          | admin123  | Directeur  — Universite UPNM  |
  | cpt_upnm          | admin123  | Comptable  — Universite UPNM  |
  | surv_upnm         | admin123  | Surveillant— Universite UPNM  |
  +-------------------+-----------+-------------------------------+

  Ouvrir : http://127.0.0.1:8000
""")
