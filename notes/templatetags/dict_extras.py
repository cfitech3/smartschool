from django import template
from django.utils.safestring import mark_safe
from django.utils.html import escape

register = template.Library()

@register.filter
def get_item(dictionary, key):
    return dictionary.get(key)

@register.filter
def render_tags(text, eleve):
    """
    Substitue les balises [TAG] du modèle de document par les données de l'élève.
    Les valeurs dynamiques sont systématiquement échappées (escape) avant insertion
    pour prévenir toute injection XSS stockée, même si une donnée contient du HTML.
    Le texte du modèle lui-même est la seule source de HTML de confiance.
    """
    if not text or not eleve:
        return text

    # Chaque valeur dynamique est échappée individuellement avant substitution
    nom_complet = f"{eleve.nom} {eleve.prenom}"
    text = text.replace('[NOM_ELEVE]', escape(nom_complet))
    text = text.replace('[MATRICULE]', escape(eleve.matricule or ''))

    date_n = eleve.date_naissance.strftime('%d/%m/%Y') if eleve.date_naissance else ''
    text = text.replace('[DATE_NAISSANCE]', escape(date_n))
    text = text.replace('[LIEU_NAISSANCE]', escape(getattr(eleve, 'lieu_naissance', '') or ''))

    try:
        insc = eleve.inscriptions.filter(is_active=True).first()
        if insc:
            text = text.replace('[CLASSE]', escape(insc.classe.nom))
            text = text.replace('[ANNEE_SCOLAIRE]', escape(insc.annee.libelle))
    except Exception:
        pass

    try:
        text = text.replace('[NOM_ECOLE]', escape(eleve.etablissement.nom))
    except Exception:
        pass

    # mark_safe : le modèle est de confiance, les données insérées sont déjà échappées
    return mark_safe(text)
