from django.core.management.base import BaseCommand, CommandError
from etablissements.models import JournalAction


class Command(BaseCommand):
    help = "Vérifie l'intégrité cryptographique (chaîne SHA-256) du journal d'audit JournalAction."

    def handle(self, *args, **options):
        ok, total, erreur = JournalAction.verifier_integrite_chaine()
        if not ok:
            raise CommandError(f"[ALERTE INTEGRITE] {erreur} (après {total} entrées valides).")
        self.stdout.write(self.style.SUCCESS(f"[OK] Chaîne d'audit intacte ({total} entrée(s) scellée(s) vérifiée(s))."))
