"""
Script complementaire : donnees de test riches pour les comptes parent1 et eleve1.
Lancez APRES setup_demo.py.
"""
import os, sys, django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'smartschool.settings')
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
django.setup()

from accounts.models import User
from eleves.models import Eleve, Presence
from finances.models import Paiement, TypeFrais
from notes.models import NotePeriode, Periode, Matiere, Reclamation, LogModificationNote
from etablissements.models import AnneeScolaire
from django.utils import timezone
from decimal import Decimal
import datetime, random

print("="*55)
print("  SmartSchool — Donnees de test Espace Famille")
print("="*55)

# Recuperer les comptes
parent_user  = User.objects.get(username='parent1')
eleve1_user  = User.objects.get(username='eleve1')
directeur    = User.objects.get(username='directeur')
comptable    = User.objects.get(username='comptable')

eleve_parent = Eleve.objects.filter(tuteur=parent_user.profil_tuteur).first()
eleve_user   = eleve1_user.profil_eleve

etab   = eleve_parent.etablissement
annee  = AnneeScolaire.objects.filter(etablissement=etab, is_active=True).first()
p1     = Periode.objects.filter(etablissement=etab, numero=1).first()
p2     = Periode.objects.filter(etablissement=etab, numero=2).first()
today  = timezone.now()
types  = {tf.nom: tf for tf in TypeFrais.objects.filter(etablissement=etab)}
insc_parent = eleve_parent.get_inscription_active()
insc_eleve  = eleve_user.get_inscription_active()

print(f"\n  Eleve parent : {eleve_parent.nom_complet}")
print(f"  Eleve user   : {eleve_user.nom_complet}")


# ── 1. PRESENCES DETAILLEES (eleve parent) ──────────────────
print("\n[1/5] Presences detaillees pour Traore Awa...")
Presence.objects.filter(eleve=eleve_parent).delete()
nb = 0
for delta in range(45):
    date_p = today.date() - datetime.timedelta(days=delta)
    if date_p.weekday() >= 5:
        continue
    classe = insc_parent.classe if insc_parent else None
    if not classe:
        continue
    if delta in [3, 8, 14, 20, 28]:
        statut = 'absent'
        motif  = random.choice(['Maladie', 'Rendez-vous medical', ''])
    elif delta in [5, 17]:
        statut = 'retard'
        motif  = 'Retard de transport'
    elif delta == 10:
        statut = 'justifie'
        motif  = 'Certificat medical fourni'
    else:
        statut = 'present'
        motif  = ''
    Presence.objects.get_or_create(
        eleve=eleve_parent, classe=classe, date=date_p,
        defaults={'statut': statut, 'motif': motif, 'enregistre_par': directeur}
    )
    nb += 1
print(f"   {nb} enregistrements (5 absences, 2 retards, 1 justifie)")

# ── 2. PRESENCES POUR ELEVE1 (Harouna Dagnon) ──────────────
print("\n[2/5] Presences pour Harouna Dagnon...")
Presence.objects.filter(eleve=eleve_user).delete()
nb2 = 0
for delta in range(45):
    date_p = today.date() - datetime.timedelta(days=delta)
    if date_p.weekday() >= 5:
        continue
    classe = insc_eleve.classe if insc_eleve else None
    if not classe:
        continue
    if delta in [2, 15, 30]:
        statut = 'absent'
        motif  = 'Maladie'
    elif delta == 7:
        statut = 'retard'
        motif  = ''
    else:
        statut = 'present'
        motif  = ''
    Presence.objects.get_or_create(
        eleve=eleve_user, classe=classe, date=date_p,
        defaults={'statut': statut, 'motif': motif, 'enregistre_par': directeur}
    )
    nb2 += 1
print(f"   {nb2} enregistrements (3 absences, 1 retard)")

# ── 3. PAIEMENTS : certains OK, certains manquants (retard) ─
print("\n[3/5] Paiements pour les deux eleves...")
Paiement.objects.filter(eleve__in=[eleve_parent, eleve_user], annee=annee).delete()

