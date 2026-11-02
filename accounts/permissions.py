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
            'bulletins', 'presences', 'emplois', 'documents', 'modeles',
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
            'dashboard', 'notes', 'emplois',
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
        {'icon': '<i class="bi bi-house-door-fill"></i>', 'label': 'Tableau de bord', 'url': 'dashboard', 'key': 'nav_dashboard'},
        {'icon': '<i class="bi bi-buildings-fill"></i>', 'label': 'Établissements', 'url': 'liste_etablissements', 'key': 'nav_etablissements'},
        {'section': 'Administration'},
        {'icon': '<i class="bi bi-people-fill"></i>', 'label': 'Utilisateurs', 'url': 'liste_utilisateurs', 'key': 'nav_utilisateurs'},
    ],
    'admin': [
        {'section': 'Principal'},
        {'icon': '<i class="bi bi-house-door-fill"></i>', 'label': 'Tableau de bord', 'url': 'dashboard', 'key': 'nav_dashboard'},
        {'section': 'Scolarité'},
        {'icon': '<i class="bi bi-person"></i>‍<i class="bi bi-mortarboard-fill"></i>', 'label': 'Élèves', 'url': 'liste_eleves', 'key': 'nav_eleves'},
        {'icon': '<i class="bi bi-buildings-fill"></i>', 'label': 'Classes', 'url': 'liste_classes', 'key': 'nav_classes'},
        {'icon': '<i class="bi bi-mortarboard-fill"></i>', 'label': "Fin d'année", 'url': 'assistant_fin_annee', 'key': 'nav_fin_annee'},
        {'icon': '<i class="bi bi-person"></i>‍<i class="bi bi-buildings-fill"></i>', 'label': 'Enseignants', 'url': 'liste_enseignants', 'key': 'nav_enseignants'},
        {'icon': '<i class="bi bi-clipboard"></i>', 'label': 'Présences', 'url': 'appel_presences', 'key': 'nav_presences'},
        {'icon': '<i class="bi bi-calendar-event"></i>️', 'label': 'Emplois du temps', 'url': 'emploi_du_temps', 'key': 'nav_emplois'},
        {'section': 'Notes'},
        {'icon': '<i class="bi bi-journal-text"></i>', 'label': 'Saisie notes', 'url': 'saisie_notes_mali', 'key': 'nav_notes'},
        {'icon': '<i class="bi bi-bank"></i>', 'label': 'Notes Université', 'url': 'saisie_notes_ue', 'key': 'nav_notes_ue'},
        {'icon': '<i class="bi bi-file-earmark-text"></i>', 'label': 'Bulletins', 'url': 'bulletins_classe_mali', 'key': 'nav_bulletins'},
        {'icon': '<i class="bi bi-calendar3"></i>', 'label': 'Périodes', 'url': 'liste_periodes', 'key': 'nav_periodes'},

        {'section': 'Finances'},
        {'icon': '<i class="bi bi-credit-card"></i>', 'label': 'Paiements', 'url': 'liste_paiements', 'key': 'nav_paiements'},
        {'icon': '<i class="bi bi-graph-up"></i>', 'label': 'Rapport financier', 'url': 'rapport_financier', 'key': 'nav_rapports'},
        {'section': 'Administration'},
        {'icon': '<i class="bi bi-chat-dots-fill"></i>', 'label': 'Messages', 'url': 'admin_messages', 'key': 'nav_admin_messages', 'badge': 'nb_messages_non_lus'},
        {'icon': '<i class="bi bi-envelope-fill"></i>️', 'label': 'Réclamations', 'url': 'liste_reclamations_admin', 'key': 'nav_reclamations_admin', 'badge': 'nb_reclamations_attente'},
        {'icon': '<i class="bi bi-bell-fill"></i>', 'label': 'Logs notes', 'url': 'logs_modifications', 'key': 'nav_logs', 'badge': 'notifs_non_lues'},
        {'icon': '<i class="bi bi-people-fill"></i>', 'label': 'Utilisateurs', 'url': 'liste_utilisateurs', 'key': 'nav_utilisateurs'},
        {'section': 'Configuration'},
        {'icon': '<i class="bi bi-folder2-open"></i>️', 'label': 'Documents', 'url': 'liste_documents', 'key': 'nav_documents'},
        {'icon': '<i class="bi bi-printer-fill"></i>️', 'label': 'Modèles docs', 'url': 'liste_modeles', 'key': 'nav_modeles'},
        {'icon': '<i class="bi bi-bank"></i>️', 'label': 'Divisions', 'url': 'liste_divisions', 'key': 'nav_divisions'},
        {'icon': '<i class="bi bi-mortarboard-fill"></i>', 'label': 'Cycles', 'url': 'liste_cycles', 'key': 'nav_cycles'},
        {'icon': '<i class="bi bi-gear-fill"></i>️', 'label': 'Paramètres', 'url': 'parametres', 'key': 'nav_parametres'},
    ],
    'secretariat': [
        {'section': 'Principal'},
        {'icon': '<i class="bi bi-house-door-fill"></i>', 'label': 'Tableau de bord', 'url': 'dashboard', 'key': 'nav_dashboard'},
        {'section': 'Scolarité'},
        {'icon': '<i class="bi bi-person"></i>‍<i class="bi bi-mortarboard-fill"></i>', 'label': 'Élèves', 'url': 'liste_eleves', 'key': 'nav_eleves'},
        {'icon': '<i class="bi bi-buildings-fill"></i>', 'label': 'Classes', 'url': 'liste_classes', 'key': 'nav_classes'},
        {'icon': '<i class="bi bi-person"></i>‍<i class="bi bi-buildings-fill"></i>', 'label': 'Enseignants', 'url': 'liste_enseignants', 'key': 'nav_enseignants'},
        {'icon': '<i class="bi bi-clipboard"></i>', 'label': 'Présences', 'url': 'appel_presences', 'key': 'nav_presences'},
        {'icon': '<i class="bi bi-calendar-event"></i>️', 'label': 'Emplois du temps', 'url': 'emploi_du_temps', 'key': 'nav_emplois'},
        {'icon': '<i class="bi bi-file-earmark-text"></i>', 'label': 'Bulletins', 'url': 'bulletins_classe_mali', 'key': 'nav_bulletins'},
        {'section': 'Documents'},
        {'icon': '<i class="bi bi-folder2-open"></i>️', 'label': 'Générer docs', 'url': 'liste_documents', 'key': 'nav_documents'},
        {'section': 'Communication'},
        {'icon': '<i class="bi bi-chat-dots-fill"></i>', 'label': 'Messages', 'url': 'admin_messages', 'key': 'nav_admin_messages'},
        {'icon': '<i class="bi bi-envelope-fill"></i>️', 'label': 'Réclamations', 'url': 'liste_reclamations_admin', 'key': 'nav_reclamations_admin'},
    ],
    'comptable': [
        {'section': 'Principal'},
        {'icon': '<i class="bi bi-house-door-fill"></i>', 'label': 'Tableau de bord', 'url': 'dashboard', 'key': 'nav_dashboard'},
        {'section': 'Finances'},
        {'icon': '<i class="bi bi-credit-card"></i>', 'label': 'Paiements', 'url': 'liste_paiements', 'key': 'nav_paiements'},
        {'icon': '<i class="bi bi-cash"></i>', 'label': 'Encaisser', 'url': 'enregistrer_paiement', 'key': 'nav_encaissement'},
        {'icon': '<i class="bi bi-graph-up"></i>', 'label': 'Rapport', 'url': 'rapport_financier', 'key': 'nav_rapports'},
        {'section': 'Personnel'},
        {'icon': '<i class="bi bi-person"></i>‍<i class="bi bi-buildings-fill"></i>', 'label': 'Salaires profs', 'url': 'enseignants_comptable', 'key': 'nav_salaires'},
    ],
    'enseignant': [
        {'section': 'Principal'},
        {'icon': '<i class="bi bi-house-door-fill"></i>', 'label': 'Tableau de bord', 'url': 'dashboard', 'key': 'nav_dashboard'},
        {'section': 'Mon travail'},
        {'icon': '<i class="bi bi-journal-text"></i>', 'label': 'Saisie notes', 'url': 'saisie_notes_mali', 'key': 'nav_notes'},
        {'icon': '<i class="bi bi-bank"></i>', 'label': 'Notes Université', 'url': 'saisie_notes_ue', 'key': 'nav_notes_ue'},
        {'icon': '<i class="bi bi-calendar-event"></i>️', 'label': 'Mon emploi du temps', 'url': 'emploi_du_temps', 'key': 'nav_emplois'},
    ],
    'surveillant': [
        {'section': 'Principal'},
        {'icon': '<i class="bi bi-house-door-fill"></i>', 'label': 'Tableau de bord', 'url': 'dashboard', 'key': 'nav_dashboard'},
        {'section': 'Surveillance'},
        {'icon': '<i class="bi bi-buildings-fill"></i>', 'label': 'Classes', 'url': 'liste_classes', 'key': 'nav_classes'},
        {'icon': '<i class="bi bi-clipboard"></i>', 'label': 'Appel présences', 'url': 'appel_presences', 'key': 'nav_presences'},
        {'icon': '<i class="bi bi-exclamation-triangle-fill text-warning"></i>️', 'label': 'Rapport absences', 'url': 'rapport_absences', 'key': 'nav_absences'},
        {'icon': '<i class="bi bi-bar-chart-fill"></i>', 'label': 'Note conduite', 'url': 'saisie_conduite', 'key': 'nav_conduite'},
        {'icon': '<i class="bi bi-calendar-event"></i>️', 'label': 'Emplois du temps', 'url': 'emploi_du_temps', 'key': 'nav_emplois'},
    ],
}


