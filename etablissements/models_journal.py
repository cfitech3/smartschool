"""
Journal des actions du super admin.
Enregistre automatiquement toute intervention sur les établissements et comptes.
"""
from django.db import models
from django.utils import timezone


class JournalAction(models.Model):
    TYPES = [
        ('creer_etab',      'Création établissement'),
        ('modifier_etab',   'Modification établissement'),
        ('suspendre_etab',  'Suspension établissement'),
        ('reactiver_etab',  'Réactivation établissement'),
        ('supprimer_etab',  'Suppression établissement'),
        ('creer_compte',    'Création compte'),
        ('reset_mdp',       'Réinitialisation mot de passe'),
        ('bloquer_compte',  'Blocage compte'),
        ('debloquer_compte','Déblocage compte'),
        ('supprimer_compte','Suppression compte'),
        ('connexion',       'Connexion super admin'),
        ('basculer_etab',   'Basculement établissement'),
        ('export',          'Export rapport'),
        ('autre',           'Autre action'),
    ]

    auteur       = models.ForeignKey('accounts.User', on_delete=models.SET_NULL,
                                     null=True, related_name='actions_journal')
    type_action  = models.CharField(max_length=30, choices=TYPES)
    etablissement= models.ForeignKey('etablissements.Etablissement',
                                     on_delete=models.SET_NULL, null=True, blank=True,
                                     related_name='journal_actions')
    cible        = models.CharField(max_length=200, blank=True,
                                    help_text="Description de la cible (nom étab, username...)")
    detail       = models.TextField(blank=True, help_text="Détail de l'action")
    ip           = models.GenericIPAddressField(null=True, blank=True)
    date         = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ['-date']
        verbose_name = "Journal action"
        verbose_name_plural = "Journal des actions"

    def __str__(self):
        return f"{self.get_type_action_display()} — {self.auteur} — {self.date:%d/%m/%Y %H:%M}"

    @classmethod
    def log(cls, request, type_action, cible='', detail='', etablissement=None):
        """Helper pour enregistrer une action facilement."""
        ip = request.META.get('HTTP_X_FORWARDED_FOR', '').split(',')[0].strip() \
             or request.META.get('REMOTE_ADDR')
        cls.objects.create(
            auteur=request.user if request.user.is_authenticated else None,
            type_action=type_action,
            etablissement=etablissement,
            cible=cible,
            detail=detail,
            ip=ip or None,
        )
