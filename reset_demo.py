# -*- coding: utf-8 -*-
"""
=============================================================
SCRIPT DE REMISE A ZERO -- SmartSchool
=============================================================
CONSERVE : Etablissement, Cycles, Niveaux, Classes (vides),
           Annee scolaire, TypeFrais, Matieres, Periodes,
           Comptes staff (directeur, enseignants, etc.)
SUPPRIME  : Eleves, Inscriptions, Presences, Paiements,
            Notes, Bulletins, Logs, Emplois du temps,
            2 etablissements de demo (Lycee, Universite)
=============================================================
"""
import os
import sys
import shutil
from datetime import datetime

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'smartschool.settings')
import django
django.setup()

from django.db import transaction
from etablissements.models import Etablissement, AnneeScolaire, Classe
from eleves.models import Eleve, Inscription, Presence
from finances.models import Paiement, Echeance, TypeFrais
from notes.models import NotePeriode, Periode, Matiere, EmploiDuTemps, LogModificationNote
from accounts.models import User

TARGET_NOM = "Ecole Fondamentale Babemba Traore"

print("=" * 60)
print("REMISE A ZERO -- SmartSchool")
print("Date : " + datetime.now().strftime('%d/%m/%Y %H:%M'))
print("=" * 60)

# -- 1. Sauvegarde automatique --
db_src = os.path.join(os.path.dirname(os.path.abspath(__file__)), "smartschool.db")
backup = db_src.replace(".db", "_BACKUP_" + datetime.now().strftime('%Y%m%d_%H%M%S') + ".db")
if os.path.exists(db_src):
    shutil.copy2(db_src, backup)
    print("\n[OK] Sauvegarde creee : " + os.path.basename(backup))
else:
    print("\n[WARN] Pas de fichier DB trouve pour sauvegarder.")

# -- 2. Confirmation --
print()
print("[ATTENTION] Cette action est IRREVERSIBLE (sauf backup).")
print("  Toutes les donnees fictives seront supprimees.")
print()
reponse = input("Tapez OUI pour confirmer : ").strip().upper()
if reponse != "OUI":
    print("[Annule]")
    sys.exit(0)

print()

# -- 3. Etablissement cible --
etab_principal = Etablissement.objects.filter(nom=TARGET_NOM).first()
if not etab_principal:
    print("ERREUR: Etablissement '" + TARGET_NOM + "' introuvable. Abandon.")
    sys.exit(1)

print("Etablissement conserve : " + etab_principal.nom + " (pk=" + str(etab_principal.pk) + ")")

# -- 4. Suppression en transaction --
try:
    with transaction.atomic():

        # 4a. Supprimer les autres etablissements de demo
        autres = Etablissement.objects.exclude(pk=etab_principal.pk)
        noms_autres = list(autres.values_list('nom', flat=True))

        for e in autres:
            Paiement.objects.filter(etablissement=e).delete()
            Echeance.objects.filter(etablissement=e).delete()
            TypeFrais.objects.filter(etablissement=e).delete()
            User.objects.filter(etablissement=e).delete()
            # Eleves + inscriptions + presences via cascade
            Eleve.objects.filter(etablissement=e).delete()
            e.delete()

        if noms_autres:
            print("[OK] Etablissements supprimes : " + ", ".join(noms_autres))

        etab = etab_principal

        # 4b. Logs
        try:
            LogModificationNote.objects.filter(
                note_periode__eleve__etablissement=etab
            ).delete()
            print("[OK] Logs notes supprimes")
        except Exception as ex:
            print("[WARN] Logs: " + str(ex))

        # 4c. Bulletins (si modele existe)
        try:
            from notes.models import Bulletin
            n_bull = Bulletin.objects.filter(eleve__etablissement=etab).count()
            Bulletin.objects.filter(eleve__etablissement=etab).delete()
            print("[OK] Bulletins supprimes : " + str(n_bull))
        except Exception:
            pass

        # 4d. Notes
        n = NotePeriode.objects.filter(eleve__etablissement=etab).delete()
        print("[OK] Notes supprimees : " + str(n[0]))

        # 4e. Presences
        n = Presence.objects.filter(classe__etablissement=etab).delete()
        print("[OK] Presences supprimees : " + str(n[0]))

        # 4f. Echeances
        n = Echeance.objects.filter(etablissement=etab).delete()
        print("[OK] Echeances supprimees : " + str(n[0]))

        # 4g. Paiements
        n = Paiement.objects.filter(etablissement=etab).delete()
        print("[OK] Paiements supprimes : " + str(n[0]))

        # 4h. Inscriptions
        n = Inscription.objects.filter(classe__etablissement=etab).delete()
        print("[OK] Inscriptions supprimees : " + str(n[0]))

        # 4i. Comptes parents et eleves
        n = User.objects.filter(etablissement=etab, role__in=['parent', 'eleve']).delete()
        print("[OK] Comptes parents/eleves supprimes : " + str(n[0]))

        # 4j. Eleves
        n = Eleve.objects.filter(etablissement=etab).delete()
        print("[OK] Eleves supprimes : " + str(n[0]))

        # 4k. Emplois du temps
        n = EmploiDuTemps.objects.filter(classe__etablissement=etab).delete()
        print("[OK] Emplois du temps supprimes : " + str(n[0]))

    print()
    print("=" * 60)
    print("REMISE A ZERO TERMINEE AVEC SUCCES")
    print("=" * 60)
    print()
    print("ETAT APRES RESET:")
    print("  Eleves en base   : " + str(Eleve.objects.filter(etablissement=etab_principal).count()))
    print("  Paiements        : " + str(Paiement.objects.filter(etablissement=etab_principal).count()))
    print("  Classes (vides)  : " + str(Classe.objects.filter(etablissement=etab_principal).count()))
    print("  Types de frais   : " + str(TypeFrais.objects.filter(etablissement=etab_principal).count()))
    print("  Comptes staff    : " + str(
        User.objects.filter(etablissement=etab_principal).exclude(role__in=['parent','eleve']).count()
    ))
    print()
    print("PROCHAINES ETAPES:")
    print("  1. Lancez le serveur : python manage.py runserver")
    print("  2. Connectez-vous avec le compte directeur")
    print("  3. Allez dans Eleves > Ajouter pour inscrire vos eleves")
    print("     OU utilisez l'import Excel (bientot disponible)")
    print()
    print("Sauvegarde : " + os.path.basename(backup))

except Exception as e:
    print()
    print("ERREUR : " + str(e))
    print("La transaction a ete annulee. Aucune donnee modifiee.")
    import traceback
    traceback.print_exc()