def creer_paiement(eleve, nom_type, montant, delta_jours, reference_suffix=''):
    tf = types.get(nom_type)
    if not tf:
        return
    Paiement.objects.create(
        etablissement=etab, eleve=eleve, annee=annee,
        type_frais=tf, montant=Decimal(str(montant)),
        mode_paiement=random.choice(['especes','especes','mobile_money']),
        statut='valide',
        date_paiement=today - datetime.timedelta(days=delta_jours),
        encaisse_par=comptable,
    )

# Traore Awa : inscription payee, 3 mois de scolarite payes, examen PAS paye (retard !)
creer_paiement(eleve_parent, "Frais d'inscription", 25000, 85)
creer_paiement(eleve_parent, 'Scolarite mensuelle', 15000, 75)  # Octobre
creer_paiement(eleve_parent, 'Scolarite mensuelle', 15000, 45)  # Novembre
creer_paiement(eleve_parent, 'Scolarite mensuelle', 15000, 15)  # Decembre
creer_paiement(eleve_parent, 'Cantine mensuelle', 8000, 70)
creer_paiement(eleve_parent, 'Cantine mensuelle', 8000, 40)
# PAS de Frais examen -> visible en retard

# Harouna Dagnon : inscription, 2 mois scolarite, PAS de janvier (retard !)
creer_paiement(eleve_user, "Frais d'inscription", 25000, 80)
creer_paiement(eleve_user, 'Scolarite mensuelle', 15000, 72)  # Octobre
creer_paiement(eleve_user, 'Scolarite mensuelle', 15000, 42)  # Novembre
# PAS Decembre ni Frais examen -> retard
creer_paiement(eleve_user, 'Transport mensuel', 6000, 65)

pa = Paiement.objects.filter(eleve=eleve_parent, annee=annee).count()
pe = Paiement.objects.filter(eleve=eleve_user, annee=annee).count()
print(f"   Traore Awa : {pa} paiements (frais examen en retard)")
print(f"   Harouna    : {pe} paiements (decembre + examen en retard)")

# ── 4. NOTES T2 POUR HAROUNA (9A) ───────────────────────────
print("\n[4/5] Notes 2eme Trimestre pour Harouna Dagnon...")
if p2 and insc_eleve:
    matieres = Matiere.objects.filter(etablissement=etab)
    nb_notes = 0
    for mat in matieres:
        if mat.is_conduite:
            base = random.uniform(13, 18)
            NotePeriode.objects.get_or_create(
                eleve=eleve_user, matiere=mat,
                classe=insc_eleve.classe, periode=p2,
                defaults={'note_conduite': Decimal(str(round(base, 1))), 'saisi_par': directeur}
            )
        else:
            base = random.uniform(8, 18)
            mc = round(min(20, max(0, base + random.uniform(-2, 2))), 2)
            mn = round(min(40, max(0, mc * 2 + random.uniform(-4, 4))), 2)
            NotePeriode.objects.get_or_create(
                eleve=eleve_user, matiere=mat,
                classe=insc_eleve.classe, periode=p2,
                defaults={'moy_classe': Decimal(str(mc)), 'moy_compo': Decimal(str(mn)),
                          'note_max_classe': 20, 'note_max_compo': 40, 'saisi_par': directeur}
            )
        nb_notes += 1
    print(f"   {nb_notes} notes T2 creees")
else:
    print("   SKIP (pas de 2eme trimestre ou pas d'inscription)")

# ── 5. RECLAMATIONS DE DEMO ──────────────────────────────────
print("\n[5/5] Reclamations de demonstration...")
Reclamation.objects.filter(eleve__in=[eleve_parent, eleve_user]).delete()

# Reclamation 1 : parent sur note de Maths T1 (en attente)
note_maths = NotePeriode.objects.filter(eleve=eleve_parent, matiere__nom='Mathematiques', periode=p1).first()
if note_maths:
    Reclamation.objects.create(
        note_periode=note_maths, eleve=eleve_parent,
        auteur=parent_user, role_auteur='parent',
        motif=f"La note de Mathematiques de ma fille me semble incorrecte. "
              f"Elle avait obtenu {note_maths.moy_classe}/20 en classe mais je "
              f"pense qu'il y a eu une erreur de saisie. Merci de verifier.",
        statut='en_attente'
    )
    print(f"   Reclamation 1 (parent, Maths T1): EN ATTENTE")

