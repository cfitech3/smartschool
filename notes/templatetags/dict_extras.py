from django import template
from django.utils.safestring import mark_safe

register = template.Library()

@register.filter
def get_item(dictionary, key):
    return dictionary.get(key)

@register.filter
def render_tags(text, eleve):
    if not text or not eleve:
        return text
    
    # Remplacement sécurisé des tags
    nom_complet = f"{eleve.nom} {eleve.prenom}"
    text = text.replace('[NOM_ELEVE]', nom_complet)
    text = text.replace('[MATRICULE]', eleve.matricule or '')
    
    date_n = eleve.date_naissance.strftime('%d/%m/%Y') if eleve.date_naissance else ''
    text = text.replace('[DATE_NAISSANCE]', date_n)
    
    # Pour CLASSE, ANNEE_SCOLAIRE, NOM_ECOLE, on pourrait les extraire de eleve ou de l'établissement
    try:
        insc = eleve.inscriptions.filter(is_active=True).first()
        if insc:
            text = text.replace('[CLASSE]', insc.classe.nom)
            text = text.replace('[ANNEE_SCOLAIRE]', insc.annee.libelle)
    except:
        pass
        
    try:
        text = text.replace('[NOM_ECOLE]', eleve.etablissement.nom)
    except:
        pass

    return mark_safe(text)
