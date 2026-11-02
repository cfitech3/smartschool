"""
SmartSchool ERP - Jeu de donnees de demonstration (tests en ligne)
==================================================================

Script AUTONOME et IDEMPOTENT : il cree tout ce qui manque et peut etre
relance sans dupliquer les donnees (les effectifs sont completes jusqu'a la cible).

Cree 3 etablissements couvrant les 3 modes de notation du logiciel :
  - LYC-EXC : Lycee            (cycle 'lycee', note directe /20 + conduite /18)
  - UCADB   : Universite       (cycle 'universite', UE / credits ECTS, semestres)
  - EFBT    : Ecole fondamentale (1er cycle, compositions /10)

Pour chaque etablissement : cycle + cycle actif, parametres, annee scolaire,
periodes, niveaux, classes, matieres/UE, equipe (directeur, secretariat,
comptable, surveillant, enseignants), affectations, emploi du temps, eleves
avec tuteurs (fratries), notes, frais (dont tranches + echeances), paiements,
presences des 10 derniers jours ouvres, et un compte eleve + parent de demo.

IMPORTANT : si un etablissement possede deja une annee scolaire active, elle est
REUTILISEE (aucune annee existante n'est desactivee).

Usage :
    python complete_demo.py
    DEMO_PASSWORD="MonMotDePasse" python complete_demo.py      (Linux)
    $env:DEMO_PASSWORD="MonMotDePasse"; python complete_demo.py (PowerShell)
"""
import os
import sys
import random
import datetime

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'smartschool.settings')
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import django  # noqa: E402
django.setup()

from decimal import Decimal  # noqa: E402
from django.db import transaction  # noqa: E402
from django.utils import timezone  # noqa: E402

from accounts.models import User  # noqa: E402
from etablissements.models import (  # noqa: E402
    Etablissement, AnneeScolaire, Niveau, Classe, Enseignant, AffectationMatiere,
    ParametreEtablissement, Cycle, CycleActif, UEUniversite,
)
from eleves.models import Eleve, Tuteur, Inscription, Presence  # noqa: E402
from finances.models import TypeFrais, Paiement, Echeance  # noqa: E402
from notes.models import (  # noqa: E402
    Matiere, Periode, NotePeriode, NoteUE, Composition, EmploiDuTemps, MessageFamille,
)

random.seed(2026)
PASSWORD = os.environ.get('DEMO_PASSWORD', 'passer123')
TODAY = timezone.localdate()

PRENOMS_M = ['Amadou', 'Moussa', 'Ibrahim', 'Seydou', 'Boubacar', 'Oumar', 'Mamadou', 'Souleymane',
             'Abdoulaye', 'Cheick', 'Modibo', 'Lassina', 'Dramane', 'Adama']
PRENOMS_F = ['Fatoumata', 'Aminata', 'Mariam', 'Kadiatou', 'Rokia', 'Oumou', 'Djeneba', 'Nana',
             'Aissata', 'Bintou', 'Korotoumou', 'Salimata', 'Hawa', 'Maimouna']
NOMS = ['Coulibaly', 'Diallo', 'Traore', 'Konate', 'Keita', 'Dembele', 'Sangare', 'Camara', 'Bah',
        'Sidibe', 'Kouyate', 'Diarra', 'Sissoko', 'Toure', 'Maiga']
VILLES = ['Bamako', 'Sikasso', 'Mopti', 'Segou', 'Kayes', 'Gao']
QUARTIERS = ['Lafiabougou', 'Hippodrome', 'Faladie', 'Badalabougou', 'Kalaban']
PROFESSIONS = ['Commercant', 'Enseignant', 'Infirmier', 'Fonctionnaire', 'Agriculteur', 'Chauffeur']
JOURS = ['lundi', 'mardi', 'mercredi', 'jeudi', 'vendredi', 'samedi']
CRENEAUX = [('08:00', '10:00'), ('10:00', '12:00'), ('15:00', '17:00')]


# ════════════════════════════════════════════════════════════════════
#  Utilitaires
# ════════════════════════════════════════════════════════════════════

def log(msg):
    print(f'  {msg}')


def dt_aware(d, h=None, m=None):
    h = random.randint(8, 16) if h is None else h
    m = random.randint(0, 59) if m is None else m
    return timezone.make_aware(datetime.datetime.combine(d, datetime.time(h, m)))


def date_aleatoire(debut, fin):
    if fin <= debut:
        return debut
    return debut + datetime.timedelta(days=random.randint(0, (fin - debut).days))


def note20(lo=4, hi=19):
    return Decimal(str(round(random.uniform(lo, hi), 2)))