# ── Type d'établissement ──────────────────────────────────────

# Types d'établissements considérés comme « enseignement supérieur »
TYPES_SUPERIEURS = ('universite', 'centre', 'institut')


def is_etab_superieur(etablissement):
    """True si l'établissement relève de l'enseignement supérieur (notes UE / LMD)."""
    return etablissement is not None and etablissement.type in TYPES_SUPERIEURS


# ── Accès aux bulletins / relevés ─────────────────────────────

# Rôles du personnel autorisés à consulter les bulletins de n'importe quel élève
ROLES_BULLETINS_PERSONNEL = ('super_admin', 'admin', 'secretariat')


def verifier_acces_bulletin(request, eleve):
    """
    Contrôle centralisé d'accès au bulletin / relevé d'un élève.
    - admin, super_admin, secrétariat : accès à tous les élèves de l'établissement
    - parent / élève : uniquement les élèves rattachés (anti-IDOR)
    - tous les autres rôles (enseignant, comptable, surveillant...) : refusé
    Retourne None si l'accès est autorisé, sinon une réponse de redirection.
    """
    from django.shortcuts import redirect
    from django.contrib import messages as dj_messages
    role = request.user.role
    if role == 'super_admin':
        return None
    if role in ROLES_BULLETINS_PERSONNEL and eleve.etablissement_id != getattr(getattr(request, 'etablissement', None), 'pk', None):
        dj_messages.error(request, "Accès refusé. Cet élève n'appartient pas à votre établissement.")
        return redirect('dashboard')
    if role in ROLES_BULLETINS_PERSONNEL:
        return None
    if role in ('parent', 'eleve'):
        from core.views_espace_famille import get_eleves_accessibles
        if get_eleves_accessibles(request.user).filter(pk=eleve.pk).exists():
            return None
        dj_messages.error(request, "Accès refusé. Ce bulletin ne vous appartient pas.")
        return redirect('dashboard')
    dj_messages.error(request, "Accès refusé. Vous n'avez pas accès aux bulletins.")
    return redirect('dashboard')


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
            # Sécurité : seul le super_admin bénéficie d'un accès implicite.
            # Le rôle 'admin' (Directeur) doit être listé explicitement dans `roles`.
            if request.user.role not in roles and request.user.role != 'super_admin':
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


def require_etab(fn):
    """Décorateur centralisé : vérifie que request.etablissement est défini."""
    from functools import wraps
    from django.shortcuts import redirect

    @wraps(fn)
    def wrapper(request, *args, **kwargs):
        if not getattr(request, 'etablissement', None):
            return redirect('dashboard')
        return fn(request, *args, **kwargs)
    return wrapper


def admin_etab_required(fn):
    """Décorateur centralisé : vérifie que l'utilisateur est admin d'établissement et a un établissement actif."""
    from functools import wraps
    from django.shortcuts import redirect

    @wraps(fn)
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated or not request.user.is_admin or not getattr(request, 'etablissement', None):
            return redirect('dashboard')
        return fn(request, *args, **kwargs)
    return wrapper
