import re
from django.core.exceptions import ValidationError
from django.utils.translation import gettext as _

# Caractères qui, en tête de cellule, sont interprétés comme des formules
# par Excel/LibreOffice (=WEBSERVICE, +CMD, @SUM...).
_FORMULE_PREFIXES = ('=', '+', '-', '@', '\t', '\r')


def safe_excel_value(value):
    """Neutralise une valeur texte destinée à une cellule Excel/CSV.

    Empêche l'injection de formules : une chaîne saisie par un utilisateur
    (nom, tuteur...) et réexportée ne doit pas pouvoir s'exécuter comme
    formule à l'ouverture du fichier par le comptable ou le directeur.
    """
    if isinstance(value, str) and value.startswith(_FORMULE_PREFIXES):
        return "'" + value
    return value


class ComplexPasswordValidator:
    """
    Valide que le mot de passe contient :
    - Au moins 1 majuscule
    - Au moins 1 minuscule
    - Au moins 1 chiffre
    - Au moins 1 caractère spécial
    """
    def validate(self, password, user=None):
        if not re.search(r'[A-Z]', password):
            raise ValidationError(
                _("Le mot de passe doit contenir au moins une lettre majuscule."),
                code='password_no_upper',
            )
        if not re.search(r'[a-z]', password):
            raise ValidationError(
                _("Le mot de passe doit contenir au moins une lettre minuscule."),
                code='password_no_lower',
            )
        if not re.search(r'[0-9]', password):
            raise ValidationError(
                _("Le mot de passe doit contenir au moins un chiffre."),
                code='password_no_number',
            )
        if not re.search(r'[!@#$%^&*(),.?":{}|<>\-_+=\[\]/]', password):
            raise ValidationError(
                _("Le mot de passe doit contenir au moins un caractère spécial (ex: @, #, $, !...)."),
                code='password_no_symbol',
            )

    def get_help_text(self):
        return _(
            "Votre mot de passe doit contenir au moins 8 caractères, dont une majuscule, "
            "une minuscule, un chiffre et un caractère spécial."
        )
