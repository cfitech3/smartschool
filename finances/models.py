from decimal import Decimal
from django.core.exceptions import ValidationError
from django.db import models, transaction
from django.db.models import Q
from django.utils import timezone
from django.core.validators import MinValueValidator
from core.tenancy import TenantSafeMixin
import secrets

class TypeFrais(TenantSafeMixin, models.Model):
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

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=Q(montant_defaut__gte=0),
                name='typefrais_montant_non_negatif',
            ),
        ]

    def __str__(self):
        if self.annee:
            return f"{self.nom} ({self.annee.libelle})"
        return self.nom


class ReductionFrais(TenantSafeMixin, models.Model):
    """
    Bourse / remise accordée à un élève sur un type de frais.
    Le champ `montant` contient TOUJOURS le montant effectif déduit (FCFA),
    même en mode pourcentage : il est recalculé dans save() à partir du tarif
    standard du TypeFrais. Le tarif de la classe n'est jamais modifié.
    """
    CATEGORIES = [
        ('bourse_etat',       "Bourse d'État / Nationale"),
        ('bourse_excellence', "Bourse d'excellence / Mérite"),
        ('demi_bourse',       "Demi-bourse"),
        ('fratrie',           "Réduction Fratrie / Famille nombreuse"),
        ('personnel',         "Enfant du personnel"),
        ('prise_en_charge',   "Prise en charge par un tiers (ONG, entreprise...)"),
        ('social',            "Cas social / Dérogation Direction"),
        ('autre',             "Autre réduction"),
    ]
    MODES_CALCUL = [('fixe', 'Montant fixe (FCFA)'), ('pourcentage', 'Pourcentage (%)')]

    etablissement = models.ForeignKey('etablissements.Etablissement', on_delete=models.CASCADE)
    eleve = models.ForeignKey('eleves.Eleve', on_delete=models.CASCADE, related_name='reductions')
    annee = models.ForeignKey('etablissements.AnneeScolaire', on_delete=models.CASCADE)
    type_frais = models.ForeignKey(TypeFrais, on_delete=models.CASCADE)
    categorie = models.CharField(max_length=30, choices=CATEGORIES, default='autre')
    mode_calcul = models.CharField(max_length=15, choices=MODES_CALCUL, default='fixe')
    valeur_pourcentage = models.DecimalField(
        max_digits=5, decimal_places=2, null=True, blank=True,
        validators=[MinValueValidator(0)],
        help_text="Pourcentage de remise (0 à 100) si mode = pourcentage."
    )
    montant = models.DecimalField(max_digits=12, decimal_places=0, default=0, help_text="Montant effectif réduit (FCFA).")
    organisme_tiers = models.CharField(max_length=150, blank=True, help_text="Organisme payeur (État, ONG, Mairie, Entreprise...)")
    motif = models.CharField(max_length=200, blank=True)
    date_accord = models.DateTimeField(default=timezone.now)
    accordee_par = models.ForeignKey('accounts.User', on_delete=models.SET_NULL, null=True, blank=True,
                                     related_name='reductions_accordees')

    class Meta:
        unique_together = ['eleve', 'annee', 'type_frais']
        constraints = [
            models.CheckConstraint(
                condition=Q(montant__gte=0),
                name='reduction_montant_non_negatif',
            ),
            models.CheckConstraint(
                condition=Q(valeur_pourcentage__isnull=True) | (Q(valeur_pourcentage__gte=0) & Q(valeur_pourcentage__lte=100)),
                name='reduction_pourcentage_0_100',
            ),
        ]

    def __str__(self): return f"Réduction de {self.montant} FCFA pour {self.eleve}"

    def calculer_montant(self):
        """Montant effectif (FCFA) borné entre 0 et le tarif standard du frais."""
        from decimal import Decimal, ROUND_HALF_UP
        base = Decimal(str(self.type_frais.montant_defaut or 0))
        if self.mode_calcul == 'pourcentage':
            pct = Decimal(str(self.valeur_pourcentage or 0))
            pct = max(Decimal('0'), min(Decimal('100'), pct))
            val = (base * pct / Decimal('100')).quantize(Decimal('1'), rounding=ROUND_HALF_UP)
        else:
            val = Decimal(str(self.montant or 0))
        return max(Decimal('0'), min(base, val)) if base > 0 else max(Decimal('0'), val)

    def save(self, *args, **kwargs):
        self.montant = self.calculer_montant()
        super().save(*args, **kwargs)

    @property
    def est_exoneration_totale(self):
        return self.type_frais.montant_defaut > 0 and self.montant >= self.type_frais.montant_defaut

    @property
    def libelle_valeur(self):
        if self.mode_calcul == 'pourcentage' and self.valeur_pourcentage is not None:
            return f"-{self.valeur_pourcentage.normalize():f} %"
        return f"-{int(self.montant):,} F".replace(',', ' ')


