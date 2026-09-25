"""
SmartSchool ERP - Demo Universite COMPLETE v2
=============================================
Universite : UCADB - Universite Cheikh Anta Diop de Bamako

CONTENU GENERE :
  - 1 Universite avec parametres personnalises
  - 5 Filieres : Informatique, Gestion, Droit, Medecine, Sciences
  - 9 Classes  : L1/L2/L3 Info, L1/L2 Gestion, L1/L2 Droit, L1 Medecine, L1 Sciences
  - UEs LMD completes par filiere/semestre avec credits ECTS
  - 149 Etudiants avec profils realistes
  - Notes UE S1 completes (cloturees) + S2 partielles (en cours)
  - 60 jours de presences simulees par classe
  - Paiements : inscription + scolarite (complets, partiels, impayes)
  - Tranches d echeances generees
  - 12 comptes utilisateurs
  - Modele de releve de notes LMD personnalise

Usage : python setup_universite_demo.py [--reset]
  --reset : supprime d abord l etablissement existant avant de recreer
"""
import os, sys, django, random, datetime

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'smartschool.settings')
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
django.setup()

from decimal import Decimal
from django.utils import timezone
from accounts.models import User
from etablissements.models import (
    Etablissement, AnneeScolaire, Niveau, Classe,
    Enseignant, ParametreEtablissement,
    ModeleDocument, Cycle, CycleActif, UEUniversite
)
from eleves.models import Eleve, Tuteur, Inscription, Presence
from finances.models import TypeFrais, Paiement, Echeance
from notes.models import Matiere, Periode, NoteUE

random.seed(2024)

RESET = '--reset' in sys.argv
if RESET:
    print("Suppression de l ancien etablissement UCADB...")
    Etablissement.objects.filter(code='UCADB').delete()
    User.objects.filter(username__endswith='_ucadb').delete()
    print("   Fait.\n")

PRENOMS_M = ['Amadou','Moussa','Ibrahim','Seydou','Boubacar','Oumar','Mamadou',
    'Souleymane','Abdoulaye','Cheick','Modibo','Lassina','Dramane','Adama',
    'Fousseyni','Ismail','Yacouba','Issa','Hamidou','Bakary','Alou','Drissa',
    'Sidiki','Youssouf','Aboubacar','Moulaye','Tiemoko','Samba']
PRENOMS_F = ['Fatoumata','Aminata','Mariam','Kadiatou','Rokia','Oumou','Djeneba',
    'Nana','Aissata','Bintou','Korotoumou','Salimata','Hawa','Maimouna',
    'Fanta','Safiatou','Awa','Kadidiatou','Ramata','Sita','Tenin','Ramatou',
    'Sanata','Nene','Coumba','Diata']
NOMS = ['Coulibaly','Diallo','Traore','Konate','Keita','Dembele','Sangare',
    'Camara','Bah','Sidibe','Kouyate','Diarra','Sissoko','Toure','Maiga',
    'Cisse','Doumbia','Bagayoko','Fofana','Diabate','Kone','Samake',
    'Goita','Bore','Sylla','Gassama','Ndiaye']
VILLES = ['Bamako','Sikasso','Mopti','Segou','Kayes','Gao','Koutiala',
          'Bougouni','San','Djenne','Tombouctou','Niono']
QUARTIERS = ['Lafiabougou','Hippodrome','Faladie','Badalabougou','Kalaban',
             'Magnambougou','Banankabougou','Missira','Niarela','Hamdallaye']
PROFESSIONS = ['Commercant','Fonctionnaire','Enseignant','Medecin',
               'Ingenieur','Agriculteur','Entrepreneur','Journaliste']

def nom_aleat(sexe):
    return random.choice(NOMS), random.choice(PRENOMS_M if sexe=='M' else PRENOMS_F)

def ddn_univ():
    return datetime.date(random.randint(1996,2006), random.randint(1,12), random.randint(1,28))

