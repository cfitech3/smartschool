"""
Management command : update_echeances_retard
=============================================
Met à jour le statut des échéances dépassées de 'a_payer' → 'retard'.

Usage :
    python manage.py update_echeances_retard
    python manage.py update_echeances_retard --etablissement <id>

À planifier via cron (ex: chaque nuit à minuit) :
    0 0 * * * /path/to/venv/bin/python manage.py update_echeances_retard

Ce command remplace l'ancien UPDATE qui était exécuté dans views_alertes.py
à chaque chargement du dashboard (PERF-002).
"""
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone


class Command(BaseCommand):
    help = (
        "Met à jour le statut des échéances de paiement dépassées "
        "(a_payer → retard) selon leur date_limite."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--etablissement',
            type=int,
            default=None,
            metavar='ID',
            help="Filtrer sur un établissement précis (optionnel).",
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            default=False,
            help="Affiche le nombre d'échéances concernées sans les modifier.",
        )

    def handle(self, *args, **options):
        from finances.models import Echeance

        today = timezone.now().date()
        qs = Echeance.objects.filter(statut='a_payer', date_limite__lt=today)

        etab_id = options.get('etablissement')
        if etab_id:
            qs = qs.filter(etablissement_id=etab_id)

        count = qs.count()

        if options['dry_run']:
            self.stdout.write(
                self.style.WARNING(
                    f"[DRY-RUN] {count} échéance(s) seraient marquées en retard."
                )
            )
            return

        if count == 0:
            self.stdout.write(self.style.SUCCESS("✅ Aucune échéance à mettre à jour."))
            return

        updated = qs.update(statut='retard')
        self.stdout.write(
            self.style.SUCCESS(
                f"✅ {updated} échéance(s) marquée(s) en retard "
                f"(date_limite < {today})."
            )
        )