def creer_user(username, prenom, nom, role, etab, tel=''):
    u, cree = User.objects.get_or_create(username=username, defaults={
        'first_name': prenom, 'last_name': nom, 'role': role,
        'etablissement': etab, 'telephone': tel,
    })
    if cree:
        u.set_password(PASSWORD)
        u.save()
    return u


def creer_enseignant(etab, username, prenom, nom, spec, diplome='Licence', salaire=250000):
    u = creer_user(username, prenom, nom, 'enseignant', etab)
    ens, _ = Enseignant.objects.get_or_create(user=u, defaults={
        'etablissement': etab, 'specialite': spec, 'diplome': diplome,
        'statut': 'actif', 'salaire': salaire,
        'date_embauche': TODAY - datetime.timedelta(days=random.randint(365, 3650)),
    })
    return ens


def setup_etablissement(code, nom, type_etab, type_cycle, cycle_cfg, type_periode='trimestre'):
    """Etablissement + Cycle + CycleActif + Parametres + Annee active."""
    etab, cree = Etablissement.objects.get_or_create(code=code, defaults={
        'nom': nom, 'type': type_etab, 'adresse': f'{random.choice(QUARTIERS)}, Bamako',
        'telephone': f'+223 20 {random.randint(10, 99)} {random.randint(10, 99)} {random.randint(10, 99)}',
        'email': f'contact@{code.lower()}.ml', 'is_active': True,
    })
    log(f"Etablissement {'cree' if cree else 'existant'} : {etab.nom}")

    cycle, _ = Cycle.objects.get_or_create(etablissement=etab, type_cycle=type_cycle, defaults=cycle_cfg)
    CycleActif.objects.get_or_create(etablissement=etab, cycle=cycle, defaults={'is_active': True, 'ordre': 1})
    ParametreEtablissement.objects.get_or_create(etablissement=etab, defaults={'type_periode': type_periode})

    annee = AnneeScolaire.objects.filter(etablissement=etab, is_active=True).first()
    if not annee:
        y = TODAY.year if TODAY.month >= 9 else TODAY.year - 1
        annee, _ = AnneeScolaire.objects.get_or_create(
            etablissement=etab, libelle=f'{y}-{y + 1}',
            defaults={'date_debut': datetime.date(y, 10, 1), 'date_fin': datetime.date(y + 1, 7, 15),
                      'is_active': True})
        if not annee.is_active:
            annee.is_active = True
            annee.save()
    log(f'Annee scolaire active : {annee.libelle} | Cycle : {cycle.nom} ({cycle.mode_calcul})')
    return etab, cycle, annee


def setup_periodes(etab, annee, type_periode):
    y = annee.date_debut.year
    if type_periode == 'semestre':
        cfg = [(1, 'Semestre 1', datetime.date(y, 10, 1), datetime.date(y + 1, 2, 15)),
               (2, 'Semestre 2', datetime.date(y + 1, 2, 16), datetime.date(y + 1, 7, 15))]
    else:
        cfg = [(1, '1er Trimestre', datetime.date(y, 10, 1), datetime.date(y, 12, 20)),
               (2, '2eme Trimestre', datetime.date(y + 1, 1, 6), datetime.date(y + 1, 3, 28)),
               (3, '3eme Trimestre', datetime.date(y + 1, 4, 7), datetime.date(y + 1, 6, 30))]
    periodes, creees = [], False
    for num, lib, d1, d2 in cfg:
        p, c = Periode.objects.get_or_create(etablissement=etab, annee=annee, numero=num, defaults={
            'type': type_periode, 'libelle': lib, 'date_debut': d1, 'date_fin': d2})
        creees = creees or c
        periodes.append(p)
    # Une seule periode active (celle en cours, sinon la derniere commencee) - uniquement si on vient de les creer
    if creees and not Periode.objects.filter(etablissement=etab, annee=annee, is_active=True).exists():
        commencees = [p for p in periodes if p.date_debut <= TODAY] or periodes[:1]
        active = next((p for p in commencees if p.date_fin >= TODAY), commencees[-1])
        Periode.objects.filter(pk=active.pk).update(is_active=True)
    # Periodes pour lesquelles on genere des notes : celles deja commencees (au moins la 1ere)
    a_noter = [p for p in periodes if p.date_debut <= TODAY] or periodes[:1]
    log(f'{len(periodes)} periodes ({len(a_noter)} avec notes)')
    return periodes, a_noter