UES_INFO = {
    1:[('INFO101','Algorithmique et Structures de Donnees',4,2),
       ('INFO102','Programmation C/C++',4,2),
       ('INFO103','Mathematiques Discretes',3,1),
       ('INFO104','Architecture des Ordinateurs',3,1),
       ('INFO105',"Systemes d'Exploitation I",3,1),
       ('LANG101','Anglais Technique I',3,1)],
    2:[('INFO201','Bases de Donnees Relationnelles',4,2),
       ('INFO202','Developpement Web HTML/CSS/JS',4,2),
       ('INFO203','Reseaux Informatiques I',3,1),
       ('INFO204','Probabilites et Statistiques',3,1),
       ('INFO205',"Systemes d'Exploitation II",3,1),
       ('LANG201','Anglais Technique II',3,1)],
    3:[('INFO301','Genie Logiciel et UML',4,2),
       ('INFO302','Programmation Java OO',4,2),
       ('INFO303','Reseaux et Securite',3,1),
       ('INFO304','Intelligence Artificielle I',3,1),
       ('INFO305','Bases de Donnees Avancees',3,1),
       ('INFO306','Projet Individuel',3,1)],
    4:[('INFO401','Developpement Mobile Android',4,2),
       ('INFO402','Cloud Computing et DevOps',3,1),
       ('INFO403','Intelligence Artificielle II',3,1),
       ('INFO404','Entrepreneuriat Numerique',3,1),
       ('INFO405','Stage et Rapport',4,2),
       ('INFO406','Projet de Fin de Licence',3,1)],
    5:[('INFO501','Architecture Logicielle',4,2),
       ('INFO502','Big Data et Analytics',4,2),
       ('INFO503','Cybersecurite Avancee',3,1),
       ('INFO504','Gestion de Projet IT',3,1),
       ('INFO505','Memoire de Recherche',4,2),
       ('INFO506','Seminaire Professionnel',2,1)],
    6:[('INFO601','Systemes Distribues',4,2),
       ('INFO602','Machine Learning Applique',4,2),
       ('INFO603','Entrepreneuriat et Startup',3,1),
       ("INFO604","Stage de Fin d'Etudes",4,2),
       ('INFO605','Soutenance de Memoire',5,2)],
}
UES_GEST = {
    1:[('GEST101','Introduction a la Gestion',4,2),
       ('GEST102','Comptabilite Generale I',4,2),
       ('GEST103','Droit des Affaires I',3,1),
       ('GEST104','Mathematiques Financieres',3,1),
       ('GEST105','Microeconomie',3,1),
       ('LANG111','Francais des Affaires',3,1)],
    2:[('GEST201','Comptabilite Generale II',4,2),
       ('GEST202','Marketing Fondamental',4,2),
       ('GEST203','Gestion des Ressources Humaines',3,1),
       ('GEST204','Macroeconomie',3,1),
       ('GEST205','Statistiques Appliquees',3,1),
       ('GEST206','Fiscalite des Entreprises',3,1)],
    3:[('GEST301',"Finance d'Entreprise",4,2),
       ('GEST302','Gestion de Production',3,1),
       ('GEST303','Commerce International',3,1),
       ('GEST304',"Systeme d'Information",3,1),
       ('GEST305','Gestion de Projet',3,1),
       ('GEST306','Stage et Memoire L2',4,2)],
    4:[('GEST401','Comptabilite Analytique',4,2),
       ('GEST402','Audit et Controle de Gestion',4,2),
       ('GEST403','Management Strategique',3,1),
       ('GEST404','Gestion Bancaire',3,1),
       ('GEST405','Stage et Soutenance L3',4,2)],
}
UES_DROIT = {
    1:[('DROIT101','Introduction au Droit',4,2),
       ('DROIT102','Droit Civil I - Personnes',4,2),
       ('DROIT103','Institutions Judiciaires',3,1),
       ('DROIT104','Histoire du Droit',3,1),
       ('DROIT105','Economie Politique I',3,1),
       ('DROIT106','Methodologie Juridique',3,1)],
    2:[('DROIT201','Droit Civil II - Obligations',4,2),
       ('DROIT202','Droit Constitutionnel',4,2),
       ('DROIT203','Droit Administratif I',3,1),
       ('DROIT204','Droit Penal General',3,1),
       ('DROIT205','Droit Commercial I',3,1),
       ('DROIT206','Economie Politique II',3,1)],
    3:[('DROIT301','Droit du Travail',4,2),
       ('DROIT302','Droit International Public',3,1),
       ('DROIT303','Procedure Civile',3,1),
       ('DROIT304','Droit des Societes',3,1),
       ('DROIT305','Stage et Rapport',4,2)],
    4:[('DROIT401','Droit Fiscal',4,2),
       ('DROIT402','Droit International Prive',3,1),
       ('DROIT403','Criminologie',3,1),
       ("DROIT404","Droit de l'Environnement",3,1),
       ("DROIT405","Memoire de Fin d'Etudes",5,2)],
}
UES_MED = {
    1:[('MED101','Anatomie I',5,3),('MED102','Biologie Cellulaire',4,2),
       ('MED103','Biophysique Medicale',4,2),('MED104','Chimie Biologique',3,1),
       ('MED105','Histologie I',3,1),('MED106','Psychologie Medicale',2,1)],
    2:[('MED201','Anatomie II',5,3),('MED202','Physiologie I',4,2),
       ('MED203','Biochimie Structurale',4,2),('MED204','Histologie II',3,1),
       ('MED205','Semiologie Generale',3,1),('MED206','Ethique Medicale',2,1)],
}
UES_SCI = {
    1:[('SCI101','Mathematiques I - Analyse',4,2),('SCI102','Physique I - Mecanique',4,2),
       ('SCI103','Chimie Generale',3,1),('SCI104','Biologie Generale',3,1),
       ('SCI105','Informatique Scientifique',3,1),('SCI106','Geologie Generale',3,1)],
    2:[('SCI201','Mathematiques II - Algebre',4,2),('SCI202','Physique II - Electricite',4,2),
       ('SCI203','Chimie Organique',3,1),('SCI204','Genetique',3,1),
       ('SCI205','Statistiques et Probabilites',3,1),('SCI206','Environnement et Ecologie',3,1)],
}

