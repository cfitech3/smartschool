"""
SmartSchool ERP - Completion demos tous etablissements
"""
import os, sys, django, random, datetime
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'smartschool.settings')
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
django.setup()

from decimal import Decimal
from accounts.models import User
from etablissements.models import (
    Etablissement, AnneeScolaire, Niveau, Classe,
    Enseignant, AffectationMatiere, ParametreEtablissement,
    Cycle, CycleActif, UEUniversite
)
from eleves.models import Eleve, Inscription
from finances.models import TypeFrais, Paiement
from notes.models import Matiere, Periode, NotePeriode, NoteUE

random.seed(2026)

PRENOMS_M = ['Amadou','Moussa','Ibrahim','Seydou','Boubacar','Oumar','Mamadou','Souleymane','Abdoulaye','Cheick','Modibo','Lassina','Dramane','Adama']
PRENOMS_F = ['Fatoumata','Aminata','Mariam','Kadiatou','Rokia','Oumou','Djeneba','Nana','Aissata','Bintou','Korotoumou','Salimata','Hawa','Maimouna']
NOMS = ['Coulibaly','Diallo','Traore','Konate','Keita','Dembele','Sangare','Camara','Bah','Sidibe','Kouyate','Diarra','Sissoko','Toure','Maiga']
VILLES = ['Bamako','Sikasso','Mopti','Segou','Kayes','Gao']
QUARTIERS = ['Lafiabougou','Hippodrome','Faladie','Badalabougou','Kalaban']

_cnts = {}
def mat_unique(p):
    _cnts[p] = _cnts.get(p,0)+1
    return f"{p}{datetime.date.today().year}{_cnts[p]:04d}"

def ddn(a=14,b=20):
    y=datetime.date.today().year-random.randint(a,b)
    return datetime.date(y,random.randint(1,12),random.randint(1,28))

def ddn_univ():
    return datetime.date(random.randint(1996,2007),random.randint(1,12),random.randint(1,28))

def note():
    return Decimal(str(round(random.uniform(4,19),2)))

def creer_el(etab, prefix, age_min=14, age_max=20):
    sx = random.choice(['M','F'])
    nom = random.choice(NOMS)
    prenom = random.choice(PRENOMS_M if sx=='M' else PRENOMS_F)
    mat = mat_unique(prefix)
    while Eleve.objects.filter(matricule=mat).exists():
        mat = mat_unique(prefix)
    return Eleve.objects.create(
        etablissement=etab, nom=nom, prenom=prenom, sexe=sx, matricule=mat,
        date_naissance=ddn(age_min, age_max),
        lieu_naissance=random.choice(VILLES),
        adresse=f"{random.choice(QUARTIERS)}, {random.choice(VILLES)}",
        is_active=True,
    )

def creer_ens(etab, prenom, nom, username, spec='', diplome='Licence'):
    u, c = User.objects.get_or_create(username=username, defaults={
        'first_name':prenom,'last_name':nom,'role':'enseignant','etablissement':etab})
    if c:
        u.set_password('passer123'); u.save()
    ens, _ = Enseignant.objects.get_or_create(user=u, etablissement=etab,
        defaults={'specialite':spec,'diplome':diplome,'statut':'actif'})
    return ens

print('='*55)
print('  SmartSchool - Completion des demos')
print('='*55)

# =========================================================
# 1. LYCEE d Excellence
# =========================================================
print('\n[1/3] LYCEE (LYC-EXC)')
lycee = Etablissement.objects.get(code='LYC-EXC')
annee_lyc = AnneeScolaire.objects.filter(etablissement=lycee, is_active=True).first()
cycle_lyc = Cycle.objects.filter(etablissement=lycee).first()

# Classes supplementaires
niv_sec  = Niveau.objects.filter(etablissement=lycee, nom='Seconde').first()
niv_prem = Niveau.objects.filter(etablissement=lycee, nom='Premiere').first()
niv_term, _ = Niveau.objects.get_or_create(etablissement=lycee, nom='Terminale',
    defaults={'cycle': cycle_lyc, 'ordre': 12})

cls = []
for nom_cl, niv in [
    ('10eme Commune A', niv_sec), ('10eme Commune B', niv_sec),
    ('11eme Lettres', niv_prem), ('11eme Sciences', niv_prem),
    ('Terminale Sciences', niv_term), ('Terminale Lettres', niv_term),
]:
    if niv:
        cl, _ = Classe.objects.get_or_create(etablissement=lycee, annee=annee_lyc, nom=nom_cl,
            defaults={'niveau': niv})
        cls.append(cl)
