"""
Commande d'audit et de réconciliation comptable — SmartSchool ERP.
Vérifie l'intégrité des écritures de caisse, bourses et échéanciers sur toute la base :
  1. Aucun paiement valide de montant <= 0
  2. Aucune réduction supérieure au tarif standard (quand montant_defaut > 0)
  3. Cohérence entre la somme des tranches d'un échéancier et le net à payer
  4. Cohérence entre le cumul encaissé valide et les tranches marquées 'payee'
"""
from decimal import Decimal
from django.core.management.base import BaseCommand, CommandError
from django.db.models import Sum

from finances.models import Echeance, Paiement, ReductionFrais
from finances.services_bourses import net_a_payer


class Command(BaseCommand):
    help = "Vérifie la cohérence financière (paiements, bourses, échéanciers) sur tous les établissements."

    def handle(self, *args, **options):
        anomalies = []

        # 1. Paiements invalides
        nb_neg = Paiement.objects.filter(montant__lte=0).count()
        if nb_neg:
            anomalies.append(f"{nb_neg} paiement(s) avec montant <= 0.")

        # 2. Réductions dépassant le tarif standard
        for red in ReductionFrais.objects.select_related("type_frais", "eleve"):
            base = Decimal(str(red.type_frais.montant_defaut or 0))
            if base > 0 and Decimal(str(red.montant)) > base:
                anomalies.append(
                    f"ReductionFrais #{red.pk} ({red.eleve}) : réduction {red.montant} > tarif {base}."
                )

        # 3 & 4. Échéanciers par (eleve_id, annee_id, type_frais_id)
        couples = (
            Echeance.objects.values_list("eleve_id", "annee_id", "type_frais_id")
            .distinct()
        )
        for eleve_id, annee_id, tf_id in couples:
            echs = list(
                Echeance.objects.select_related("eleve", "annee", "type_frais")
                .filter(eleve_id=eleve_id, annee_id=annee_id, type_frais_id=tf_id)
                .order_by("numero")
            )
            if not echs:
                continue
            sample = echs[0]
            net = net_a_payer(sample.eleve, sample.annee, sample.type_frais)
            somme_tranches = sum((Decimal(str(e.montant)) for e in echs), Decimal("0"))
            if somme_tranches != net:
                anomalies.append(
                    f"Échéancier déséquilibré ({sample.eleve}, {sample.type_frais.nom}) : "
                    f"somme tranches={somme_tranches} != net={net}."
                )

            paye_caisse = (
                Paiement.objects.filter(
                    eleve_id=eleve_id, annee_id=annee_id, type_frais_id=tf_id, statut="valide"
                ).aggregate(t=Sum("montant"))["t"]
                or Decimal("0")
            )
            somme_payees = sum(
                (Decimal(str(e.montant)) for e in echs if e.statut == "payee"),
                Decimal("0"),
            )
            if somme_payees > paye_caisse:
                anomalies.append(
                    f"Tranches marquées payées ({somme_payees}) > encaissements valides ({paye_caisse}) "
                    f"pour {sample.eleve} ({sample.type_frais.nom})."
                )

        if anomalies:
            for a in anomalies[:20]:
                self.stderr.write(self.style.ERROR(f"  - {a}"))
            raise CommandError(f"[ALERTE COMPTABLE] {len(anomalies)} anomalie(s) financière(s) détectée(s).")

        self.stdout.write(
            self.style.SUCCESS(
                f"[OK] Intégrité financière vérifiée : 0 anomalie ({len(couples)} échéancier(s) contrôlé(s))."
            )
        )