print("=" * 65)
print("  SMARTSCHOOL - DEMO UNIVERSITE COMPLETE v2")
print("=" * 65)

# [1] Etablissement
print("\n[1/12] Creation de l universite...")
univ, cr = Etablissement.objects.get_or_create(code='UCADB', defaults={
    'nom': 'Universite Cheikh Anta Diop de Bamako',
    'type': 'universite',
    'adresse': "Boulevard de l'Independance, Bamako, Mali",
    'telephone': '+223 20 22 56 00',
    'email': 'contact@ucadb.edu.ml',
    'directeur': 'Prof. Mamadou Kouyate',
    'slogan': 'La connaissance au service du developpement',
    'couleur_principale': '#1B5E20',
    'couleur_secondaire': '#2E7D32',
})
print(f"   {'Creee' if cr else 'Existante'}: {univ.nom}")

ParametreEtablissement.objects.get_or_create(etablissement=univ, defaults={
    'devise': 'FCFA', 'type_periode': 'semestre',
    'note_passage': 10, 'note_max': 20,
})


# [2] Annee
print("\n[2/12] Annee scolaire 2025-2026...")
annee, _ = AnneeScolaire.objects.get_or_create(
    etablissement=univ, libelle='2025-2026',
    defaults={'date_debut': datetime.date(2025,10,1),
              'date_fin': datetime.date(2026,7,31), 'is_active': True}
)
if not annee.is_active:
    annee.is_active = True; annee.save()

# [3] Cycle LMD
print("\n[3/12] Cycle LMD...")
cycle_lmd, _ = Cycle.objects.get_or_create(etablissement=univ, type_cycle='universite', defaults={
    'nom': 'Licence LMD', 'mode_calcul': 'credit'
})
CycleActif.objects.get_or_create(etablissement=univ, cycle=cycle_lmd)

