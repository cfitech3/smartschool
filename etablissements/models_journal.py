"""
Journal d'audit des actions sensibles — Chaînage cryptographique SHA-256 infalsifiable.
Chaque entrée scelle son contenu avec le `hash_integrite` de l'entrée précédente :
toute modification ou suppression a posteriori en base de données rompt la chaîne.
"""
import hashlib
from django.conf import settings
from django.db import models, transaction
from django.utils import timezone


class JournalAction(models.Model):
    TYPES = [
        ('creer_etab',       'Création établissement'),
        ('modifier_etab',    'Modification établissement'),
        ('suspendre_etab',   'Suspension établissement'),
        ('reactiver_etab',   'Réactivation établissement'),
        ('supprimer_etab',   'Suppression établissement'),
        ('creer_compte',     'Création compte'),
        ('reset_mdp',        'Réinitialisation mot de passe'),
        ('bloquer_compte',   'Blocage compte'),
        ('debloquer_compte', 'Déblocage compte'),
        ('supprimer_compte', 'Suppression compte'),
        ('connexion',        'Connexion super admin'),
        ('basculer_etab',    'Basculement établissement'),
        ('export',           'Export rapport'),
        ('autre',            'Autre action'),
    ]

    auteur         = models.ForeignKey('accounts.User', on_delete=models.SET_NULL,
                                       null=True, related_name='actions_journal')
    type_action    = models.CharField(max_length=30, choices=TYPES)
    etablissement  = models.ForeignKey('etablissements.Etablissement',
                                       on_delete=models.SET_NULL, null=True, blank=True,
                                       related_name='journal_actions')
    cible          = models.CharField(max_length=200, blank=True,
                                      help_text="Description de la cible (nom étab, username...)")
    detail         = models.TextField(blank=True, help_text="Détail de l'action")
    ip             = models.GenericIPAddressField(null=True, blank=True)
    date           = models.DateTimeField(default=timezone.now)
    hash_precedent = models.CharField(max_length=64, blank=True, default="GENESIS")
    hash_integrite = models.CharField(max_length=64, blank=True, default="", db_index=True)

    class Meta:
        ordering = ['-date', '-pk']
        verbose_name = "Journal action"
        verbose_name_plural = "Journal des actions"
        indexes = [
            models.Index(fields=['etablissement', '-date'], name='idx_jaction_etab_date'),
        ]

    def __str__(self):
        return f"{self.get_type_action_display()} — {self.auteur} — {self.date:%d/%m/%Y %H:%M}"

    def calculer_hash(self, prev_hash: str) -> str:
        ts_iso = self.date.isoformat() if self.date else ""
        payload = "|".join([
            prev_hash or "GENESIS",
            ts_iso,
            str(self.auteur_id or ""),
            str(self.etablissement_id or ""),
            self.type_action or "",
            self.cible or "",
            self.detail or "",
            str(self.ip or ""),
            settings.SECRET_KEY,
        ])
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()

    def save(self, *args, **kwargs):
        if not self.pk and not self.hash_integrite:
            with transaction.atomic():
                last = (
                    JournalAction.objects.select_for_update()
                    .exclude(hash_integrite="")
                    .order_by("-pk")
                    .only("pk", "hash_integrite")
                    .first()
                )
                self.hash_precedent = last.hash_integrite if last else "GENESIS"
                self.hash_integrite = self.calculer_hash(self.hash_precedent)
                return super().save(*args, **kwargs)
        return super().save(*args, **kwargs)

    @classmethod
    def verifier_integrite_chaine(cls) -> tuple[bool, int, str | None]:
        """
        Parcourt toutes les entrées scellées par ordre chronologique d'insertion (`pk`)
        et vérifie la continuité de la chaîne SHA-256.
        Retourne `(est_intacte, nb_verifies, message_erreur_ou_None)`.
        """
        prev = "GENESIS"
        count = 0
        qs = cls.objects.exclude(hash_integrite="").order_by("pk")
        for entry in qs.iterator():
            if entry.hash_precedent != prev:
                return False, count, f"Rupture de chaînage sur JournalAction #{entry.pk} (attendu {prev[:12]}…, trouvé {entry.hash_precedent[:12]}…)"
            expected = entry.calculer_hash(entry.hash_precedent)
            if entry.hash_integrite != expected:
                return False, count, f"Altération détectée sur JournalAction #{entry.pk} (hash invalide)"
            prev = entry.hash_integrite
            count += 1
        return True, count, None

    @classmethod
    def log(cls, request, type_action, cible='', detail='', etablissement=None):
        """Helper pour enregistrer une action scellée cryptographiquement."""
        ip = request.META.get('REMOTE_ADDR') if request else None
        user = getattr(request, 'user', None)
        return cls.objects.create(
            auteur=user if (user and user.is_authenticated) else None,
            type_action=type_action,
            etablissement=etablissement,
            cible=cible,
            detail=detail,
            ip=ip or None,
        )
