"""
Système de permissions SmartSchool.
Chaque rôle a un périmètre défini. Les vues utilisent les décorateurs
de ce module pour contrôler l'accès.
"""

# ── Définition des permissions par rôle ──────────────────────

PERMISSIONS = {
    'super_admin': {
        'label': 'Super Administrateur',
        'tout': True,  # accès total
    },
    'admin': {
        'label': 'Directeur',
        'modules': [
            'dashboard', 'eleves', 'classes', 'enseignants',
            'notes', 'bulletins', 'presences', 'emplois',
            'finances', 'paiements', 'documents', 'modeles',
            'parametres', 'cycles', 'divisions', 'utilisateurs',
            'reclamations', 'messages', 'logs', 'rapports',
        ],
    },
    'secretariat': {
        'label': 'Secrétariat',
        'modules': [
            'dashboard', 'eleves', 'classes', 'enseignants',
            'presences', 'emplois', 'documents', 'modeles',
            'reclamations', 'messages',
        ],
    },
    'comptable': {
        'label': 'Comptable',
        'modules': [
            'dashboard', 'paiements', 'finances', 'rapports',
            'salaires',
        ],
    },
    'enseignant': {
        'label': 'Enseignant',
        'modules': [
            'dashboard', 'notes', 'bulletins', 'emplois',
        ],
        'restrictions': {
            'notes': 'ses_matieres',     # seulement ses matières
            'emplois': 'ses_classes',    # seulement ses classes
        },
    },
    'surveillant': {
        'label': 'Surveillant Général',
        'modules': [
            'dashboard', 'classes', 'presences', 'emplois',
            'conduite', 'absences',
        ],
    },
    'parent': {
        'label': 'Parent',
        'modules': ['espace_famille'],
    },
    'eleve': {
        'label': 'Élève',
        'modules': ['espace_famille'],
    },
}

# ── Sidebar items par rôle ────────────────────────────────────

SIDEBAR_ITEMS = {
    'super_admin': [
        {'section': 'Vue globale'},
        {'icon': '🏠', 'label': 'Tableau de bord', 'url': 'dashboard', 'key': 'nav_dashboard'},
        {'icon': '🏫', 'label': 'Établissements', 'url': 'etablissements', 'key': 'nav_etablissements'},
        {'section': 'Administration'},
        {'icon': '👥', 'label': 'Utilisateurs', 'url': 'liste_utilisateurs', 'key': 'nav_utilisateurs'},
    ],
    'admin': [
        {'section': 'Principal'},
        {'icon': '🏠', 'label': 'Tableau de bord', 'url': 'dashboard', 'key': 'nav_dashboard'},
        {'section': 'Scolarité'},
        {'icon': '👨‍🎓', 'label': 'Élèves', 'url': 'liste_eleves', 'key': 'nav_eleves'},
        {'icon': '🏫', 'label': 'Classes', 'url': 'liste_classes', 'key': 'nav_classes'},
        {'icon': '🎓', 'label': "Fin d'année", 'url': 'assistant_fin_annee', 'key': 'nav_fin_annee'},
        {'icon': '👩‍🏫', 'label': 'Enseignants', 'url': 'liste_enseignants', 'key': 'nav_enseignants'},
        {'icon': '📋', 'label': 'Présences', 'url': 'appel_presences', 'key': 'nav_presences'},
        {'icon': '🗓️', 'label': 'Emplois du temps', 'url': 'emploi_du_temps', 'key': 'nav_emplois'},
        {'section': 'Notes'},
        {'icon': '📝', 'label': 'Saisie notes', 'url': 'saisie_notes_mali', 'key': 'nav_notes'},
        {'icon': '📄', 'label': 'Bulletins', 'url': 'bulletins_classe_mali', 'key': 'nav_bulletins'},
        {'icon': '🏛️', 'label': 'Notes Université', 'url': 'saisie_notes_ue', 'key': 'nav_notes_ue'},
        {'section': 'Finances'},
        {'icon': '💳', 'label': 'Paiements', 'url': 'liste_paiements', 'key': 'nav_paiements'},
        {'icon': '📈', 'label': 'Rapport financier', 'url': 'rapport_financier', 'key': 'nav_rapports'},
        {'section': 'Administration'},
        {'icon': '💬', 'label': 'Messages', 'url': 'admin_messages', 'key': 'nav_admin_messages', 'badge': 'nb_messages_non_lus'},
        {'icon': '✉️', 'label': 'Réclamations', 'url': 'liste_reclamations_admin', 'key': 'nav_reclamations_admin', 'badge': 'nb_reclamations_attente'},
        {'icon': '🔔', 'label': 'Logs notes', 'url': 'logs_modifications', 'key': 'nav_logs', 'badge': 'notifs_non_lues'},
        {'icon': '👥', 'label': 'Utilisateurs', 'url': 'liste_utilisateurs', 'key': 'nav_utilisateurs'},
        {'section': 'Configuration'},
        {'icon': '🗂️', 'label': 'Documents', 'url': 'liste_documents', 'key': 'nav_documents'},
        {'icon': '🖨️', 'label': 'Modèles docs', 'url': 'liste_modeles', 'key': 'nav_modeles'},
        {'icon': '🏛️', 'label': 'Divisions', 'url': 'liste_divisions', 'key': 'nav_divisions'},
        {'icon': '🎓', 'label': 'Cycles', 'url': 'liste_cycles', 'key': 'nav_cycles'},
        {'icon': '⚙️', 'label': 'Paramètres', 'url': 'parametres', 'key': 'nav_parametres'},
    ],
    'secretariat': [
        {'section': 'Principal'},
        {'icon': '🏠', 'label': 'Tableau de bord', 'url': 'dashboard', 'key': 'nav_dashboard'},
        {'section': 'Scolarité'},
        {'icon': '👨‍🎓', 'label': 'Élèves', 'url': 'liste_eleves', 'key': 'nav_eleves'},
        {'icon': '🏫', 'label': 'Classes', 'url': 'liste_classes', 'key': 'nav_classes'},
        {'icon': '👩‍🏫', 'label': 'Enseignants', 'url': 'liste_enseignants', 'key': 'nav_enseignants'},
        {'icon': '📋', 'label': 'Présences', 'url': 'appel_presences', 'key': 'nav_presences'},
        {'icon': '🗓️', 'label': 'Emplois du temps', 'url': 'emploi_du_temps', 'key': 'nav_emplois'},
        {'section': 'Documents'},
        {'icon': '🗂️', 'label': 'Générer docs', 'url': 'liste_documents', 'key': 'nav_documents'},
        {'section': 'Communication'},
        {'icon': '💬', 'label': 'Messages', 'url': 'admin_messages', 'key': 'nav_admin_messages'},
        {'icon': '✉️', 'label': 'Réclamations', 'url': 'liste_reclamations_admin', 'key': 'nav_reclamations_admin'},
    ],
    'comptable': [
        {'section': 'Principal'},
        {'icon': '🏠', 'label': 'Tableau de bord', 'url': 'dashboard', 'key': 'nav_dashboard'},
        {'section': 'Finances'},
        {'icon': '💳', 'label': 'Paiements', 'url': 'liste_paiements', 'key': 'nav_paiements'},
        {'icon': '💵', 'label': 'Encaisser', 'url': 'enregistrer_paiement', 'key': 'nav_encaissement'},
        {'icon': '📈', 'label': 'Rapport', 'url': 'rapport_financier', 'key': 'nav_rapports'},
        {'section': 'Personnel'},
        {'icon': '👩‍🏫', 'label': 'Salaires profs', 'url': 'liste_enseignants', 'key': 'nav_salaires'},
    ],
    'enseignant': [
        {'section': 'Principal'},
        {'icon': '🏠', 'label': 'Tableau de bord', 'url': 'dashboard', 'key': 'nav_dashboard'},
        {'section': 'Mon travail'},
        {'icon': '📝', 'label': 'Saisie notes', 'url': 'saisie_notes_mali', 'key': 'nav_notes'},
        {'icon': '📄', 'label': 'Bulletins', 'url': 'bulletins_classe_mali', 'key': 'nav_bulletins'},
        {'icon': '🗓️', 'label': 'Mon emploi du temps', 'url': 'emploi_du_temps', 'key': 'nav_emplois'},
    ],
    'surveillant': [
        {'section': 'Principal'},
        {'icon': '🏠', 'label': 'Tableau de bord', 'url': 'dashboard', 'key': 'nav_dashboard'},
        {'section': 'Surveillance'},
        {'icon': '🏫', 'label': 'Classes', 'url': 'liste_classes', 'key': 'nav_classes'},
        {'icon': '📋', 'label': 'Appel présences', 'url': 'appel_presences', 'key': 'nav_presences'},
        {'icon': '⚠️', 'label': 'Rapport absences', 'url': 'rapport_absences', 'key': 'nav_absences'},
        {'icon': '📊', 'label': 'Note conduite', 'url': 'saisie_conduite', 'key': 'nav_conduite'},
        {'icon': '🗓️', 'label': 'Emplois du temps', 'url': 'emploi_du_temps', 'key': 'nav_emplois'},
    ],
}