# [4] Niveaux
print("\n[4/12] Niveaux L1/L2/L3...")
niveaux = {}
for i, n in enumerate(['Licence 1 (L1)','Licence 2 (L2)','Licence 3 (L3)'], 1):
    nv, _ = Niveau.objects.get_or_create(etablissement=univ, nom=n,
        defaults={'cycle': cycle_lmd, 'ordre': i})
    niveaux[f'L{i}'] = nv

# [5] Semestres
print("\n[5/12] Semestres S1 et S2...")
sem1, _ = Periode.objects.get_or_create(etablissement=univ, annee=annee, numero=1, defaults={
    'type':'semestre','libelle':'Semestre 1 (S1)',
    'date_debut':datetime.date(2025,10,1),'date_fin':datetime.date(2026,1,31),
    'is_active':False,'saisie_cloturee':True})
sem2, _ = Periode.objects.get_or_create(etablissement=univ, annee=annee, numero=2, defaults={
    'type':'semestre','libelle':'Semestre 2 (S2)',
    'date_debut':datetime.date(2026,2,1),'date_fin':datetime.date(2026,6,30),
    'is_active':True,'saisie_cloturee':False})
print("   S1 (cloture) + S2 (en cours)")

# [6] Comptes
print("\n[6/12] Comptes utilisateurs (12)...")
def creer_user(un, fn, ln, role):
    u, c = User.objects.get_or_create(username=un, defaults={
        'first_name':fn,'last_name':ln,'role':role,
        'email':f'{un}@ucadb.edu.ml'})
    u.etablissement = univ
    u.role = role
    u.set_password('passer123')
    u.save()
    return u

dir_u      = creer_user('dir_ucadb',        'Mamadou',   'Kouyate',  'admin')
sec1_u     = creer_user('sec1_ucadb',       'Kadiatou',  'Diallo',   'secretariat')
sec2_u     = creer_user('sec2_ucadb',       'Fatoumata', 'Traore',   'secretariat')
compt_u    = creer_user('compt_ucadb',      'Seydou',    'Konate',   'comptable')
surv_u     = creer_user('surv_ucadb',       'Boubacar',  'Sissoko',  'surveillant')
prof_info1 = creer_user('prof_info1_ucadb', 'Oumar',     'Coulibaly','enseignant')
prof_info2 = creer_user('prof_info2_ucadb', 'Ibrahim',   'Dembele',  'enseignant')
prof_gest1 = creer_user('prof_gest1_ucadb', 'Aminata',   'Sangare',  'enseignant')
prof_gest2 = creer_user('prof_gest2_ucadb', 'Modibo',    'Diarra',   'enseignant')
prof_droit = creer_user('prof_droit_ucadb', 'Souleymane','Bagayoko', 'enseignant')
prof_med   = creer_user('prof_med_ucadb',   'Hawa',      'Sidibe',   'enseignant')
prof_sci   = creer_user('prof_sci_ucadb',   'Dramane',   'Toure',    'enseignant')

def creer_ens(u, sp):
    Enseignant.objects.get_or_create(user=u, etablissement=univ,
        defaults={'specialite':sp,'statut':'actif','date_embauche':datetime.date(2020,9,1)})

creer_ens(prof_info1,'Informatique - Algorithmique et Reseaux')
creer_ens(prof_info2,'Informatique - BDD et Developpement Web')
creer_ens(prof_gest1,'Gestion - Finance et Comptabilite')
creer_ens(prof_gest2,'Gestion - Marketing et RH')
creer_ens(prof_droit,'Droit - Droit Civil et Commercial')
creer_ens(prof_med,  'Medecine - Anatomie et Physiologie')
creer_ens(prof_sci,  'Sciences - Mathematiques et Physique')
print("   12 comptes crees (passer123)")