# Reclamation 2 : eleve sur note d'Anglais T1 (en cours de traitement)
note_anglais = NotePeriode.objects.filter(eleve=eleve_user, matiere__nom='Anglais', periode=p1).first()
if note_anglais:
    r2 = Reclamation.objects.create(
        note_periode=note_anglais, eleve=eleve_user,
        auteur=eleve1_user, role_auteur='eleve',
        motif=f"Je pense que ma note d'Anglais ({note_anglais.moy_classe}/20) "
              f"est incorrecte. J'ai eu une meilleure note lors du devoir en classe.",
        statut='en_cours',
        reponse="Votre reclamation est en cours d'examen. Nous verifierons les copies dans les prochains jours.",
        traite_par=directeur,
        date_traitement=timezone.now() - datetime.timedelta(days=1),
    )
    print(f"   Reclamation 2 (eleve, Anglais T1): EN COURS")

# Reclamation 3 : eleve sur note de Physique T1 (rejetee avec explication)
note_pc = NotePeriode.objects.filter(eleve=eleve_user, matiere__nom='Physique/Chimie', periode=p1).first()
if note_pc:
    Reclamation.objects.create(
        note_periode=note_pc, eleve=eleve_user,
        auteur=eleve1_user, role_auteur='eleve',
        motif="Je ne suis pas d'accord avec ma note de Physique/Chimie.",
        statut='rejetee',
        reponse="Apres verification des copies, la note est confirmee. "
                "Le calcul est correct et correspond bien au devoir rendu.",
        traite_par=directeur,
        date_traitement=timezone.now() - datetime.timedelta(days=3),
    )
    print(f"   Reclamation 3 (eleve, Physique T1): REJETEE")

# Reclamation 4 : parent sur note de Redaction T1 (acceptee + note corrigee)
note_red = NotePeriode.objects.filter(eleve=eleve_parent, matiere__nom='Redaction', periode=p1).first()
if note_red:
    ancienne = note_red.moy_classe
    Reclamation.objects.create(
        note_periode=note_red, eleve=eleve_parent,
        auteur=parent_user, role_auteur='parent',
        motif="Il y a eu une erreur de saisie sur la note de Redaction. "
              "Le professeur nous a confirme oralement que la note est plus haute.",
        statut='acceptee',
        reponse=f"Apres verification, une erreur de saisie a ete confirmee. "
                f"La note a ete corrigee de {ancienne}/20 a {min(20, float(ancienne)+2)}/20.",
        traite_par=directeur,
        date_traitement=timezone.now() - datetime.timedelta(days=2),
    )
    # Corriger la note
    LogModificationNote.objects.create(
        note_periode=note_red, modifie_par=directeur, role_modifiant='admin',
        champ_modifie='moy_classe', valeur_avant=str(note_red.moy_classe),
        valeur_apres=str(min(20, float(note_red.moy_classe)+2)),
        notif_envoyee=False,
    )
    note_red.moy_classe = min(Decimal('20'), note_red.moy_classe + Decimal('2'))
    note_red.modifie_par = directeur
    note_red.save()
    print(f"   Reclamation 4 (parent, Redaction T1): ACCEPTEE + note corrigee")

print("\n" + "="*55)
print("  DONNEES DE TEST FAMILLE TERMINEES !")
print("="*55)
print("\n  Comptes de test :")
print("  parent1 / parent123  → 5 absences, 1 retard paiement, 2 reclamations")
print("  eleve1  / eleve123   → 3 absences, 2 retards paiement, 3 reclamations")
print("\n  Pages a tester :")
print("  /espace/             → choix enfant (parent) ou redirect (eleve)")
print("  /espace/<id>/paiements/  → frais payes + en retard en rouge")
print("  /espace/<id>/absences/   → historique 45 jours")
print("  /espace/<id>/notes/      → bouton Reclamer par matiere")
print("  /espace/<id>/reclamations/ → statuts varies")
print("  /reclamations/           → admin voit tout")
print("="*55)