def setup_classes(etab, annee, cycle, cfg):
    """cfg = [(nom_niveau, ordre, [noms_classes], extra_defaults)]"""
    classes = []
    for niv_nom, ordre, noms, extra in cfg:
        niv, _ = Niveau.objects.get_or_create(etablissement=etab, nom=niv_nom,
                                              defaults={'cycle': cycle, 'ordre': ordre})
        if not niv.cycle_id:
            niv.cycle = cycle
            niv.save(update_fields=['cycle'])
        for i, nom_cl in enumerate(noms):
            cl, _ = Classe.objects.get_or_create(etablissement=etab, annee=annee, nom=nom_cl, defaults={
                'niveau': niv, 'capacite_max': 45, 'salle': f'Salle {ordre}{i + 1}', **extra})
            classes.append(cl)
    log(f'{len(classes)} classes')
    return classes


def setup_matieres(etab, cfg):
    mats = {}
    for nom_m, code_m, coef in cfg:
        m, _ = Matiere.objects.get_or_create(etablissement=etab, nom=nom_m, defaults={
            'code': code_m, 'coefficient': coef, 'is_conduite': code_m == 'COND'})
        mats[code_m] = m
    log(f'{len(mats)} matieres')
    return mats


def remplir_classes(etab, annee, classes, cible, age_min, age_max):
    """Complete chaque classe jusqu'a `cible` eleves. ~30% des eleves partagent un tuteur (fratrie)."""
    tuteurs = list(Tuteur.objects.filter(etablissement=etab)[:50])
    nb = 0
    for cl in classes:
        manquants = max(0, cible - cl.inscriptions.filter(is_active=True).count())
        for _ in range(manquants):
            nom = random.choice(NOMS)
            if tuteurs and random.random() < 0.3:
                tut = random.choice(tuteurs)
                nom = tut.nom
            else:
                tut = Tuteur.objects.create(
                    etablissement=etab, nom=nom, prenom=random.choice(PRENOMS_M + PRENOMS_F),
                    lien=random.choice(['pere', 'mere', 'tuteur']),
                    telephone=f'+223 {random.randint(60, 99)} {random.randint(10, 99)} '
                              f'{random.randint(10, 99)} {random.randint(10, 99)}',
                    profession=random.choice(PROFESSIONS))
                tuteurs.append(tut)
            sx = random.choice(['M', 'F'])
            y = TODAY.year - random.randint(age_min, age_max)
            el = Eleve.objects.create(  # matricule genere automatiquement (CODE-ANNEE-XXXX)
                etablissement=etab, nom=nom, prenom=random.choice(PRENOMS_M if sx == 'M' else PRENOMS_F),
                sexe=sx, date_naissance=datetime.date(y, random.randint(1, 12), random.randint(1, 28)),
                lieu_naissance=random.choice(VILLES),
                adresse=f'{random.choice(QUARTIERS)}, {random.choice(VILLES)}', tuteur=tut)
            Inscription.objects.create(eleve=el, classe=cl, annee=annee, statut='actif', is_active=True,
                                       date_inscription=annee.date_debut)
            nb += 1
    log(f'{nb} eleves ajoutes')


def inscriptions_de(cl):
    return list(cl.inscriptions.filter(is_active=True).select_related('eleve'))


def affecter(annee, classes, mats, cfg):
    """cfg = [(enseignant, [codes_matieres])]"""
    nb = 0
    for ens, codes in cfg:
        for code in codes:
            m = mats.get(code)
            if not m:
                continue
            for cl in classes:
                _, c = AffectationMatiere.objects.get_or_create(
                    enseignant=ens, classe=cl, matiere=m, annee=annee, defaults={'heures_semaine': 3})
                nb += c
    log(f'{nb} affectations')


def emploi_du_temps(etab, annee, classes):
    """EDT sans chevauchement (classe et enseignant), genere uniquement pour les classes sans EDT."""
    occupes = set(EmploiDuTemps.objects.filter(classe__etablissement=etab)
                  .values_list('enseignant_id', 'jour', 'heure_debut'))
    nb = 0
    for i, cl in enumerate(classes):
        if EmploiDuTemps.objects.filter(classe=cl).exists():
            continue
        affs = list(AffectationMatiere.objects.filter(classe=cl, annee=annee).select_related('enseignant__user', 'matiere'))
        if not affs:
            continue
        k = i
        for jour in JOURS[:5]:
            for hd, hf in CRENEAUX:
                for essai in range(len(affs)):
                    a = affs[(k + essai) % len(affs)]
                    cle = (a.enseignant.user_id, jour, hd)
                    if cle not in occupes:
                        EmploiDuTemps.objects.create(etablissement=etab, classe=cl, matiere=a.matiere,
                                                     enseignant=a.enseignant.user, jour=jour,
                                                     heure_debut=hd, heure_fin=hf, salle=cl.salle)
                        occupes.add(cle)
                        nb += 1
                        break
                k += 1
    log(f'{nb} creneaux d\'emploi du temps')