# [7] Classes
print("\n[7/12] Classes (5 filieres, 9 classes)...")
classes_def = [
    ('L1 Informatique','L1','Informatique',2,22),
    ('L2 Informatique','L2','Informatique',4,18),
    ('L3 Informatique','L3','Informatique',6,14),
    ('L1 Gestion',     'L1','Gestion',     2,20),
    ('L2 Gestion',     'L2','Gestion',     4,15),
    ('L1 Droit',       'L1','Droit',       2,18),
    ('L2 Droit',       'L2','Droit',       4,12),
    ('L1 Medecine',    'L1','Medecine',    2,16),
    ('L1 Sciences',    'L1','Sciences',    2,14),
]
classes = {}
for nom, nk, fil, sa, _ in classes_def:
    cl, _ = Classe.objects.get_or_create(etablissement=univ, annee=annee, nom=nom,
        defaults={'niveau':niveaux[nk],'filiere':fil,'semestre_actif':sa,'capacite_max':30})
    classes[nom] = cl
    print(f"   {nom} ({fil})")

# [8] UEs
print("\n[8/12] Unites d Enseignement...")
all_ues = {}
def creer_ues(ues_d, fil):
    nb = 0
    for sem, lst in ues_d.items():
        for code, intit, cred, coef in lst:
            ue, _ = UEUniversite.objects.get_or_create(cycle=cycle_lmd, code=code,
                defaults={'nom':intit,'credits':cred,'coefficient':coef,'semestre':sem})
            all_ues[code] = ue; nb += 1
    return nb

nb_ues = sum([creer_ues(d,f) for d,f in [
    (UES_INFO,'Informatique'),(UES_GEST,'Gestion'),(UES_DROIT,'Droit'),
    (UES_MED,'Medecine'),(UES_SCI,'Sciences')]])
print(f"   {nb_ues} UEs creees")

# [9] Etudiants
print("\n[9/12] Etudiants, tuteurs et inscriptions...")
def creer_etudiants(nom_cl, nb):
    cl = classes[nom_cl]; ets = []
    for _ in range(nb):
        sx = 'F' if random.random()<0.38 else 'M'
        nom, prenom = nom_aleat(sx)
        tel = f"+22370{random.randint(1000000,9999999)}"
        sx_t = 'M' if random.random()<0.65 else 'F'
        tn, tp = nom_aleat(sx_t)
        tut, _ = Tuteur.objects.get_or_create(etablissement=univ, telephone=tel,
            defaults={'nom':tn,'prenom':tp,'lien':random.choice(['pere','mere','tuteur']),
                      'telephone':tel,'profession':random.choice(PROFESSIONS)})
        el = Eleve(etablissement=univ, nom=nom, prenom=prenom, sexe=sx,
            date_naissance=ddn_univ(), lieu_naissance=random.choice(VILLES),
            adresse=f"Quartier {random.choice(QUARTIERS)}, Bamako",
            telephone=f"+22376{random.randint(1000000,9999999)}",
            tuteur=tut, is_active=True)
        el.save()
        Inscription.objects.get_or_create(eleve=el, annee=annee,
            defaults={'classe':cl,'statut':'actif','is_active':True})
        ets.append(el)
    return ets

etudiants_map = {}
for nc, nk, fil, sa, nb in classes_def:
    print(f"   {nc}: {nb} etudiants...")
    etudiants_map[nc] = creer_etudiants(nc, nb)
total_et = sum(len(v) for v in etudiants_map.values())
print(f"   Total: {total_et} etudiants inscrits")

# [10] Notes
print("\n[10/12] Notes UE (S1 complet + S2 partiel)...")
def note_p(niveau='moyen'):
    r = random.random()
    if niveau=='fort':
        if r<0.05: return round(random.uniform(4,9.9),2)
        elif r<0.20: return round(random.uniform(10,11.9),2)
        elif r<0.45: return round(random.uniform(12,13.9),2)
        elif r<0.75: return round(random.uniform(14,15.9),2)
        else: return round(random.uniform(16,19.5),2)
    elif niveau=='faible':
        if r<0.30: return round(random.uniform(2,7.9),2)
        elif r<0.55: return round(random.uniform(8,9.9),2)
        elif r<0.80: return round(random.uniform(10,12),2)
        else: return round(random.uniform(12,15),2)
    else:
        if r<0.15: return round(random.uniform(4,9.9),2)
        elif r<0.35: return round(random.uniform(10,11.9),2)
        elif r<0.60: return round(random.uniform(12,13.9),2)
        elif r<0.82: return round(random.uniform(14,15.9),2)
        else: return round(random.uniform(16,19.5),2)