# ── 6. MESSAGES DE DEMONSTRATION ────────────────────────────
comptable = User.objects.get(username='comptable')
surveil = User.objects.get(username='surveillant')
print("\n[6/6] Messages de demonstration...")
from notes.models import MessageFamille

MessageFamille.objects.filter(etablissement=etab).delete()

# Message 1 : parent vers directeur (non lu)
MessageFamille.objects.create(
    etablissement=etab,
    expediteur=parent_user,
    eleve=eleve_parent,
    destinataire_role='directeur',
    destinataire_user=directeur,
    sujet='Demande de rendez-vous',
    corps="Bonjour Monsieur le Directeur,\n\nJe souhaiterais avoir un rendez-vous avec vous concernant les resultats de ma fille Traore Awa. Elle a eu quelques difficultes ce trimestre et j'aimerais discuter des moyens de l'aider.\n\nMerci de me contacter au +223 76 11 22 33.\n\nCordialement,\nM. Traore Moussa",
    statut='non_lu',
)

# Message 2 : parent vers comptable (lu, non repondu)
MessageFamille.objects.create(
    etablissement=etab,
    expediteur=parent_user,
    eleve=eleve_parent,
    destinataire_role='comptable',
    destinataire_user=comptable,
    sujet='Question sur les frais d\'examen',
    corps="Bonjour,\n\nJe n'ai pas encore paye les frais d'examen pour ma fille. Est-ce que je peux passer regler ca avant la fin de la semaine ?\n\nMerci",
    statut='lu',
)

# Message 3 : eleve vers surveillant (repondu)
import datetime as dt2
msg3 = MessageFamille.objects.create(
    etablissement=etab,
    expediteur=eleve1_user,
    eleve=eleve_user,
    destinataire_role='surveillant',
    destinataire_user=surveil,
    sujet='Justificatif absence du 15 janvier',
    corps="Bonjour,\n\nJe vous fais parvenir ce message pour justifier mon absence du 15 janvier. J'avais un rendez-vous medical urgent. Le certificat a ete remis a la secretaria.\n\nCordialement,\nHarouna Dagnon",
    statut='repondu',
    reponse="Bonjour Harouna,\n\nMerci pour votre message. J'ai bien pris note de votre absence. Le certificat medical a ete recu et valide. Votre absence est donc justifiee dans notre systeme.\n\nCordialement,\nLe Surveillant General",
    repondu_par=surveil,
    date_reponse=timezone.now() - datetime.timedelta(days=2),
)

# Message 4 : eleve vers un enseignant (non lu)
enseignant_maths = User.objects.filter(etablissement=etab, username='bdiallo').first()
MessageFamille.objects.create(
    etablissement=etab,
    expediteur=eleve1_user,
    eleve=eleve_user,
    destinataire_role='enseignant',
    destinataire_user=enseignant_maths,
    sujet='Question sur le cours de Mathematiques',
    corps="Bonjour Monsieur,\n\nJ'ai du mal a comprendre la lecon sur les equations du second degre. Pourriez-vous me donner des exercices supplementaires ou m'expliquer la methode de resolution ?\n\nMerci beaucoup.",
    statut='non_lu',
)

total = MessageFamille.objects.count()
non_lus = MessageFamille.objects.filter(statut='non_lu').count()
print(f"   {total} messages crees ({non_lus} non lus)")
print(f"   - Demande RDV directeur (non lu)")
print(f"   - Question frais comptable (lu)")
print(f"   - Justificatif surveillant (repondu)")
print(f"   - Question maths enseignant (non lu)")

print("\n" + "="*55)
print("  SETUP TEST FAMILLE COMPLET !")
print("="*55)
print("\n  Nouvelles pages a tester :")
print("  /espace/<id>/messages/         → liste messages")
print("  /espace/<id>/messages/nouveau/ → envoyer (choisir destinataire)")
print("  /messages/                     → admin voit tous les messages")
print("  /messages/<pk>/                → admin repond")