def notes_periodes(cycle, classes, mats, periodes, saisi_par, surveillant):
    """NotePeriode selon le mode du cycle : 'direct' (note /20) ou 'compo' (classe /20 + compo /40). Conduite /18."""
    nb = 0
    mats_notes = [m for m in mats.values() if not m.is_conduite]
    conduite = next((m for m in mats.values() if m.is_conduite), None)
    for p in periodes:
        for cl in classes:
            existants = set(NotePeriode.objects.filter(classe=cl, periode=p).values_list('eleve_id', 'matiere_id'))
            a_creer = []
            for insc in inscriptions_de(cl):
                niveau_eleve = random.uniform(-3, 3)  # eleve plus ou moins fort
                for m in mats_notes:
                    if (insc.eleve_id, m.pk) in existants:
                        continue
                    base = max(0, min(20, random.uniform(6, 17) + niveau_eleve))
                    if cycle.mode_calcul == 'direct':
                        kw = {'moy_classe': Decimal(str(round(base, 2))), 'moy_compo': None,
                              'note_max_classe': Decimal('20'), 'note_max_compo': Decimal('20')}
                    else:
                        compo = max(0, min(40, base * 2 + random.uniform(-4, 4)))
                        kw = {'moy_classe': Decimal(str(round(base, 2))), 'moy_compo': Decimal(str(round(compo, 2))),
                              'note_max_classe': Decimal('20'), 'note_max_compo': Decimal('40')}
                    a_creer.append(NotePeriode(eleve=insc.eleve, matiere=m, classe=cl, periode=p,
                                               saisi_par=saisi_par, **kw))
                if conduite and (insc.eleve_id, conduite.pk) not in existants:
                    a_creer.append(NotePeriode(eleve=insc.eleve, matiere=conduite, classe=cl, periode=p,
                                               note_conduite=Decimal(str(random.randint(11, 18))),
                                               saisi_par=surveillant))
            NotePeriode.objects.bulk_create(a_creer, ignore_conflicts=True)
            nb += len(a_creer)
    log(f'{nb} notes de periode')


def frais_et_paiements(etab, annee, cfg, comptable, prefix_mode='especes'):
    """cfg = [(nom, montant, periodicite, nb_tranches)]. Genere echeances (tranches) et paiements realistes."""
    fin_paiements = min(TODAY, annee.date_fin)
    frais = []
    for nom, montant, period, nbt in cfg:
        f, _ = TypeFrais.objects.get_or_create(etablissement=etab, annee=annee, nom=nom, defaults={
            'montant_defaut': montant, 'is_obligatoire': True, 'periodicite': period, 'nombre_tranches': nbt})
        frais.append(f)

    y = annee.date_debut.year
    dates_tranches = [datetime.date(y, 10, 31), datetime.date(y + 1, 1, 31), datetime.date(y + 1, 4, 30)]
    eleves = Eleve.objects.filter(etablissement=etab, is_active=True,
                                  inscriptions__annee=annee, inscriptions__is_active=True).distinct()
    nb_pay = nb_ech = 0
    for el in eleves:
        profil = random.random()  # <0.55 bon payeur, <0.85 partiel, sinon mauvais payeur
        for f in frais:
            if Paiement.objects.filter(eleve=el, type_frais=f, annee=annee).exists():
                continue
            if f.periodicite == 'tranches' and f.nombre_tranches > 1:
                n = f.nombre_tranches
                part = int(f.montant_defaut) // n
                montants = [part] * (n - 1) + [int(f.montant_defaut) - part * (n - 1)]
                for i, mt in enumerate(montants, 1):
                    dl = dates_tranches[i - 1] if i <= len(dates_tranches) else annee.date_fin
                    ech, c = Echeance.objects.get_or_create(
                        etablissement=etab, eleve=el, annee=annee, type_frais=f, numero=i,
                        defaults={'libelle': f'Tranche {i}', 'montant': mt, 'date_limite': dl})
                    nb_ech += c
                    echue = dl <= fin_paiements
                    paye = echue and (profil < 0.55 or (profil < 0.85 and i == 1))
                    if paye and ech.statut != 'payee':
                        d = date_aleatoire(max(annee.date_debut, dl - datetime.timedelta(days=30)), min(dl, fin_paiements))
                        p = Paiement.objects.create(
                            etablissement=etab, annee=annee, eleve=el, type_frais=f, montant=mt,
                            mode_paiement=random.choice([prefix_mode, 'mobile_money']),
                            periode_payee=f'Tranche {i}', date_paiement=dt_aware(d), encaisse_par=comptable)
                        ech.marquer_payee(p)
                        nb_pay += 1
                    elif echue and ech.statut == 'a_payer':
                        ech.statut = 'retard'
                        ech.save(update_fields=['statut'])
            else:
                if profil < 0.55:
                    mt = f.montant_defaut
                elif profil < 0.85:
                    mt = (f.montant_defaut * Decimal('0.5')).quantize(Decimal('1'))
                else:
                    continue
                d = date_aleatoire(annee.date_debut, min(annee.date_debut + datetime.timedelta(days=45), fin_paiements))
                Paiement.objects.create(etablissement=etab, annee=annee, eleve=el, type_frais=f, montant=mt,
                                        mode_paiement=random.choice([prefix_mode, 'mobile_money']),
                                        date_paiement=dt_aware(d), encaisse_par=comptable)
                nb_pay += 1
    log(f'{len(frais)} types de frais | {nb_ech} echeances | {nb_pay} paiements')


