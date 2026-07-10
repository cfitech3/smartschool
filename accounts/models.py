from django.contrib.auth.models import AbstractUser
from django.db import models

class User(AbstractUser):
    ROLE_SUPER_ADMIN  = 'super_admin'
    ROLE_ADMIN        = 'admin'
    ROLE_COMPTABLE    = 'comptable'
    ROLE_ENSEIGNANT   = 'enseignant'
    ROLE_SURVEILLANT  = 'surveillant'
    ROLE_SECRETARIAT  = 'secretariat'
    ROLE_PARENT       = 'parent'
    ROLE_ELEVE        = 'eleve'
    ROLE_PERSONNEL    = 'personnel'

    ROLES = [
        (ROLE_SUPER_ADMIN, 'Super Administrateur'),
        (ROLE_ADMIN,       'Administrateur'),
        (ROLE_COMPTABLE,   'Comptable'),
        (ROLE_ENSEIGNANT,  'Enseignant'),
        (ROLE_SURVEILLANT, 'Surveillant General'),
        (ROLE_SECRETARIAT, 'Secrétariat'),
        (ROLE_PARENT,      'Parent'),
        (ROLE_ELEVE,       'Eleve'),
        (ROLE_PERSONNEL,   'Personnel'),
    ]

    role        = models.CharField(max_length=20, choices=ROLES, default=ROLE_PERSONNEL)
    photo       = models.ImageField(upload_to='users/', blank=True, null=True)
    telephone   = models.CharField(max_length=20, blank=True)
    etablissement = models.ForeignKey(
        'etablissements.Etablissement', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='utilisateurs'
    )
    division = models.ForeignKey(
        'etablissements.Division', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='utilisateurs',
        help_text="Division géree (si établissement multi-cycles)"
    )
    date_creation = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Utilisateur'

    def __str__(self):
        return f"{self.get_full_name() or self.username} ({self.get_role_display()})"

    @property
    def is_super_admin(self): return self.role == self.ROLE_SUPER_ADMIN
    @property
    def is_admin(self): return self.role in [self.ROLE_SUPER_ADMIN, self.ROLE_ADMIN]
    @property
    def is_enseignant(self): return self.role == self.ROLE_ENSEIGNANT
    @property
    def is_surveillant(self): return self.role == self.ROLE_SURVEILLANT
    @property
    def is_secretariat(self): return self.role == self.ROLE_SECRETARIAT
    @property
    def is_parent(self): return self.role == self.ROLE_PARENT
    @property
    def is_eleve_user(self): return self.role == self.ROLE_ELEVE
    @property
    def is_comptable(self): return self.role in [self.ROLE_COMPTABLE, self.ROLE_ADMIN, self.ROLE_SUPER_ADMIN]