def get_sidebar_items(user):
    """Retourne les items de sidebar pour un utilisateur."""
    if user.role == 'super_admin':
        return SIDEBAR_ITEMS.get('super_admin', [])
    return SIDEBAR_ITEMS.get(user.role, [])


def has_permission(user, module):
    """Vérifie si un utilisateur a accès à un module."""
    if not user.is_authenticated:
        return False
    # super_admin et admin ont toujours accès à tout
    if user.role in ('super_admin', 'admin'):
        return True
    perms = PERMISSIONS.get(user.role, {})
    if perms.get('tout'):
        return True
    return module in perms.get('modules', [])


def role_required(*roles):
    """Décorateur : restreint une vue à certains rôles.
    Accepte aussi bien @role_required('admin', 'surveillant')
    que @role_required(['admin', 'surveillant']).
    """
    from functools import wraps
    from django.shortcuts import redirect
    from django.contrib import messages as dj_messages
    # Aplatir si une liste est passée comme premier arg
    if len(roles) == 1 and isinstance(roles[0], (list, tuple)):
        roles = tuple(roles[0])

    def decorator(fn):
        @wraps(fn)
        def wrapper(request, *args, **kwargs):
            if not request.user.is_authenticated:
                return redirect('login')
            if request.user.role not in roles and request.user.role not in ('super_admin', 'admin'):
                dj_messages.error(request, "Accès refusé. Vous n'avez pas les droits nécessaires.")
                return redirect('dashboard')
            return fn(request, *args, **kwargs)
        return wrapper
    return decorator


def permission_required(module):
    """Décorateur : restreint une vue selon le module."""
    from functools import wraps
    from django.shortcuts import redirect
    from django.contrib import messages as dj_messages

    def decorator(fn):
        @wraps(fn)
        def wrapper(request, *args, **kwargs):
            if not request.user.is_authenticated:
                return redirect('login')
            if not has_permission(request.user, module):
                dj_messages.error(request, f"Accès refusé à ce module.")
                return redirect('dashboard')
            return fn(request, *args, **kwargs)
        return wrapper
    return decorator