print(f'  {len(cls)} classes')

# Matieres
MAT_LYCEE = [
    ('Mathematiques','MATH',4), ('Physique-Chimie','PC',3),
    ('Sciences de la Vie','SVT',2), ('Francais','FR',3),
    ('Histoire-Geographie','HG',2), ('Anglais','ANG',2),
    ('Philosophie','PHILO',2), ('Education Civique','EC',1),
    ('Sport','EPS',1), ('Conduite','COND',1),
]
mats = {}
for nom_m, code_m, coef_m in MAT_LYCEE:
    m, _ = Matiere.objects.get_or_create(etablissement=lycee, nom=nom_m,
        defaults={'code':code_m,'coefficient':coef_m,'is_conduite':(code_m=='COND')})
    mats[code_m] = m
print(f'  {len(mats)} matieres')

# Periodes
p1, _ = Periode.objects.get_or_create(etablissement=lycee, annee=annee_lyc, libelle='1er Trimestre',
    defaults={'numero':1,'date_debut':datetime.date(2024,10,1),'date_fin':datetime.date(2024,12,20),
              'is_active':True,'saisie_cloturee':False,'saisie_cloturee':False})
p2, _ = Periode.objects.get_or_create(etablissement=lycee, annee=annee_lyc, libelle='2eme Trimestre',
    defaults={'numero':2,'date_debut':datetime.date(2025,1,6),'date_fin':datetime.date(2025,3,28),
              'is_active':False,'saisie_cloturee':False,'saisie_cloturee':False})
p3, _ = Periode.objects.get_or_create(etablissement=lycee, annee=annee_lyc, libelle='3eme Trimestre',
    defaults={'numero':3,'date_debut':datetime.date(2025,4,7),'date_fin':datetime.date(2025,6,30),
              'is_active':False,'saisie_cloturee':False,'saisie_cloturee':False})
print('  3 periodes')

# Enseignants
ens_math = creer_ens(lycee,'Boubacar','Diarra','prof_math_lyc',spec='Mathematiques',diplome='CAPES')
ens_fr   = creer_ens(lycee,'Aminata','Kone','prof_fr_lyc',spec='Lettres',diplome='CAPES')
ens_sc   = creer_ens(lycee,'Ibrahim','Coulibaly','prof_sc_lyc',spec='Sciences',diplome='Master')
ens_hg   = creer_ens(lycee,'Fatoumata','Traore','prof_hg_lyc',spec='Histoire',diplome='Licence')
ens_ang  = creer_ens(lycee,'Seydou','Bah','prof_ang_lyc',spec='Anglais',diplome='CAPES')

for uname,prenom,nom,role in [
    ('sec_lyc','Mariam','Sissoko','secretariat'),
    ('surv_lyc','Oumar','Sangare','surveillant'),
    ('compt_lyc','Djeneba','Maiga','comptable'),
]:
    u,c = User.objects.get_or_create(username=uname,
        defaults={'first_name':prenom,'last_name':nom,'role':role,'etablissement':lycee})
    if c:
        u.set_password('passer123'); u.save()
print('  5 enseignants + equipe')

# Affectations
aff_cfg = [
    (ens_math,['MATH','PC']), (ens_fr,['FR','PHILO','EC']),
    (ens_sc,['SVT','EPS']), (ens_hg,['HG']), (ens_ang,['ANG']),
]
nb_aff = 0
for ens, codes in aff_cfg:
    for code in codes:
        m = mats.get(code)
        if not m: continue
        for cl in cls:
            _, c = AffectationMatiere.objects.get_or_create(
                enseignant=ens,classe=cl,matiere=m,annee=annee_lyc,
                defaults={'heures_semaine':3})
            if c: nb_aff+=1
print(f'  {nb_aff} affectations')

# Eleves
nb_el_lyc = 0
for cl in cls:
    actifs = cl.inscriptions.filter(is_active=True).count()
    for _ in range(max(0, 22-actifs)):
        el = creer_el(lycee, 'LYC')
        Inscription.objects.create(eleve=el,classe=cl,annee=annee_lyc,is_active=True)
        nb_el_lyc += 1
print(f'  {nb_el_lyc} eleves inscrits')