def presences(etab, classes, surveillant, nb_jours=10):
    """Appel des `nb_jours` derniers jours ouvres (hors dimanche) pour chaque classe."""
    jours, d = [], TODAY
    while len(jours) < nb_jours:
        d -= datetime.timedelta(days=1)
        if d.weekday() != 6:
            jours.append(d)
    a_creer = []
    for cl in classes:
        inscs = inscriptions_de(cl)
        deja = set(Presence.objects.filter(classe=cl, date__in=jours).values_list('eleve_id', 'date'))
        for j in jours:
            for insc in inscs:
                if (insc.eleve_id, j) in deja:
                    continue
                r = random.random()
                statut = 'present' if r < 0.88 else 'absent' if r < 0.95 else 'retard' if r < 0.98 else 'justifie'
                a_creer.append(Presence(eleve=insc.eleve, classe=cl, date=j, statut=statut,
                                        motif='Maladie' if statut == 'justifie' else '',
                                        justificatif_valide=statut == 'justifie', enregistre_par=surveillant))
    Presence.objects.bulk_create(a_creer, ignore_conflicts=True)
    log(f'{len(a_creer)} presences')


def comptes_famille(etab, suffixe):
    """Un compte eleve + le compte parent de son tuteur, pour tester l'Espace Famille."""
    el = (Eleve.objects.filter(etablissement=etab, is_active=True, tuteur__isnull=False,
                               inscriptions__is_active=True).order_by('pk').first())
    if not el:
        return
    if not el.user_compte_id:
        u = creer_user(f'eleve_{suffixe}', el.prenom, el.nom, 'eleve', etab)
        if not hasattr(u, 'profil_eleve'):
            el.user_compte = u
            el.save(update_fields=['user_compte'])
    tut = el.tuteur
    if not tut.user_compte_id:
        u = creer_user(f'parent_{suffixe}', tut.prenom, tut.nom, 'parent', etab, tel=tut.telephone)
        if not hasattr(u, 'profil_tuteur'):
            tut.user_compte = u
            tut.save(update_fields=['user_compte'])
    if tut.user_compte_id and not MessageFamille.objects.filter(expediteur=tut.user_compte).exists():
        MessageFamille.objects.create(
            etablissement=etab, expediteur=tut.user_compte, eleve=el, destinataire_role='directeur',
            sujet='Demande de rendez-vous', corps=f'Bonjour, je souhaite vous rencontrer au sujet de {el.prenom}.')
    log(f'Espace famille : eleve_{suffixe} / parent_{suffixe} ({el.nom_complet})')


# ════════════════════════════════════════════════════════════════════
#  1. LYCEE (note directe /20)
# ════════════════════════════════════════════════════════════════════

