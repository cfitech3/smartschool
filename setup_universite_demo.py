"""
SmartSchool ERP — Demo Universite (Systeme LMD)
================================================
Cree un etablissement universitaire complet avec :
  - 1 Universite  : "Universite Cheikh Anta Diop de Bamako" (UCADB)
  - 3 Filieres    : Informatique, Gestion, Droit
  - 4 Classes     : L1/L2 Informatique, L1 Gestion, L1 Droit
  - UEs avec credits ECTS par semestre (S1 -> S4)
  - 60 Etudiants avec profils realistes
  - Notes UE pour S1 (cloture) et S2 partiel (en cours)
  - Paiements frais inscription et scolarite
  - 7 comptes utilisateurs

Usage : python setup_universite_demo.py
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
from eleves.models import Eleve, Tuteur, Inscription
from finances.models import TypeFrais, Paiement
from notes.models import Matiere, Periode, NoteUE

random.seed(42)

PRENOMS_M = ['Amadou','Moussa','Ibrahim','Seydou','Boubacar','Oumar',
             'Mamadou','Souleymane','Abdoulaye','Cheick','Modibo',
             'Lassina','Dramane','Adama','Fousseyni','Ismail',
             'Yacouba','Issa','Hamidou','Bakary']

PRENOMS_F = ['Fatoumata','Aminata','Mariam','Kadiatou','Rokia',
             'Oumou','Djeneba','Nana','Aissata','Bintou',
             'Korotoumou','Salimata','Hawa','Maimouna','Fanta',
             'Safiatou','Awa','Kadidiatou','Ramata','Sita']

NOMS = ['Coulibaly','Diallo','Traore','Konate','Keita','Dembele',
        'Sangare','Camara','Bah','Sidibe','Kouyate','Diarra',
        'Sissoko','Toure','Maiga','Cisse','Doumbia','Bagayoko',
        'Fofana','Diabate','Kone','Samake','Goita','Bore']

VILLES_NAISS = ['Bamako','Sikasso','Mopti','Segou','Kayes',
                'Gao','Koutiala','Bougouni','San','Djenne']

UES_INFO = {
    1: [('INFO101','Algorithmique et Structures de Donnees',4,2),
        ('INFO102','Programmation C/C++',4,2),
        ('INFO103','Mathematiques Discretes',3,1),
        ('INFO104','Architecture des Ordinateurs',3,1),
        ('INFO105','Systemes dExploitation I',3,1),
        ('LANG101','Anglais Technique I',3,1)],
    2: [('INFO201','Bases de Donnees Relationnelles',4,2),
        ('INFO202','Programmation Web HTML/CSS/JS',4,2),
        ('INFO203','Reseaux Informatiques I',3,1),
        ('INFO204','Probabilites et Statistiques',3,1),
        ('INFO205','Systemes dExploitation II',3,1),
        ('LANG201','Anglais Technique II',3,1)],
    3: [('INFO301','Genie Logiciel',4,2),
        ('INFO302','Programmation OO Java',4,2),
        ('INFO303','Reseaux et Securite',3,1),
        ('INFO304','Intelligence Artificielle I',3,1),
        ('INFO305','Bases de Donnees Avancees',3,1),
        ('INFO306','Projet Individuel',3,1)],
    4: [('INFO401','Developpement Mobile',4,2),
        ('INFO402','Cloud Computing',3,1),
        ('INFO403','Intelligence Artificielle II',3,1),
        ('INFO404','Entrepreneuriat Numerique',3,1),
        ('INFO405','Stage et Rapport',4,2),
        ('INFO406','Projet de Fin de Licence',3,1)],
}

UES_GEST = {
    1: [('GEST101','Comptabilite Generale I',4,2),
        ('GEST102','Microeconomie',3,1),
        ('GEST103','Droit des Obligations',3,1),
        ('GEST104','Mathematiques Financieres',3,1),
        ('GEST105','Informatique de Gestion',3,1),
        ('GEST106','Francais Professionnel',4,2)],
    2: [('GEST201','Comptabilite Generale II',4,2),
        ('GEST202','Macroeconomie',3,1),
        ('GEST203','Droit Commercial',3,1),
        ('GEST204','Statistiques Appliquees',3,1),
        ('GEST205','Management des Organisations',3,1),
        ('GEST206','Fiscalite I',4,2)],
}

UES_DROIT = {
    1: [('DRT101','Introduction au Droit',4,2),
        ('DRT102','Droit Constitutionnel',4,2),
        ('DRT103','Histoire du Droit Africain',3,1),
        ('DRT104','Institutions Politiques',3,1),
        ('DRT105','Methodologie Juridique',3,1),
        ('DRT106','Francais Juridique',3,1)],
    2: [('DRT201','Droit des Personnes et Famille',4,2),
        ('DRT202','Droit des Biens',4,2),
        ('DRT203','Droit Penal General',3,1),
        ('DRT204','Droit Administratif I',3,1),
        ('DRT205','Procedure Civile',3,1),
        ('DRT206','Relations Internationales',3,1)],
}

print("=" * 65)
print("  SmartSchool ERP - Demo Universite (Systeme LMD)")
print("=" * 65)

# Nettoyage
print("\n[1/11] Nettoyage donnees universite existantes...")
for code in ['UCADB','UNIV-SCI']:
    try:
        etab_old = Etablissement.objects.get(code=code)
        NoteUE.objects.filter(eleve__etablissement=etab_old).delete()
        Paiement.objects.filter(eleve__etablissement=etab_old).delete()
        Inscription.objects.filter(eleve__etablissement=etab_old).delete()
        Eleve.objects.filter(etablissement=etab_old).delete()
        Tuteur.objects.filter(etablissement=etab_old).delete()
        Periode.objects.filter(etablissement=etab_old).delete()
        TypeFrais.objects.filter(etablissement=etab_old).delete()
        Matiere.objects.filter(etablissement=etab_old).delete()
        UEUniversite.objects.filter(cycle__etablissement=etab_old).delete()
        Classe.objects.filter(etablissement=etab_old).delete()
        Niveau.objects.filter(etablissement=etab_old).delete()
        ModeleDocument.objects.filter(etablissement=etab_old).delete()
        ParametreEtablissement.objects.filter(etablissement=etab_old).delete()
        AnneeScolaire.objects.filter(etablissement=etab_old).delete()
        CycleActif.objects.filter(etablissement=etab_old).delete()
        Cycle.objects.filter(etablissement=etab_old).delete()
        User.objects.filter(etablissement=etab_old, is_superuser=False).delete()
        etab_old.delete()
        print(f"    Ancien etablissement '{code}' supprime.")
    except Etablissement.DoesNotExist:
        pass

# Etablissement
print("\n[2/11] Creation universite...")
univ = Etablissement.objects.create(
    nom="Universite Cheikh Anta Diop de Bamako",
    type='universite', code='UCADB',
    adresse='Colline de Badalabougou, Bamako, Mali',
    telephone='+223 20 22 10 00',
    email='contact@ucadb.edu.ml',
    directeur='Pr. Oumar Konate',
    slogan="La Science au Service du Developpement de lAfrique",
    couleur_principale='#1B5E20',
    couleur_secondaire='#2E7D32',
)
print(f"    {univ.nom}")

ParametreEtablissement.objects.create(
    etablissement=univ, devise='FCFA',
    type_periode='semestre', note_passage=10, note_max=20,
)

annee = AnneeScolaire.objects.create(
    etablissement=univ, libelle='2024-2025',
    date_debut=datetime.date(2024,10,1),
    date_fin=datetime.date(2025,7,31),
    is_active=True,
)
print(f"    Annee : {annee.libelle}")

# Cycle
print("\n[3/11] Cycle et niveaux...")
cycle = Cycle.objects.create(
    etablissement=univ, type_cycle='universite',
    nom='Licence (LMD)', mode_calcul='credit',
    note_passage=10, note_max=20,
    diplome_prepare='Licence LMD', ordre=1,
)
CycleActif.objects.create(etablissement=univ, cycle=cycle, is_active=True)

niv_l1i = Niveau.objects.create(etablissement=univ, nom='L1 Informatique', cycle=cycle, ordre=1)
niv_l2i = Niveau.objects.create(etablissement=univ, nom='L2 Informatique', cycle=cycle, ordre=2)
niv_l1g = Niveau.objects.create(etablissement=univ, nom='L1 Gestion',      cycle=cycle, ordre=3)
niv_l1d = Niveau.objects.create(etablissement=univ, nom='L1 Droit',        cycle=cycle, ordre=5)

cl_l1i = Classe.objects.create(etablissement=univ, annee=annee, nom='L1 Informatique A', niveau=niv_l1i, filiere='Informatique', semestre_actif=2, capacite_max=40, salle='Amphi A')
cl_l2i = Classe.objects.create(etablissement=univ, annee=annee, nom='L2 Informatique A', niveau=niv_l2i, filiere='Informatique', semestre_actif=4, capacite_max=35, salle='Amphi B')
cl_l1g = Classe.objects.create(etablissement=univ, annee=annee, nom='L1 Gestion A',      niveau=niv_l1g, filiere='Gestion',      semestre_actif=2, capacite_max=45, salle='Salle 101')
cl_l1d = Classe.objects.create(etablissement=univ, annee=annee, nom='L1 Droit A',        niveau=niv_l1d, filiere='Droit',        semestre_actif=2, capacite_max=50, salle='Amphi C')
print("    4 classes creees")

# UEs
print("\n[4/11] Creation des UEs...")
all_ues = {}
for ues_dict, label in [(UES_INFO,'INFO'), (UES_GEST,'GEST'), (UES_DROIT,'DRT')]:
    for sem, liste in ues_dict.items():
        for code, nom, credits, coef in liste:
            if not UEUniversite.objects.filter(cycle=cycle, code=code, semestre=sem).exists():
                ue = UEUniversite.objects.create(cycle=cycle, code=code, nom=nom, credits=credits, semestre=sem, coefficient=coef, est_obligatoire=True)
                all_ues[code] = ue
            else:
                all_ues[code] = UEUniversite.objects.get(cycle=cycle, code=code, semestre=sem)
print(f"    {len(all_ues)} UEs creees")

# Periodes
print("\n[5/11] Periodes semestrielles...")
sem1 = Periode.objects.create(etablissement=univ, annee=annee, type='semestre', numero=1,
    libelle='Semestre 1 (Oct 2024 - Jan 2025)',
    date_debut=datetime.date(2024,10,1), date_fin=datetime.date(2025,1,31),
    is_active=False, saisie_cloturee=True)
sem2 = Periode.objects.create(etablissement=univ, annee=annee, type='semestre', numero=2,
    libelle='Semestre 2 (Fev 2025 - Jul 2025)',
    date_debut=datetime.date(2025,2,1), date_fin=datetime.date(2025,7,31),
    is_active=True, saisie_cloturee=False)
print("    S1 (cloture) + S2 (en cours)")

# Comptes
print("\n[6/11] Comptes utilisateurs...")
def creer_user(username, role, prenom, nom):
    u, cr = User.objects.get_or_create(username=username, defaults={
        'role':role, 'etablissement':univ,
        'first_name':prenom, 'last_name':nom,
        'email':f'{username}@ucadb.edu.ml',
    })
    if cr: u.set_password('passer123'); u.save()
    return u

dir_u  = creer_user('dir_ucadb',   'admin',       'Oumar',    'Konate')
sec_u  = creer_user('sec_ucadb',   'secretariat', 'Aminata',  'Diallo')
cpt_u  = creer_user('compt_ucadb', 'comptable',   'Seydou',   'Coulibaly')
ens1   = creer_user('prof_algo',   'enseignant',  'Boubacar', 'Traore')
ens2   = creer_user('prof_bdd',    'enseignant',  'Modibo',   'Sangare')
ens3   = creer_user('prof_compta', 'enseignant',  'Ibrahim',  'Keita')
ens4   = creer_user('prof_droit',  'enseignant',  'Fatoumata','Diarra')

for eu, sp in [(ens1,'Informatique/Algorithmique'),(ens2,'Info/BDD'),(ens3,'Gestion/Compta'),(ens4,'Droit/Civil')]:
    Enseignant.objects.get_or_create(user=eu, defaults={'etablissement':univ,'specialite':sp,'statut':'actif'})
print("    7 utilisateurs crees")

# Etudiants
print("\n[7/11] Creation des etudiants...")
def gen_etudiant(classe):
    sx = random.choice(['M','F'])
    pr = random.choice(PRENOMS_M if sx=='M' else PRENOMS_F)
    nm = random.choice(NOMS)
    an = random.randint(1998,2004)
    dn = datetime.date(an, random.randint(1,12), random.randint(1,28))
    el = Eleve.objects.create(
        etablissement=univ, nom=nm.upper(), prenom=pr, sexe=sx,
        date_naissance=dn, lieu_naissance=random.choice(VILLES_NAISS),
        adresse=f"Bamako, Commune {random.choice(['I','II','III','IV','V','VI'])}",
        telephone=f"+223 7{random.randint(0,9)} {random.randint(10,99):02d} {random.randint(10,99):02d} {random.randint(10,99):02d}",
    )
    tt = Tuteur.objects.create(
        etablissement=univ, nom=nm.upper(), prenom=random.choice(PRENOMS_M),
        lien=random.choice(['pere','mere','tuteur']),
        telephone=f"+223 6{random.randint(0,9)} {random.randint(10,99):02d} {random.randint(10,99):02d} {random.randint(10,99):02d}",
        profession=random.choice(['Commercant','Enseignant','Fonctionnaire','Medecin','Ingenieur','Agriculteur']),
    )
    el.tuteur=tt; el.save()
    Inscription.objects.create(eleve=el, classe=classe, annee=annee,
        statut='actif', is_active=True, date_inscription=datetime.date(2024,10,random.randint(1,15)))
    return el

et_l1i = [gen_etudiant(cl_l1i) for _ in range(22)]
et_l2i = [gen_etudiant(cl_l2i) for _ in range(18)]
et_l1g = [gen_etudiant(cl_l1g) for _ in range(15)]
et_l1d = [gen_etudiant(cl_l1d) for _ in range(12)]
total = 22+18+15+12
print(f"    {total} etudiants crees et inscrits")

# Frais et paiements
print("\n[8/11] Frais et paiements...")
fi = TypeFrais.objects.create(etablissement=univ, nom="Frais inscription", montant=Decimal('50000'), obligatoire=True)
fs_info  = TypeFrais.objects.create(etablissement=univ, nom="Scolarite Informatique", montant=Decimal('350000'), obligatoire=True)
fs_gest  = TypeFrais.objects.create(etablissement=univ, nom="Scolarite Gestion",      montant=Decimal('300000'), obligatoire=True)
fs_droit = TypeFrais.objects.create(etablissement=univ, nom="Scolarite Droit",        montant=Decimal('280000'), obligatoire=True)

def paie(etudiants, fs):
    nb=0
    for el in etudiants:
        if random.random()>0.05:
            Paiement.objects.create(etablissement=univ, eleve=el, type_frais=fi,
                montant=fi.montant, date_paiement=datetime.date(2024,10,random.randint(1,20)),
                mode_paiement=random.choice(['especes','virement','mobile_money']),
                reference=f"INS-{el.matricule}", enregistre_par=cpt_u); nb+=1
        r=random.random()
        if r>0.2:
            mt = fs.montant if r>0.5 else (fs.montant*Decimal(str(round(random.uniform(0.3,0.8),1)))).quantize(Decimal('1'))
            Paiement.objects.create(etablissement=univ, eleve=el, type_frais=fs,
                montant=mt, date_paiement=datetime.date(2024,random.randint(10,12),random.randint(1,28)),
                mode_paiement=random.choice(['especes','virement','mobile_money']),
                reference=f"SCOL-{el.matricule}", enregistre_par=cpt_u); nb+=1
    return nb

nb_p = paie(et_l1i,fs_info)+paie(et_l2i,fs_info)+paie(et_l1g,fs_gest)+paie(et_l1d,fs_droit)
print(f"    {nb_p} paiements enregistres")

# Notes S1
print("\n[9/11] Notes UE - Semestre 1 (cloture)...")
def note_aleat():
    r=random.random()
    if r<0.15:   return round(random.uniform(4.0,9.9),2)
    elif r<0.35: return round(random.uniform(10.0,11.9),2)
    elif r<0.60: return round(random.uniform(12.0,13.9),2)
    elif r<0.82: return round(random.uniform(14.0,15.9),2)
    else:        return round(random.uniform(16.0,19.5),2)

def saisir_notes(etudiants, classe, codes_ue, periode):
    nb=0
    ues = [all_ues[c] for c in codes_ue if c in all_ues]
    for el in etudiants:
        for ue in ues:
            n = Decimal(str(note_aleat()))
            ratt=None
            if float(n)<10 and random.random()>0.5:
                ratt=Decimal(str(round(random.uniform(8.0,14.0),2)))
            NoteUE.objects.get_or_create(eleve=el, ue=ue, classe=classe, periode=periode,
                defaults={'note':n,'note_rattrapage':ratt,'saisi_par':ens1}); nb+=1
    return nb

codes_info_s1 = [c for c,*_ in UES_INFO[1]]
codes_info_s3 = [c for c,*_ in UES_INFO[3]]
codes_gest_s1 = [c for c,*_ in UES_GEST[1]]
codes_drt_s1  = [c for c,*_ in UES_DROIT[1]]

nb_n1  = saisir_notes(et_l1i, cl_l1i, codes_info_s1, sem1)
nb_n1 += saisir_notes(et_l2i, cl_l2i, codes_info_s3, sem1)
nb_n1 += saisir_notes(et_l1g, cl_l1g, codes_gest_s1, sem1)
nb_n1 += saisir_notes(et_l1d, cl_l1d, codes_drt_s1,  sem1)
print(f"    {nb_n1} notes UE saisies pour S1")

# Notes S2 partiel
print("\n[10/11] Notes UE - Semestre 2 (partiel en cours)...")
def saisir_notes_partiel(etudiants, classe, codes_ue, periode, ratio=0.6):
    nb=0
    ues = [all_ues[c] for c in codes_ue if c in all_ues]
    ets = random.sample(etudiants, int(len(etudiants)*ratio))
    for el in ets:
        ues_sel = random.sample(ues, max(1,int(len(ues)*random.uniform(0.5,1.0))))
        for ue in ues_sel:
            n=Decimal(str(note_aleat()))
            NoteUE.objects.get_or_create(eleve=el, ue=ue, classe=classe, periode=periode,
                defaults={'note':n,'saisi_par':ens1}); nb+=1
    return nb

codes_info_s2 = [c for c,*_ in UES_INFO[2]]
codes_info_s4 = [c for c,*_ in UES_INFO[4]]
codes_gest_s2 = [c for c,*_ in UES_GEST[2]]
codes_drt_s2  = [c for c,*_ in UES_DROIT[2]]

nb_n2  = saisir_notes_partiel(et_l1i, cl_l1i, codes_info_s2, sem2)
nb_n2 += saisir_notes_partiel(et_l2i, cl_l2i, codes_info_s4, sem2)
nb_n2 += saisir_notes_partiel(et_l1g, cl_l1g, codes_gest_s2, sem2)
nb_n2 += saisir_notes_partiel(et_l1d, cl_l1d, codes_drt_s2,  sem2)
print(f"    {nb_n2} notes partielles S2 saisies")

# Modele releve
print("\n[11/11] Modele releve de notes LMD...")
ModeleDocument.objects.get_or_create(
    etablissement=univ, type_document='releve_notes', nom='Releve LMD Standard',
    defaults={
        'is_actif':True, 'afficher_logo':True,
        'ligne1_gauche':"MINISTERE DE L'ENSEIGNEMENT SUPERIEUR",
        'ligne2_gauche':'UNIVERSITE CHEIKH ANTA DIOP DE BAMAKO',
        'ligne3_gauche':'FACULTE DES SCIENCES ET TECHNOLOGIES',
        'ligne1_droite':'Republique du Mali',
        'ligne2_droite':'Un Peuple - Un But - Une Foi',
        'titre_document':'RELEVE DE NOTES - SYSTEME LMD',
        'couleur_titre_bg':'#1B5E20', 'couleur_titre_texte':'#FFFFFF',
        'couleur_tableau_header':'#E8F5E9', 'couleur_bordure':'#1B5E20',
        'police':'Times New Roman', 'taille_police':12,
        'afficher_rang':False,
        'label_signature_gauche':'Le Chef de Departement',
        'label_signature_droite':'Le Doyen de la Faculte',
        'texte_pied_page':'Ce document est un releve officiel certifie par le Chef de Departement.',
        'afficher_date':True,
    }
)
print("    Modele releve cree")

# Resume final
print("\n" + "=" * 65)
print("  DEMO UNIVERSITE CREEE AVEC SUCCES!")
print("=" * 65)
print(f"  Etablissement : {univ.nom}")
print(f"  Classes : L1 Info ({cl_l1i.nombre_eleves}), L2 Info ({cl_l2i.nombre_eleves}), L1 Gestion ({cl_l1g.nombre_eleves}), L1 Droit ({cl_l1d.nombre_eleves})")
print(f"  Total   : {total} etudiants")
print(f"  Notes S1 (cloture) : {nb_n1}  |  Notes S2 (partiel) : {nb_n2}")
print()
print("  COMPTES DE CONNEXION (mot de passe : passer123)")
print("  " + "-"*40)
print("  dir_ucadb   -> Directeur / Admin")
print("  sec_ucadb   -> Secretariat")
print("  compt_ucadb -> Comptable")
print("  prof_algo   -> Enseignant Informatique")
print("  prof_bdd    -> Enseignant BDD")
print("  prof_compta -> Enseignant Gestion")
print("  prof_droit  -> Enseignant Droit")
print("  " + "-"*40)
print()
print("  URL CONNEXION : http://127.0.0.1:8000/auth/login/")
print("  Saisie notes  : http://127.0.0.1:8000/notes/universite/saisie/")
print("  Etudiants     : http://127.0.0.1:8000/eleves/")
print("  Finances      : http://127.0.0.1:8000/finances/")
print("=" * 65)
