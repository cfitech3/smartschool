"""
Context processors globaux — SmartSchool ERP
============================================
- global_context : injecte établissement actif, année active, compteurs de
  notifications, et le menu sidebar sérialisé en JSON (source unique de vérité).
"""
import json
import logging
from django.core.cache import cache
from django.urls import reverse, NoReverseMatch
from etablissements.models import AnneeScolaire
from notes.models import LogModificationNote

logger = logging.getLogger(__name__)


def _build_sidebar_json(user, badge_values):
    """
    Construit la liste de menu pour le rôle de cet utilisateur et la sérialise
    en JSON.  Les URL names Django sont résolus en chemins réels via reverse().
    Les valeurs de badges sont injectées depuis badge_values.

    Cette fonction est la SOURCE UNIQUE DE VÉRITÉ pour les menus de navigation.
    Ne plus modifier le bloc 'const MENUS' dans base.html.
    """
    from accounts.permissions import SIDEBAR_ITEMS
    items_raw = SIDEBAR_ITEMS.get(user.role, [])
    items_resolved = []

    for item in items_raw:
        if 'section' in item:
            items_resolved.append({'section': item['section']})
            continue

        resolved = {
            'icon': item.get('icon', ''),
            'label': item.get('label', ''),
        }

        # Résolution de l'URL
        url_name = item.get('url', '')
        try:
            resolved['url'] = reverse(url_name)
        except NoReverseMatch:
            logger.debug("NoReverseMatch pour '%s' (menu sidebar)", url_name)
            resolved['url'] = '#'

        # Valeur de badge (compteur de notifications)
        badge_key = item.get('badge', '')
        if badge_key and badge_key in badge_values:
            resolved['badge'] = badge_values.get(badge_key, 0)

        items_resolved.append(resolved)

    try:
        return json.dumps(items_resolved, ensure_ascii=False)
    except (TypeError, ValueError):
        logger.exception("Erreur sérialisation menu sidebar pour rôle %s", user.role)
        return '[]'


def global_context(request):
    context = {'app_name': 'SmartSchool ERP'}

    if not request.user.is_authenticated:
        return context

    context['current_etablissement'] = getattr(request, 'etablissement', None)

    # ── Compteurs de notifications (admins uniquement) ────────────────────────
    notifs = {}
    if request.etablissement:
        etab_id = request.etablissement.pk

        # P2.6 Cache de l'année active (1 heure)
        cache_key_annee = f"annee_active_{etab_id}"
        annee = cache.get(cache_key_annee)
        if annee is None:
            annee = AnneeScolaire.objects.filter(
                etablissement_id=etab_id, is_active=True
            ).first()
            cache.set(cache_key_annee, annee, 3600)
        context['annee_active'] = annee

        if request.user.is_admin:
            # Cache des compteurs de notifications (5 minutes)
            cache_key_notifs = f"admin_notifs_{etab_id}"
            notifs = cache.get(cache_key_notifs)
            if notifs is None:
                try:
                    from notes.models import Reclamation, MessageFamille
                    notifs = {
                        'notifs_non_lues': LogModificationNote.objects.filter(
                            note_periode__eleve__etablissement_id=etab_id,
                            notif_envoyee=True, notif_lue=False
                        ).count(),
                        'nb_reclamations_attente': Reclamation.objects.filter(
                            eleve__etablissement_id=etab_id, statut='en_attente'
                        ).count(),
                        'nb_messages_non_lus': MessageFamille.objects.filter(
                            etablissement_id=etab_id, statut='non_lu'
                        ).count(),
                    }
                except Exception:
                    logger.exception("Erreur calcul compteurs notifications admin")
                    notifs = {
                        'notifs_non_lues': 0,
                        'nb_reclamations_attente': 0,
                        'nb_messages_non_lus': 0,
                    }
                cache.set(cache_key_notifs, notifs, 300)
            context.update(notifs)

    if request.user.role == 'super_admin':
        cache_key_etabs = "tous_etablissements_actifs"
        etabs = cache.get(cache_key_etabs)
        if etabs is None:
            from etablissements.models import Etablissement
            etabs = list(Etablissement.objects.filter(is_active=True))
            cache.set(cache_key_etabs, etabs, 3600)
        context['tous_etablissements'] = etabs

    # ── Menu sidebar sérialisé en JSON (source unique de vérité) ─────────────
    # Famille/élève : pas de sidebar standard
    if not (request.user.is_parent or request.user.is_eleve_user):
        context['sidebar_menu_json'] = _build_sidebar_json(request.user, notifs)

    return context