def demo_lycee():
    print('\n[1/3] LYCEE  (LYC-EXC)')
    etab, cycle, annee = setup_etablissement(
        'LYC-EXC', "Lycee d'Excellence de Bamako", 'lycee', 'lycee',
        {'nom': 'Lycee', 'mode_calcul': 'direct', 'note_passage': 10, 'diplome_prepare': 'Baccalaureat'})
    _, a_noter = setup_periodes(etab, annee, 'trimestre')
    classes = setup_classes(etab, annee, cycle, [
        ('10eme Annee', 10, ['10eme Commune A', '10eme Commune B'], {}),
        ('11eme Annee', 11, ['11eme Lettres', '11eme Sciences'], {}),
        ('12eme Annee', 12, ['Terminale Sciences', 'Terminale Lettres'], {}),
    ])
    mats = setup_matieres(etab, [
        ('Mathematiques', 'MATH', 4), ('Physique-Chimie', 'PC', 3), ('Sciences de la Vie', 'SVT', 2),
        ('Francais', 'FR', 3), ('Histoire-Geographie', 'HG', 2), ('Anglais', 'ANG', 2),
        ('Philosophie', 'PHILO', 2), ('Education Civique', 'EC', 1), ('Sport', 'EPS', 1), ('Conduite', 'COND', 1),
    ])
    dir_ = creer_user('dir_lycee', 'Hamidou', 'Toure', 'admin', etab)
    creer_user('sec_lyc', 'Mariam', 'Sissoko', 'secretariat', etab)
    surv = creer_user('surv_lyc', 'Oumar', 'Sangare', 'surveillant', etab)
    compt = creer_user('compt_lyc', 'Djeneba', 'Maiga', 'comptable', etab)
    e_math = creer_enseignant(etab, 'prof_math_lyc', 'Boubacar', 'Diarra', 'Mathematiques', 'CAPES', 320000)
    e_fr = creer_enseignant(etab, 'prof_fr_lyc', 'Aminata', 'Kone', 'Lettres', 'CAPES', 300000)
    e_sc = creer_enseignant(etab, 'prof_sc_lyc', 'Ibrahim', 'Coulibaly', 'Sciences', 'Master', 300000)
    e_hg = creer_enseignant(etab, 'prof_hg_lyc', 'Fatoumata', 'Traore', 'Histoire', 'Licence', 260000)
    e_ang = creer_enseignant(etab, 'prof_ang_lyc', 'Seydou', 'Bah', 'Anglais', 'CAPES', 280000)
    log('Equipe : directeur, secretariat, surveillant, comptable + 5 enseignants')
    affecter(annee, classes, mats, [(e_math, ['MATH', 'PC']), (e_fr, ['FR', 'PHILO', 'EC']),
                                    (e_sc, ['SVT', 'EPS']), (e_hg, ['HG']), (e_ang, ['ANG'])])
    emploi_du_temps(etab, annee, classes)
    remplir_classes(etab, annee, classes, 22, 15, 19)
    notes_periodes(cycle, classes, mats, a_noter, e_math.user, surv)
    frais_et_paiements(etab, annee, [
        ('Frais de scolarite', Decimal('150000'), 'tranches', 3),
        ('Frais inscription', Decimal('25000'), 'unique', 1),
        ('Activites parascolaires', Decimal('15000'), 'unique', 1),
    ], compt)
    presences(etab, classes, surv)
    comptes_famille(etab, 'lyc')
    return dir_


# ════════════════════════════════════════════════════════════════════
#  2. UNIVERSITE (UE / credits ECTS)
# ════════════════════════════════════════════════════════════════════