# Notes T1
mats_notes = [m for k,m in mats.items() if k!='COND']
nb_notes_lyc = 0
for cl in cls:
    for insc in cl.inscriptions.filter(is_active=True).select_related('eleve'):
        for mat in mats_notes:
            _, c = NotePeriode.objects.get_or_create(
                eleve=insc.eleve,matiere=mat,classe=cl,periode=p1,
                defaults={
                    'moy_classe':note(),'moy_compo':note(),
                    'note_max_classe':Decimal('20'),'note_max_compo':Decimal('20'),
                    'saisi_par':ens_math.user
                })
            if c: nb_notes_lyc+=1
print(f'  {nb_notes_lyc} notes T1')

# Finances
frais_lyc = [
    ('Frais de scolarite',Decimal('150000')),
    ('Frais inscription',Decimal('25000')),
    ('Activites parascolaires',Decimal('15000')),
]
f_objs_lyc = []
for lib,mont in frais_lyc:
    f,_ = TypeFrais.objects.get_or_create(etablissement=lycee,annee=annee_lyc,nom=lib,
        defaults={'montant_defaut':mont,'is_obligatoire':True})
    f_objs_lyc.append(f)

nb_pay_lyc = 0
for cl in cls:
    for insc in cl.inscriptions.filter(is_active=True).select_related('eleve'):
        for frais in f_objs_lyc:
            if Paiement.objects.filter(eleve=insc.eleve,type_frais=frais).exists(): continue
            r = random.random()
            if r<0.6: mont=frais.montant_defaut
            elif r<0.85: mont=frais.montant_defaut*Decimal('0.5')
            else: continue
            Paiement.objects.create(
                etablissement=lycee,annee=annee_lyc,eleve=insc.eleve,
                type_frais=frais,montant=mont,
                date_paiement=datetime.date(2024,random.randint(10,12),random.randint(1,28)),
                mode_paiement='especes',reference=f'LYC{random.randint(10000,99999)}')
            nb_pay_lyc+=1
print(f'  {nb_pay_lyc} paiements')
print(f'  OK LYC-EXC')

# =========================================================
# 2. UCADB - filieres vides
# =========================================================
print('\n[2/3] UCADB - filieres sans eleves')
ucadb = Etablissement.objects.get(code='UCADB')
annee_uc = AnneeScolaire.objects.filter(etablissement=ucadb,is_active=True).first()
sem1 = Periode.objects.filter(etablissement=ucadb,numero=1).first()
sem2 = Periode.objects.filter(etablissement=ucadb,numero=2).first()

CFGS_UC = [
    ('L1 Droit','prof_droit_ucadb',18,'UCDB'),
    ('L1 Gestion','prof_gest1_ucadb',20,'UCGS'),
    ('L1 Medecine','prof_med_ucadb',15,'UCMD'),
    ('L1 Sciences','prof_sci_ucadb',16,'UCSC'),
    ('L2 Droit','prof_droit_ucadb',14,'UCDB'),
    ('L2 Gestion','prof_gest2_ucadb',16,'UCGS'),
]

nb_etu_uc=0; nb_n_uc=0
ues_s1 = list(UEUniversite.objects.filter(semestre__in=[1,3,5]))[:4]
ues_s2 = list(UEUniversite.objects.filter(semestre__in=[2,4,6]))[:3]

for cnom,puser,nb,pref in CFGS_UC:
    cl = Classe.objects.filter(etablissement=ucadb,annee=annee_uc,nom=cnom).first()
    if not cl:
        print(f'  CLASSE MANQUANTE: {cnom}'); continue
    actifs = cl.inscriptions.filter(is_active=True).count()
    for _ in range(max(0,nb-actifs)):
        el = Eleve.objects.create(
            etablissement=ucadb,nom=random.choice(NOMS),
            prenom=random.choice(PRENOMS_M+PRENOMS_F),
            sexe=random.choice(['M','F']),matricule=mat_unique(pref),
            date_naissance=ddn_univ(),
            lieu_naissance=random.choice(VILLES),
            adresse=f"{random.choice(QUARTIERS)}, Bamako",is_active=True)
        Inscription.objects.create(eleve=el,classe=cl,annee=annee_uc,is_active=True)
        nb_etu_uc+=1
    prof = User.objects.filter(username=puser).first()
    for insc in cl.inscriptions.filter(is_active=True).select_related('eleve'):
        if sem1:
            for ue in ues_s1:
                n=Decimal(str(round(random.uniform(4,19),2)))
                ratt=None
                if float(n)<10 and random.random()>0.4:
                    ratt=Decimal(str(round(random.uniform(8,16),2)))
                _,c=NoteUE.objects.get_or_create(
                    eleve=insc.eleve,ue=ue,classe=cl,periode=sem1,
                    defaults={'note':n,'note_rattrapage':ratt,'saisi_par':prof})
                if c: nb_n_uc+=1
        if sem2 and random.random()<0.65:
            for ue in random.sample(ues_s2,max(1,len(ues_s2)-1)):
                n=Decimal(str(round(random.uniform(5,19),2)))
                _,c=NoteUE.objects.get_or_create(
                    eleve=insc.eleve,ue=ue,classe=cl,periode=sem2,
                    defaults={'note':n,'saisi_par':prof})
                if c: nb_n_uc+=1
    print(f'  {cnom}: {max(0,nb-actifs)} etudiants')