def saisir_notes(ets, cl, codes, periode, prof, complet=True, profil='moyen'):
    nb = 0
    ues = [all_ues[c] for c in codes if c in all_ues]
    ets2 = ets if complet else random.sample(ets, max(1,int(len(ets)*0.55)))
    for el in ets2:
        ues_s = ues if complet else random.sample(ues, max(1,int(len(ues)*random.uniform(0.6,1.0))))
        for ue in ues_s:
            n = Decimal(str(note_p(profil)))
            ratt = None
            if float(n)<10 and random.random()>0.30:
                ratt = Decimal(str(round(random.uniform(8.0,16.0),2)))
            NoteUE.objects.get_or_create(eleve=el, ue=ue, classe=cl, periode=periode,
                defaults={'note':n,'note_rattrapage':ratt,'saisi_par':prof})
            nb += 1
    return nb

configs = [
    ('L1 Informatique',[c for c,*_ in UES_INFO[1]],[c for c,*_ in UES_INFO[2]],prof_info1,'moyen'),
    ('L2 Informatique',[c for c,*_ in UES_INFO[3]],[c for c,*_ in UES_INFO[4]],prof_info2,'fort'),
    ('L3 Informatique',[c for c,*_ in UES_INFO[5]],[c for c,*_ in UES_INFO[6]],prof_info1,'fort'),
    ('L1 Gestion',     [c for c,*_ in UES_GEST[1]],[c for c,*_ in UES_GEST[2]],prof_gest1,'moyen'),
    ('L2 Gestion',     [c for c,*_ in UES_GEST[3]],[c for c,*_ in UES_GEST[4]],prof_gest2,'moyen'),
    ('L1 Droit',       [c for c,*_ in UES_DROIT[1]],[c for c,*_ in UES_DROIT[2]],prof_droit,'faible'),
    ('L2 Droit',       [c for c,*_ in UES_DROIT[3]],[c for c,*_ in UES_DROIT[4]],prof_droit,'moyen'),
    ('L1 Medecine',    [c for c,*_ in UES_MED[1]], [c for c,*_ in UES_MED[2]], prof_med, 'faible'),
    ('L1 Sciences',    [c for c,*_ in UES_SCI[1]], [c for c,*_ in UES_SCI[2]], prof_sci, 'moyen'),
]

total_notes = 0
for nc, cs1, cs2, prof, profil in configs:
    cl = classes[nc]; ets = etudiants_map[nc]
    n1 = saisir_notes(ets,cl,cs1,sem1,prof,True,profil)
    n2 = saisir_notes(ets,cl,cs2,sem2,prof,False,profil)
    total_notes += n1+n2
    print(f"   {nc}: {n1} notes S1 + {n2} notes S2")
print(f"   Total: {total_notes} notes saisies")

# [11] Presences
print("\n[11/12] Presences (60 jours)...")
def jours_ouvr(debut, nb):
    jrs=[]; d=debut
    while len(jrs)<nb:
        if d.weekday()<5: jrs.append(d)
        d+=datetime.timedelta(days=1)
    return jrs

jours_s1 = jours_ouvr(datetime.date(2025,10,6), 40)
jours_s2 = jours_ouvr(datetime.date(2026,2,2),  20)
tous_jours = jours_s1 + jours_s2

total_presences = 0
for nc, ets in etudiants_map.items():
    cl = classes[nc]
    # Recup les presences existantes pour eviter les doublons
    existantes = set(
        Presence.objects.filter(classe=cl, date__in=tous_jours)
        .values_list('eleve_id', 'date')
    )
    batch = []
    for eleve in ets:
        for jour in tous_jours:
            if (eleve.pk, jour) not in existantes:
                r = random.random()
                if r<0.84:   st='present'
                elif r<0.91: st='absent'
                elif r<0.96: st='retard'
                else:        st='justifie'
                batch.append(Presence(
                    eleve=eleve, classe=cl, date=jour, statut=st,
                    enregistre_par=surv_u,
                    motif='Maladie' if st=='justifie' else ''
                ))
    if batch:
        Presence.objects.bulk_create(batch, ignore_conflicts=True)
        total_presences += len(batch)
    print(f"   {nc}: {len(batch)} presences")
