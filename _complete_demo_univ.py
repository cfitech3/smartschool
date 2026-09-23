import os, sys, django, random, datetime
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'smartschool.settings')
sys.path.insert(0, '.')
django.setup()

from decimal import Decimal
from etablissements.models import Etablissement, AnneeScolaire, Classe, UEUniversite, ModeleDocument
from eleves.models import Eleve, Inscription
from notes.models import Periode, NoteUE
from accounts.models import User
from finances.models import TypeFrais, Paiement

random.seed(42)

univ = Etablissement.objects.get(code='UCADB')
annee = AnneeScolaire.objects.get(etablissement=univ, is_active=True)
sem1 = Periode.objects.get(etablissement=univ, numero=1)
sem2 = Periode.objects.get(etablissement=univ, numero=2)
cpt_u = User.objects.get(username='compt_ucadb')
ens1 = User.objects.get(username='prof_algo')

cl_l1i = Classe.objects.get(etablissement=univ, nom='L1 Informatique A')
cl_l2i = Classe.objects.get(etablissement=univ, nom='L2 Informatique A')
cl_l1g = Classe.objects.get(etablissement=univ, nom='L1 Gestion A')
cl_l1d = Classe.objects.get(etablissement=univ, nom='L1 Droit A')

def get_etudiants(classe):
    return [i.eleve for i in Inscription.objects.filter(classe=classe, is_active=True).select_related('eleve')]

et_l1i = get_etudiants(cl_l1i)
et_l2i = get_etudiants(cl_l2i)
et_l1g = get_etudiants(cl_l1g)
et_l1d = get_etudiants(cl_l1d)

print('=== FRAIS ET PAIEMENTS ===')
fi       = TypeFrais.objects.create(etablissement=univ, annee=annee, nom='Frais inscription',     montant_defaut=Decimal('50000'),  is_obligatoire=True)
fs_info  = TypeFrais.objects.create(etablissement=univ, annee=annee, nom='Scolarite Informatique', montant_defaut=Decimal('350000'), is_obligatoire=True)
fs_gest  = TypeFrais.objects.create(etablissement=univ, annee=annee, nom='Scolarite Gestion',      montant_defaut=Decimal('300000'), is_obligatoire=True)
fs_droit = TypeFrais.objects.create(etablissement=univ, annee=annee, nom='Scolarite Droit',        montant_defaut=Decimal('280000'), is_obligatoire=True)

def paie(etudiants, fs):
    nb = 0
    for el in etudiants:
        if random.random() > 0.05:
            Paiement.objects.create(etablissement=univ, eleve=el, annee=annee, type_frais=fi,
                montant=fi.montant_defaut, date_paiement=datetime.datetime(2024,10,random.randint(1,20)),
                mode_paiement=random.choice(['especes','virement','mobile_money']), encaisse_par=cpt_u)
            nb += 1
        r = random.random()
        if r > 0.2:
            mt = fs.montant_defaut if r > 0.5 else (fs.montant_defaut*Decimal(str(round(random.uniform(0.3,0.8),1)))).quantize(Decimal('1'))
            Paiement.objects.create(etablissement=univ, eleve=el, annee=annee, type_frais=fs,
                montant=mt, date_paiement=datetime.datetime(2024,random.randint(10,12),random.randint(1,28)),
                mode_paiement=random.choice(['especes','virement','mobile_money']), encaisse_par=cpt_u)
            nb += 1
    return nb

nb_p = paie(et_l1i,fs_info)+paie(et_l2i,fs_info)+paie(et_l1g,fs_gest)+paie(et_l1d,fs_droit)
print(f'  {nb_p} paiements')

print('=== NOTES UE ===')
CODES = {
    'info_s1': ['INFO101','INFO102','INFO103','INFO104','INFO105','LANG101'],
    'info_s2': ['INFO201','INFO202','INFO203','INFO204','INFO205','LANG201'],
    'info_s3': ['INFO301','INFO302','INFO303','INFO304','INFO305','INFO306'],
    'info_s4': ['INFO401','INFO402','INFO403','INFO404','INFO405','INFO406'],
    'gest_s1': ['GEST101','GEST102','GEST103','GEST104','GEST105','GEST106'],
    'gest_s2': ['GEST201','GEST202','GEST203','GEST204','GEST205','GEST206'],
    'drt_s1':  ['DRT101','DRT102','DRT103','DRT104','DRT105','DRT106'],
    'drt_s2':  ['DRT201','DRT202','DRT203','DRT204','DRT205','DRT206'],
}