class Paiement(TenantSafeMixin, models.Model):
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
        constraints = [
            models.CheckConstraint(
                condition=Q(montant__gt=0),
                name='paiement_montant_strictement_positif',
            ),
        ]
        indexes = [
            models.Index(fields=['etablissement', 'statut', '-date_paiement'], name='idx_pay_etab_statut_date'),
            models.Index(fields=['eleve', 'annee', 'type_frais', 'statut'], name='idx_pay_eleve_annee_tf_st'),
        ]

    def __str__(self): return f"{self.eleve.nom_complet} — {self.montant} FCFA"

    @staticmethod
    def _generer_reference_atomique(etablissement_id=None):
        """
        Génère une référence de paiement unique et non-devinable (PAY-XXXXXXXX)
        via CSPRNG (secrets.randbelow) sans contention de verrou inter-établissements
        ni scan COUNT(*).
        """
        for _ in range(20):
            reference = f"PAY-{secrets.randbelow(100_000_000):08d}"
            if not Paiement.objects.filter(reference=reference).exists():
                return reference
        raise RuntimeError("Impossible de générer une référence de paiement unique.")

    def save(self, *args, **kwargs):
        if self.pk:
            orig = Paiement.objects.filter(pk=self.pk).only(
                'montant', 'eleve_id', 'type_frais_id', 'annee_id',
                'etablissement_id', 'reference', 'statut',
            ).first()
            if orig:
                if (
                    Decimal(str(orig.montant)) != Decimal(str(self.montant))
                    or orig.eleve_id != self.eleve_id
                    or orig.type_frais_id != self.type_frais_id
                    or orig.annee_id != self.annee_id
                    or orig.etablissement_id != self.etablissement_id
                    or (orig.reference and orig.reference != self.reference)
                ):
                    raise ValidationError(
                        "Immutabilité comptable : le montant, l'élève, le frais, l'année et la référence "
                        "d'un paiement enregistré ne peuvent pas être modifiés. Annulez le paiement avec motif."
                    )
                if orig.statut == 'annule' and self.statut != 'annule':
                    raise ValidationError("Un paiement annulé est définitif et ne peut pas être réactivé.")
        if not self.reference:
            self.reference = self._generer_reference_atomique(etablissement_id=self.etablissement_id)
        super().save(*args, **kwargs)

    def delete(self, *args, force_system_delete=False, **kwargs):
        self._check_tenant_isolation()
        if not force_system_delete:
            raise ValidationError(
                "Suppression interdite : une pièce de caisse ne peut pas être supprimée. "
                "Utilisez la procédure d'annulation motivée."
            )
        return super().delete(*args, **kwargs)


class Echeance(TenantSafeMixin, models.Model):
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
        constraints = [
            models.CheckConstraint(
                condition=Q(montant__gte=0),
                name='echeance_montant_non_negatif',
            ),
        ]
        indexes = [
            models.Index(fields=['etablissement', 'annee', 'statut', 'date_limite'], name='idx_ech_etab_ann_st_dl'),
            models.Index(fields=['eleve', 'annee', 'type_frais', 'statut'], name='idx_ech_eleve_ann_tf_st'),
        ]

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
