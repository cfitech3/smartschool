import re
from django.core.exceptions import ValidationError
from django.utils.translation import gettext as _

# Caractères qui, en tête de cellule, sont interprétés comme des formules
# par Excel/LibreOffice (=WEBSERVICE, +CMD, @SUM...).
_FORMULE_PREFIXES = ('=', '+', '-', '@', '\t', '\r', '\n')


def safe_excel_value(value):
    """Neutralise une valeur texte destinée à une cellule Excel/CSV.

    Empêche l'injection de formules : une chaîne saisie par un utilisateur
    (nom, tuteur...) et réexportée ne doit pas pouvoir s'exécuter comme
    formule à l'ouverture du fichier par le comptable ou le directeur.
    """
    if isinstance(value, str):
        stripped = value.lstrip()
        if stripped.startswith(_FORMULE_PREFIXES) or value.startswith(_FORMULE_PREFIXES):
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
            "Votre mot de passe doit contenir au moins 12 caractères, dont une majuscule, "
            "une minuscule, un chiffre et un caractère spécial."
        )


def sanitize_uploaded_image(uploaded_file, max_bytes: int = 2 * 1024 * 1024, max_dim: int = 1600):
    """
    Valide une image uploadée, supprime toutes ses métadonnées EXIF/GPS par
    ré-encodage pixel via Pillow, neutralise tout contenu polyglotte et lui
    attribue un nom UUID4 non-devinable.
    Retourne `(content_file, None)` ou `(None, message_erreur)`.
    """
    import io
    import uuid
    from django.core.files.base import ContentFile
    from PIL import Image, ImageOps

    if not uploaded_file:
        return None, None
    if uploaded_file.size > max_bytes:
        return None, f"L'image ne doit pas dépasser {max_bytes // (1024 * 1024)} Mo."

    nom = (getattr(uploaded_file, "name", "") or "").lower()
    if not nom.endswith((".jpg", ".jpeg", ".png", ".webp")):
        return None, "Format d'image non supporté (JPG, PNG ou WEBP uniquement)."

    try:
        raw_bytes = uploaded_file.read()
        uploaded_file.seek(0)
        probe = Image.open(io.BytesIO(raw_bytes))
        probe.verify()

        img = Image.open(io.BytesIO(raw_bytes))
        img = ImageOps.exif_transpose(img)
        if img.width > max_dim or img.height > max_dim:
            img.thumbnail((max_dim, max_dim), Image.Resampling.LANCZOS)

        # Création d'une image neuve sans aucun bloc EXIF / commentaire
        has_alpha = img.mode in ("RGBA", "LA") or (img.mode == "P" and "transparency" in img.info)
        target_mode = "RGBA" if has_alpha else "RGB"
        converted = img.convert(target_mode)
        clean_img = Image.new(target_mode, converted.size)
        clean_img.putdata(list(converted.getdata()))

        buf = io.BytesIO()
        if has_alpha:
            clean_img.save(buf, format="PNG", optimize=True)
            ext = "png"
        else:
            clean_img.save(buf, format="JPEG", quality=88, optimize=True)
            ext = "jpg"
        safe_name = f"{uuid.uuid4().hex}.{ext}"
        return ContentFile(buf.getvalue(), name=safe_name), None
    except Exception:
        return None, "Le fichier envoyé n'est pas une image valide."