print(f"   Total: {total_presences} enregistrements de presence")

# [12] Finances
print("\n[12/12] Finances (frais, paiements, echeances)...")
tf_insc, _ = TypeFrais.objects.get_or_create(
    etablissement=univ, nom="Frais d'Inscription", annee=annee,
    defaults={'montant_defaut':50000,'is_obligatoire':True,'periodicite':'unique'})
tf_scol, _ = TypeFrais.objects.get_or_create(
    etablissement=univ, nom='Frais de Scolarite', annee=annee,
    defaults={'montant_defaut':350000,'is_obligatoire':True,'periodicite':'tranches','nombre_tranches':3})
tf_bib, _ = TypeFrais.objects.get_or_create(
    etablissement=univ, nom='Frais de Bibliotheque', annee=annee,
    defaults={'montant_defaut':15000,'is_obligatoire':False,'periodicite':'unique'})
tf_tp, _ = TypeFrais.objects.get_or_create(
    etablissement=univ, nom='Frais de Travaux Pratiques', annee=annee,
    defaults={'montant_defaut':25000,'is_obligatoire':False,'periodicite':'unique'})

TRANCHES = [
    (1,'Tranche 1',116667,datetime.date(2025,10,31)),
    (2,'Tranche 2',116667,datetime.date(2026,1,31)),
    (3,'Tranche 3',116666,datetime.date(2026,4,30)),
]

today = datetime.date.today()  # necessaire pour calculer statut echeances

# Collecte toutes les insertions en batch
batch_paie = []
batch_ech  = []

for nc, ets in etudiants_map.items():
    for eleve in ets:
        rp = random.random()
        if rp<0.80:
            batch_paie.append(Paiement(
                etablissement=univ,eleve=eleve,annee=annee,type_frais=tf_insc,
                montant=50000,mode_paiement=random.choice(['especes','mobile_money']),
                statut='valide',encaisse_par=compt_u,
                date_paiement=timezone.make_aware(datetime.datetime(2025,10,random.randint(1,20)))))
        if random.random()<0.60:
            batch_paie.append(Paiement(
                etablissement=univ,eleve=eleve,annee=annee,type_frais=tf_bib,
                montant=15000,mode_paiement='especes',statut='valide',
                encaisse_par=compt_u,
                date_paiement=timezone.make_aware(datetime.datetime(2025,10,random.randint(1,28)))))
        if nc in ('L1 Informatique','L2 Informatique','L1 Medecine','L1 Sciences') and random.random()<0.45:
            batch_paie.append(Paiement(
                etablissement=univ,eleve=eleve,annee=annee,type_frais=tf_tp,
                montant=25000,mode_paiement=random.choice(['especes','mobile_money']),
                statut='valide',encaisse_par=compt_u,
                date_paiement=timezone.make_aware(datetime.datetime(2025,11,random.randint(1,28)))))
        nb_tranches_ok=(3 if rp<0.40 else 2 if rp<0.75 else 1 if rp<0.90 else 0)
        for num,label,montant,dlim in TRANCHES:
            paid = num<=nb_tranches_ok
            st_e = 'payee' if paid else ('retard' if dlim<today else 'a_payer')
            if paid:
                dp = timezone.make_aware(datetime.datetime(dlim.year,dlim.month,random.randint(1,min(dlim.day,28))))
                batch_paie.append(Paiement(
                    etablissement=univ,eleve=eleve,annee=annee,type_frais=tf_scol,
                    montant=montant,mode_paiement=random.choice(['especes','mobile_money','virement']),
                    statut='valide',periode_payee=label,encaisse_par=compt_u,date_paiement=dp))
            batch_ech.append(Echeance(
                etablissement=univ,eleve=eleve,annee=annee,type_frais=tf_scol,
                numero=num,libelle=label,montant=montant,date_limite=dlim,
                statut=st_e,date_paiement=timezone.now() if paid else None))