def note_aleat():
    r = random.random()
    if r < 0.15:   return round(random.uniform(4.0,9.9),2)
    elif r < 0.35: return round(random.uniform(10.0,11.9),2)
    elif r < 0.60: return round(random.uniform(12.0,13.9),2)
    elif r < 0.82: return round(random.uniform(14.0,15.9),2)
    else:          return round(random.uniform(16.0,19.5),2)

def saisir_notes(etudiants, classe, codes, periode, partiel=False):
    cycle = classe.niveau.cycle
    ues = list(UEUniversite.objects.filter(cycle=cycle, code__in=codes))
    nb = 0
    targets = random.sample(etudiants, max(1,int(len(etudiants)*0.6))) if partiel else etudiants
    for el in targets:
        ues_sel = random.sample(ues, max(1,int(len(ues)*random.uniform(0.5,1.0)))) if partiel else ues
        for ue in ues_sel:
            n = Decimal(str(note_aleat()))
            ratt = Decimal(str(round(random.uniform(8.0,14.0),2))) if (float(n)<10 and not partiel and random.random()>0.5) else None
            NoteUE.objects.get_or_create(eleve=el, ue=ue, classe=classe, periode=periode,
                defaults={'note':n,'note_rattrapage':ratt,'saisi_par':ens1})
            nb += 1
    return nb

nb_n1  = saisir_notes(et_l1i,cl_l1i,CODES['info_s1'],sem1)
nb_n1 += saisir_notes(et_l2i,cl_l2i,CODES['info_s3'],sem1)
nb_n1 += saisir_notes(et_l1g,cl_l1g,CODES['gest_s1'],sem1)
nb_n1 += saisir_notes(et_l1d,cl_l1d,CODES['drt_s1'], sem1)
print(f'  {nb_n1} notes S1 (clot.)')

nb_n2  = saisir_notes(et_l1i,cl_l1i,CODES['info_s2'],sem2,partiel=True)
nb_n2 += saisir_notes(et_l2i,cl_l2i,CODES['info_s4'],sem2,partiel=True)
nb_n2 += saisir_notes(et_l1g,cl_l1g,CODES['gest_s2'],sem2,partiel=True)
nb_n2 += saisir_notes(et_l1d,cl_l1d,CODES['drt_s2'], sem2,partiel=True)
print(f'  {nb_n2} notes S2 (partiel)')

print('=== MODELE RELEVE ===')
ModeleDocument.objects.get_or_create(
    etablissement=univ, type_document='releve_notes', nom='Releve LMD Standard',
    defaults={
        'is_actif':True,'afficher_logo':True,
        'ligne1_gauche':'MINISTERE DE LENSEIGNEMENT SUPERIEUR',
        'ligne2_gauche':'UNIVERSITE CHEIKH ANTA DIOP DE BAMAKO',
        'ligne3_gauche':'FACULTE DES SCIENCES ET TECHNOLOGIES',
        'ligne1_droite':'Republique du Mali',
        'titre_document':'RELEVE DE NOTES - SYSTEME LMD',
        'couleur_titre_bg':'#1B5E20','couleur_titre_texte':'#FFFFFF',
        'couleur_tableau_header':'#E8F5E9','couleur_bordure':'#1B5E20',
        'police':'Times New Roman','taille_police':12,
        'afficher_rang':False,
        'label_signature_gauche':'Le Chef de Departement',
        'label_signature_droite':'Le Doyen de la Faculte',
        'texte_pied_page':'Document officiel certifie par le Chef de Departement.',
        'afficher_date':True,
    }
)
print('  Modele cree')
print()
print('=== DEMO UNIVERSITE COMPLETE ===')
print(f'  Etudiants  : {len(et_l1i)+len(et_l2i)+len(et_l1g)+len(et_l1d)}')
print(f'  Paiements  : {nb_p}')
print(f'  Notes S1   : {nb_n1}')
print(f'  Notes S2   : {nb_n2}')
print()
print('  Connexion : http://127.0.0.1:8000/auth/login/')
print('  dir_ucadb / passer123   (Directeur Admin)')
print('  compt_ucadb / passer123 (Comptable)')
print('  prof_algo / passer123   (Enseignant)')
print('SUCCES!')