# Finances UCADB
frais_uc_list = [
    ("Frais d'inscription",Decimal('50000')),
    ('Scolarite annuelle',Decimal('300000')),
    ('Frais de bibliotheque',Decimal('10000')),
]
f_uc_objs=[]
for lib,mont in frais_uc_list:
    f,_=TypeFrais.objects.get_or_create(etablissement=ucadb,annee=annee_uc,nom=lib,
        defaults={'montant_defaut':mont,'is_obligatoire':True})
    f_uc_objs.append(f)

nb_pay_uc=0
for cl in Classe.objects.filter(etablissement=ucadb,annee=annee_uc):
    for insc in cl.inscriptions.filter(is_active=True).select_related('eleve'):
        for frais in f_uc_objs:
            if Paiement.objects.filter(eleve=insc.eleve,type_frais=frais).exists(): continue
            r=random.random()
            if r<0.55: mont=frais.montant_defaut
            elif r<0.80: mont=frais.montant_defaut*Decimal('0.5')
            else: continue
            Paiement.objects.create(
                etablissement=ucadb,annee=annee_uc,eleve=insc.eleve,
                type_frais=frais,montant=mont,
                date_paiement=datetime.date(2025,random.randint(1,9),random.randint(1,28)),
                mode_paiement='virement',reference=f'UC{random.randint(10000,99999)}')
            nb_pay_uc+=1

print(f'  {nb_etu_uc} etudiants + {nb_n_uc} notes + {nb_pay_uc} paiements')
print('  OK UCADB')

# =========================================================
# 3. EFBT - classes vides
# =========================================================
print('\n[3/3] EFBT - classes vides')
efbt = Etablissement.objects.get(code='EFBT')
annee_efbt = AnneeScolaire.objects.filter(etablissement=efbt,is_active=True).first()
nb_el_efbt=0
for cl in Classe.objects.filter(etablissement=efbt,annee=annee_efbt):
    actifs=cl.inscriptions.filter(is_active=True).count()
    if actifs>=10: continue
    for _ in range(15-actifs):
        el=creer_el(efbt,'EFBT',6,14)
        Inscription.objects.create(eleve=el,classe=cl,annee=annee_efbt,is_active=True)
        nb_el_efbt+=1
    print(f'  {cl.nom}: {15-actifs} eleves ajoutes')
print(f'  {nb_el_efbt} eleves total EFBT')

# =========================================================
# RESUME
# =========================================================
from eleves.models import Eleve as El
from notes.models import NotePeriode as NP, NoteUE as NU
from finances.models import Paiement as Pay

print('\n'+'='*55)
print('  RESUME FINAL')
print('='*55)
for etab in Etablissement.objects.all().order_by('code'):
    ann=AnneeScolaire.objects.filter(etablissement=etab,is_active=True).first()
    nel=El.objects.filter(etablissement=etab,is_active=True).count()
    nnp=NP.objects.filter(classe__etablissement=etab).count()
    nnu=NU.objects.filter(eleve__etablissement=etab).count()
    npa=Pay.objects.filter(etablissement=etab,annee=ann).count() if ann else 0
    nus=User.objects.filter(etablissement=etab).count()
    print(f'  [{etab.code:8}] eleves={nel:3} notes={nnp+nnu:5} paiements={npa:3} users={nus}')
print('='*55)
print()
print('LYCEE - Comptes:')
print('  dir_lycee / passer123   (Directeur)')
print('  prof_math_lyc / passer123  (Enseignant Math)')
print('  sec_lyc / passer123     (Secretaire)')
print('  surv_lyc / passer123    (Surveillant)')
print('  compt_lyc / passer123   (Comptable)')
print()
print('UCADB - Comptes existants:')
print('  dir_ucadb / passer123')
print('  prof_info1_ucadb / passer123')
print('='*55)