# Insertion en masse
nb_paie = len(batch_paie)
nb_ech  = len(batch_ech)
Paiement.objects.bulk_create(batch_paie, ignore_conflicts=True)
Echeance.objects.bulk_create(batch_ech,  ignore_conflicts=True)
print(f"   {nb_paie} paiements  |  {nb_ech} echeances")

ModeleDocument.objects.get_or_create(
    etablissement=univ, type_document='releve_notes', nom='Releve LMD Officiel UCADB',
    defaults={
        'is_actif':True,'afficher_logo':True,
        'ligne1_gauche':"MINISTERE DE L'ENSEIGNEMENT SUPERIEUR ET DE LA RECHERCHE",
        'ligne2_gauche':'UNIVERSITE CHEIKH ANTA DIOP DE BAMAKO (UCADB)',
        'ligne3_gauche':'Sous-Direction des Affaires Academiques',
        'ligne1_droite':'Republique du Mali',
        'ligne2_droite':'Un Peuple - Un But - Une Foi',
        'ligne3_droite':f'Annee Universitaire {annee.libelle}',
        'titre_document':'RELEVE DE NOTES - SYSTEME LMD',
        'couleur_titre_bg':'#1B5E20','couleur_titre_texte':'#FFFFFF',
        'couleur_tableau_header':'#E8F5E9','couleur_bordure':'#2E7D32',
        'police':'Times New Roman','taille_police':12,'afficher_rang':False,
        'label_signature_gauche':'Le Chef de Departement',
        'label_signature_droite':'Le Doyen de la Faculte',
        'texte_pied_page':"Ce document est un releve de notes officiel certifie par le Service des Affaires Academiques de l'UCADB.",
        'afficher_date':True,
    }
)

print("\n" + "="*65)
print("  DEMO UNIVERSITE CREEE AVEC SUCCES !")
print("="*65)
print(f"  Etablissement : {univ.nom}")
print(f"  Filieres      : Informatique, Gestion, Droit, Medecine, Sciences")
print(f"  Classes       : {len(classes_def)} classes (L1/L2/L3)")
print(f"  Etudiants     : {total_et}")
print(f"  Notes UE      : {total_notes} (S1 complet + S2 partiel)")
print(f"  Presences     : {total_presences} enregistrements (60 jours)")
print(f"  Paiements     : {nb_paie} paiements / {nb_ech} echeances")
print()
print("  COMPTES (mot de passe : passer123)")
print("  " + "-"*42)
print("  dir_ucadb         -> Directeur / Admin")
print("  sec1_ucadb        -> Secretariat 1")
print("  sec2_ucadb        -> Secretariat 2")
print("  compt_ucadb       -> Comptable")
print("  surv_ucadb        -> Surveillant General")
print("  prof_info1_ucadb  -> Enseignant Info (Algo/Reseaux)")
print("  prof_info2_ucadb  -> Enseignant Info (BDD/Web)")
print("  prof_gest1_ucadb  -> Enseignant Gestion (Finance)")
print("  prof_gest2_ucadb  -> Enseignant Gestion (Marketing)")
print("  prof_droit_ucadb  -> Enseignant Droit")
print("  prof_med_ucadb    -> Enseignant Medecine")
print("  prof_sci_ucadb    -> Enseignant Sciences")
print("  " + "-"*42)
print()
print("  URLs :")
print("  http://127.0.0.1:8000/auth/login/")
print("  http://127.0.0.1:8000/eleves/")
print("  http://127.0.0.1:8000/notes/universite/saisie/")
print("  http://127.0.0.1:8000/notes/bulletins/")
print("  http://127.0.0.1:8000/finances/")
print("  http://127.0.0.1:8000/eleves/appel/")
print()
print("  Relancer avec --reset pour repartir de zero")
print("="*65)
