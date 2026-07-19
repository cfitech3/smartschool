from django.db import models
from django.utils import timezone


class Notification(models.Model):
    TYPE_NOTE_MODIF = 'note_modif'
    TYPE_NOTE_AJOUT = 'note_ajout'
    TYPE_PAIEMENT   = 'paiement'
    TYPE_ABSENCE    = 'absence'
    TYPE_SYSTEM     = 'systeme'

    TYPES = [
        (TYPE_NOTE_MODIF, 'Modification de note'),
        (TYPE_NOTE_AJOUT, 'Ajout de note'),
        (TYPE_PAIEMENT,   'Paiement'),
        (TYPE_ABSENCE,    'Absence'),
        (TYPE_SYSTEM,     'Systeme'),
    ]

    destinataire = models.ForeignKey('accounts.User', on_delete=models.CASCADE, related_name='notifications')
    type_notif   = models.CharField(max_length=20, choices=TYPES)
    titre        = models.CharField(max_length=200)
    message      = models.TextField()
    lien         = models.CharField(max_length=500, blank=True)
    is_lue       = models.BooleanField(default=False)
    date_creation= models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-date_creation']
        verbose_name = 'Notification'

    def __str__(self):
        return f"{self.titre} → {self.destinataire.username}"