def demo_universite():
    print('\n[2/3] UNIVERSITE  (UCADB)')
    etab, cycle, annee = setup_etablissement(
        'UCADB', 'Universite Cheick Anta Diop de Bamako', 'universite', 'universite',
        {'nom': 'Universite', 'mode_calcul': 'credit', 'note_passage': 10,
         'diplome_prepare': 'Licence / Master / Doctorat'}, type_periode='semestre')
    periodes, a_noter = setup_periodes(etab, annee, 'semestre')

    l1 = ['L1 Droit', 'L1 Gestion', 'L1 Informatique']
    l2 = ['L2 Droit', 'L2 Gestion']
    classes = setup_classes(etab, annee, cycle, [
        ('Licence 1', 1, l1, {'semestre_actif': 1}),
        ('Licence 2', 2, l2, {'semestre_actif': 3}),
    ])
    for cl in classes:
        if not cl.filiere:
            cl.filiere = cl.nom.split(' ', 1)[1]
            cl.save(update_fields=['filiere'])

    UES = [  # (code, nom, credits, semestre)
        ('UE101', 'Methodologie du travail universitaire', 4, 1), ('UE102', 'Expression ecrite et orale', 3, 1),
        ('UE103', 'Introduction aux fondamentaux', 6, 1), ('UE104', 'Informatique de base', 3, 1),
        ('UE201', 'Statistiques descriptives', 5, 2), ('UE202', 'Economie generale', 4, 2),
        ('UE203', 'Anglais academique', 3, 2),
        ('UE301', 'Analyse approfondie I', 6, 3), ('UE302', 'Comptabilite / Droit des obligations', 5, 3),
        ('UE303', 'Recherche documentaire', 3, 3),
        ('UE401', 'Analyse approfondie II', 6, 4), ('UE402', 'Projet tutore', 4, 4),
    ]
    ues = {}
    for code, nom, cr, sem in UES:
        ue, _ = UEUniversite.objects.get_or_create(cycle=cycle, code=code, defaults={
            'nom': nom, 'credits': cr, 'semestre': sem, 'coefficient': 1})
        ues.setdefault(ue.semestre, []).append(ue)
    log(f'{len(UES)} UE (S1 a S4)')

    dir_ = creer_user('dir_ucadb', 'Sekou', 'Keita', 'admin', etab)
    creer_user('sec_ucadb', 'Aissata', 'Diallo', 'secretariat', etab)
    surv = creer_user('surv_ucadb', 'Lassina', 'Konate', 'surveillant', etab)
    compt = creer_user('compt_ucadb', 'Hawa', 'Camara', 'comptable', etab)
    profs = [creer_enseignant(etab, 'prof_droit_ucadb', 'Modibo', 'Sidibe', 'Droit', 'Doctorat', 450000),
             creer_enseignant(etab, 'prof_gest_ucadb', 'Rokia', 'Dembele', 'Gestion', 'Doctorat', 450000),
             creer_enseignant(etab, 'prof_info_ucadb', 'Cheick', 'Kouyate', 'Informatique', 'Doctorat', 450000)]
    log('Equipe : directeur, secretariat, surveillant, comptable + 3 enseignants')

    remplir_classes(etab, annee, classes, 18, 19, 26)

    # Notes UE : L1 -> S1 (periode 1) / S2 (periode 2) ; L2 -> S3 / S4
    nb = 0
    for cl in classes:
        sems = (1, 2) if cl.nom in l1 else (3, 4)
        prof = random.choice(profs).user
        for p in a_noter:
            sem = sems[0] if p.numero == 1 else sems[1]
            for insc in inscriptions_de(cl):
                for ue in ues.get(sem, []):
                    if NoteUE.objects.filter(eleve=insc.eleve, ue=ue, classe=cl, periode=p).exists():
                        continue
                    n = note20(4, 19)
                    ratt = note20(8, 16) if n < 10 and random.random() > 0.4 else None
                    NoteUE.objects.create(eleve=insc.eleve, ue=ue, classe=cl, periode=p,
                                          note=n, note_rattrapage=ratt, saisi_par=prof)  # save() -> mention + credits
                    nb += 1
    log(f'{nb} notes UE')

    frais_et_paiements(etab, annee, [
        ("Frais d'inscription", Decimal('50000'), 'unique', 1),
        ('Scolarite annuelle', Decimal('300000'), 'tranches', 3),
        ('Frais de bibliotheque', Decimal('10000'), 'unique', 1),
    ], compt, prefix_mode='virement')
    presences(etab, classes, surv, nb_jours=5)
    comptes_famille(etab, 'ucadb')
    return dir_


# ════════════════════════════════════════════════════════════════════
#  3. ECOLE FONDAMENTALE 1er cycle (compositions /10)
# ════════════════════════════════════════════════════════════════════

def demo_ecole():
    print('\n[3/3] ECOLE FONDAMENTALE  (EFBT)')
    etab, cycle, annee = setup_etablissement(
        'EFBT', 'Ecole Fondamentale Babemba Traore', 'ecole', 'premier_cycle',
        {'nom': '1er Cycle Fondamental', 'mode_calcul': 'compo', 'note_passage': 5,
         'diplome_prepare': "Certificat de fin d'etudes du 1er cycle", 'nb_compositions_trimestre': 3})
    _, a_noter = setup_periodes(etab, annee, 'trimestre')
    classes = setup_classes(etab, annee, cycle, [
        ('1ere Annee', 1, ['1ere Annee A'], {}), ('2eme Annee', 2, ['2eme Annee A'], {}),
        ('3eme Annee', 3, ['3eme Annee A'], {}), ('4eme Annee', 4, ['4eme Annee A'], {}),
        ('5eme Annee', 5, ['5eme Annee A'], {}), ('6eme Annee', 6, ['6eme Annee A'], {}),
    ])
    mats = setup_matieres(etab, [
        ('Lecture', 'LECT', 1), ('Ecriture', 'ECR', 1), ('Calcul', 'CALC', 1), ('Sciences', 'SC', 1),
        ('Histoire-Geographie', 'HG', 1), ('Education Civique et Morale', 'ECM', 1), ('Dessin', 'DES', 1),
        ('Conduite', 'COND', 1),
    ])
    dir_ = creer_user('dir_efbt', 'Bakary', 'Sangare', 'admin', etab)
    creer_user('sec_efbt', 'Nana', 'Toure', 'secretariat', etab)
    surv = creer_user('surv_efbt', 'Dramane', 'Bah', 'surveillant', etab)
    compt = creer_user('compt_efbt', 'Salimata', 'Keita', 'comptable', etab)
    maitres = [creer_enseignant(etab, f'maitre{i}_efbt', random.choice(PRENOMS_M + PRENOMS_F),
                                random.choice(NOMS), 'Enseignement fondamental', 'DEF + IFM', 150000)
               for i in range(1, 4)]
    log('Equipe : directeur, secretariat, surveillant, comptable + 3 maitres')
    codes = [c for c in mats if c != 'COND']
    affecter(annee, classes, mats, [(maitres[0], codes[:3]), (maitres[1], codes[3:5]), (maitres[2], codes[5:])])
    emploi_du_temps(etab, annee, classes)
    remplir_classes(etab, annee, classes, 15, 6, 12)

    if cycle.utilise_compositions_multiples:
        # Compositions /10 liees a l'annee (pas a la periode) : une par trimestre deja commence
        nb = 0
        mats_notes = [m for m in mats.values() if not m.is_conduite]
        for cl in classes:
            a_creer = []
            existants = set(Composition.objects.filter(classe=cl, annee=annee)
                            .values_list('eleve_id', 'matiere_id', 'numero'))
            for insc in inscriptions_de(cl):
                niv = random.uniform(-1.5, 1.5)
                for numero in range(1, len(a_noter) + 1):
                    for m in mats_notes:
                        if (insc.eleve_id, m.pk, numero) in existants:
                            continue
                        n = max(0, min(10, random.uniform(3, 9.5) + niv))
                        a_creer.append(Composition(eleve=insc.eleve, matiere=m, classe=cl, annee=annee,
                                                   numero=numero, note=Decimal(str(round(n, 2))),
                                                   note_max=Decimal('10'), saisi_par=maitres[0].user))
            Composition.objects.bulk_create(a_creer, ignore_conflicts=True)
            nb += len(a_creer)
        log(f'{nb} compositions /10')
    else:
        log('Cycle existant sans compositions multiples -> notes de periode classiques')
        notes_periodes(cycle, classes, mats, a_noter, maitres[0].user, surv)

    frais_et_paiements(etab, annee, [
        ('Frais de scolarite', Decimal('45000'), 'tranches', 3),
        ('Frais inscription', Decimal('10000'), 'unique', 1),
        ('Cantine', Decimal('20000'), 'unique', 1),
    ], compt)
    presences(etab, classes, surv)
    comptes_famille(etab, 'efbt')
    return dir_


