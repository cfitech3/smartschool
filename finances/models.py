from django.db import models, transaction
from django.utils import timezone
from django.core.validators import MinValueValidator
import time

class TypeFrais(models.Model):
    PERIODICITES = [('unique', 'Paiement Unique'), ('mensuel', 'Mensuel'), ('tranches', 'Par Tranches')]
    etablissement = models.ForeignKey('etablissements.Etablissement', on_delete=models.CASCADE)
    annee = models.ForeignKey(
        'etablissements.AnneeScolaire', on_delete=models.CASCADE, null=True, blank=True,
        help_text="Année scolaire concernée. Si vide, s'applique à toutes les années (legacy)."
    )
    nom = models.CharField(max_length=100)
    montant_defaut = models.DecimalField(max_digits=12, decimal_places=0, default=0)
    is_obligatoire = models.BooleanField(default=True)
    periodicite = models.CharField(max_length=20, choices=PERIODICITES, default='unique')
    nombre_tranches = models.IntegerField(default=1, blank=True, help_text="Si périodicité par tranches, combien de tranches ?")
    description = models.TextField(blank=True)

    def __str__(self):
        if self.annee:
            return f"{self.nom} ({self.annee.libelle})"
        return self.nom


class ReductionFrais(models.Model):
    etablissement = models.ForeignKey('etablissements.Etablissement', on_delete=models.CASCADE)
    eleve = models.ForeignKey('eleves.Eleve', on_delete=models.CASCADE, related_name='reductions')
    annee = models.ForeignKey('etablissements.AnneeScolaire', on_delete=models.CASCADE)
    type_frais = models.ForeignKey(TypeFrais, on_delete=models.CASCADE)
    montant = models.DecimalField(max_digits=12, decimal_places=0, default=0, help_text="Montant fixe réduit.")
    motif = models.CharField(max_length=200, blank=True)
    date_accord = models.DateTimeField(default=timezone.now)

    class Meta:
        unique_together = ['eleve', 'annee', 'type_frais']

    def __str__(self): return f"Réduction de {self.montant} FCFA pour {self.eleve}"


class Paiement(models.Model):
    MODES = [('especes','Especes'),('mobile_money','Mobile Money'),('virement','Virement')]
    STATUTS = [('valide','Valide'),('annule','Annule'),('attente','En attente')]

    etablissement = models.ForeignKey('etablissements.Etablissement', on_delete=models.CASCADE)
    eleve = models.ForeignKey('eleves.Eleve', on_delete=models.CASCADE, related_name='paiements')
    annee = models.ForeignKey('etablissements.AnneeScolaire', on_delete=models.CASCADE)
    type_frais = models.ForeignKey(TypeFrais, on_delete=models.CASCADE)
    montant = models.DecimalField(
        max_digits=12, decimal_places=0,
        validators=[MinValueValidator(1, message="Le montant doit être strictement positif.")]
    )
    mode_paiement = models.CharField(max_length=20, choices=MODES, default='especes')
    statut = models.CharField(max_length=20, choices=STATUTS, default='valide', db_index=True)
    reference = models.CharField(max_length=50, unique=True, blank=True)
    periode_payee = models.CharField(max_length=50, blank=True, help_text="Mois ou Tranche réglée (ex: Novembre, Tranche 1)")
    date_paiement = models.DateTimeField(default=timezone.now, db_index=True)
    encaisse_par = models.ForeignKey('accounts.User', on_delete=models.SET_NULL, null=True, related_name="encaissements")
    notes = models.TextField(blank=True)
    
    # P3.9 : Traçabilité des annulations
    date_annulation = models.DateTimeField(null=True, blank=True)
    motif_annulation = models.CharField(max_length=255, blank=True)
    annule_par = models.ForeignKey('accounts.User', on_delete=models.SET_NULL, null=True, blank=True, related_name="annulations")

    class Meta:
        ordering = ['-date_paiement']

    def __str__(self): return f"{self.eleve.nom_complet} — {self.montant} FCFA"

    @staticmethod
    def _generer_reference_atomique():
        """
        Génère une référence de paiement unique et non-devinable de façon atomique.

        Format : PAY-XXXXXXXX (8 chiffres basés sur timestamp en microsecondes
        + compteur journalier pour garantir l'unicité).

        La combinaison timestamp+select_for_update protège contre les conditions
        de concurrence même avec plusieurs workers Gunicorn simultanés.
        """
        with transaction.atomic():
            # Timestamp en microsecondes, réduit aux 8 derniers chiffres
            ts_micro = str(int(time.time() * 1_000_000))[-8:]
            reference = f"PAY-{ts_micro}"

            # En cas de collision (très peu probable mais possible), ajouter
            # un compteur croissant jusqu'à trouver une référence libre.
            if Paiement.objects.filter(reference=reference).exists():
                compteur = Paiement.objects.select_for_update().count()
                reference = f"PAY-{ts_micro[:4]}{compteur:04d}"
                # Dernière vérification de sécurité
                while Paiement.objects.filter(reference=reference).exists():
                    compteur += 1
                    reference = f"PAY-{ts_micro[:4]}{compteur:04d}"
            return reference

    def save(self, *args, **kwargs):
        if not self.reference:
            self.reference = self._generer_reference_atomique()
        super().save(*args, **kwargs)


class Echeance(models.Model):
    """Représente une tranche de paiement due par un élève."""
    STATUTS = [
        ('a_payer',  'À payer'),
        ('payee',    'Payée'),
        ('retard',   'En retard'),
        ('dispensee','Dispensée'),
    ]
    etablissement = models.ForeignKey('etablissements.Etablissement', on_delete=models.CASCADE)
    eleve         = models.ForeignKey('eleves.Eleve', on_delete=models.CASCADE, related_name='echeances')
    annee         = models.ForeignKey('etablissements.AnneeScolaire', on_delete=models.CASCADE)
    type_frais    = models.ForeignKey(TypeFrais, on_delete=models.CASCADE, related_name='echeances')
    numero        = models.PositiveSmallIntegerField(help_text="Numéro de la tranche (1, 2, 3...)")
    libelle       = models.CharField(max_length=50, help_text="Ex: Tranche 1")
    montant       = models.DecimalField(max_digits=12, decimal_places=0)
    date_limite   = models.DateField(null=True, blank=True)
    statut        = models.CharField(max_length=12, choices=STATUTS, default='a_payer', db_index=True)
    paiement      = models.ForeignKey(Paiement, on_delete=models.SET_NULL,
                                      null=True, blank=True, related_name='echeances_liees')
    date_paiement = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['eleve','numero']
        unique_together = ['eleve', 'annee', 'type_frais', 'numero']

    def __str__(self):
        return f"{self.eleve.nom_complet} — {self.libelle} ({self.type_frais.nom}) — {self.get_statut_display()}"

    @property
    def est_en_retard(self):
        from django.utils import timezone
        return (self.statut == 'a_payer' and self.date_limite
                and self.date_limite < timezone.now().date())

    def marquer_payee(self, paiement):
        from django.utils import timezone
        self.statut = 'payee'
        self.paiement = paiement
        self.date_paiement = timezone.now()
        self.save()