# ════════════════════════════════════════════════════════════════════
#  MAIN
# ════════════════════════════════════════════════════════════════════

def main():
    print('=' * 60)
    print('  SmartSchool - Donnees de demonstration')
    print('=' * 60)
    for fn in (demo_lycee, demo_universite, demo_ecole):
        try:
            with transaction.atomic():
                fn()
        except Exception as exc:  # un etablissement en echec n'empeche pas les autres
            import traceback
            traceback.print_exc()
            print(f'  !! ECHEC {fn.__name__} : {exc} (transaction annulee pour cet etablissement)')

    from django.core.cache import cache
    cache.clear()  # badges, annee active, dashboards...

    print('\n' + '=' * 60)
    print('  RESUME')
    print('=' * 60)
    for code in ('LYC-EXC', 'UCADB', 'EFBT'):
        etab = Etablissement.objects.filter(code=code).first()
        if not etab:
            continue
        ann = AnneeScolaire.objects.filter(etablissement=etab, is_active=True).first()
        nel = Eleve.objects.filter(etablissement=etab, is_active=True).count()
        nnp = NotePeriode.objects.filter(classe__etablissement=etab).count()
        nnu = NoteUE.objects.filter(eleve__etablissement=etab).count()
        nco = Composition.objects.filter(classe__etablissement=etab).count()
        npa = Paiement.objects.filter(etablissement=etab, annee=ann).count() if ann else 0
        nus = User.objects.filter(etablissement=etab).count()
        print(f'  [{code:8}] eleves={nel:4} notes={nnp + nnu + nco:6} paiements={npa:4} utilisateurs={nus}')
    print('=' * 60)
    print(f"\nComptes de demo (mot de passe : {'variable DEMO_PASSWORD' if 'DEMO_PASSWORD' in os.environ else PASSWORD}) :")
    print('  LYC-EXC : dir_lycee, sec_lyc, compt_lyc, surv_lyc, prof_math_lyc, eleve_lyc, parent_lyc')
    print('  UCADB   : dir_ucadb, sec_ucadb, compt_ucadb, surv_ucadb, prof_info_ucadb, eleve_ucadb, parent_ucadb')
    print('  EFBT    : dir_efbt, sec_efbt, compt_efbt, surv_efbt, maitre1_efbt, eleve_efbt, parent_efbt')
    print('  Portails : /auth/portail/LYC-EXC/  /auth/portail/UCADB/  /auth/portail/EFBT/')
    if 'DEMO_PASSWORD' not in os.environ:
        print('\n  [!] Mot de passe par defaut utilise. En ligne, definissez DEMO_PASSWORD avant de lancer le script.')


if __name__ == '__main__':
    main()
