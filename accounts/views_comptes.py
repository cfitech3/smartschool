"""
Gestion des comptes élève et parent :
- Création automatique à l'inscription
- Fiche d'accès imprimable individuelle
- Génération en masse par classe
- Impersonation (mode espionnage) : super_admin peut se connecter comme n'importe quel utilisateur
"""
import re
import secrets
import string

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login as auth_login, update_session_auth_hash
from django.contrib.auth.decorators import login_required
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.contrib import messages
from django.utils import timezone
from accounts.models import User
from accounts.permissions import role_required
from eleves.models import Eleve, Inscription


# Rôles que le Directeur (admin) peut attribuer dans son établissement.
ROLES_STAFF = ['admin', 'secretariat', 'comptable', 'enseignant', 'surveillant']


# ── Génération de noms d'utilisateur ─────────────────────────────────────────

def _generer_username(base):
    """Génère un username unique en ajoutant un suffixe numérique si nécessaire.
    Boucle itérative (pas de récursion) et nettoyage des caractères invalides."""
    base = re.sub(r'[^a-z0-9]', '', (base or '').lower()) or 'user'
    base = base[:28]
    username = base
    tentative = 0
    while User.objects.filter(username=username).exists():
        tentative += 1
        username = f"{base}{tentative}"
    return username


# ── Génération de mots de passe sécurisés ────────────────────────────────────

# Alphabet utilisé pour les mots de passe : lettres minuscules + majuscules + chiffres.
# Les caractères ambigus (0, O, l, I) sont exclus pour faciliter la lecture sur papier.
_ALPHABET_MDP = (
    string.ascii_lowercase.translate(str.maketrans('', '', 'lI'))
    + string.ascii_uppercase.translate(str.maketrans('', '', 'IO'))
    + string.digits.translate(str.maketrans('', '', '01'))
)


def _generer_mot_de_passe(longueur=10):
    """
    Génère un mot de passe aléatoire et cryptographiquement sûr.

    Utilise le module `secrets` (stdlib Python) qui est conçu pour
    la génération de tokens et mots de passe sécurisés, contrairement
    à `random` qui ne doit pas être utilisé à des fins de sécurité.

    Longueur par défaut : 12 caractères (aligné sur AUTH_PASSWORD_VALIDATORS).
    Le mot de passe contient au minimum une lettre majuscule, une lettre
    minuscule et un chiffre pour respecter les exigences de complexité.
    """
    while True:
        mdp = ''.join(secrets.choice(_ALPHABET_MDP) for _ in range(longueur))
        a_majuscule = any(c.isupper() for c in mdp)
        a_minuscule = any(c.islower() for c in mdp)
        a_chiffre = any(c.isdigit() for c in mdp)
        if a_majuscule and a_minuscule and a_chiffre:
            return mdp


def _valider_mdp(request, mdp, user=None):
    """Valide un mot de passe via AUTH_PASSWORD_VALIDATORS. Retourne True si valide."""
    try:
        validate_password(mdp, user=user)
        return True
    except ValidationError as e:
        for err in e.messages:
            messages.error(request, err)
        return False


# ── Création des comptes ──────────────────────────────────────────────────────

def creer_compte_eleve(eleve, etab):
    """
    Crée ou récupère le compte de connexion d'un élève.

    Retourne : (user, cree, mot_de_passe_brut)
    - cree (bool) : True si le compte vient d'être créé.
    - mot_de_passe_brut (str | None) : le mot de passe en clair,
      disponible uniquement à la création. None si le compte existait déjà.
    """
    if eleve.user_compte:
        return eleve.user_compte, False, None  # Compte déjà existant

    # Username = matricule en minuscules, sans tirets ni espaces
    username = _generer_username(eleve.matricule)
    mdp = _generer_mot_de_passe()

    user = User.objects.create_user(
        username=username,
        password=mdp,
        first_name=eleve.prenom,
        last_name=eleve.nom,
        role=User.ROLE_ELEVE,
        etablissement=etab,
    )
    eleve.user_compte = user
    eleve.save()
    return user, True, mdp


def creer_compte_parent(eleve, etab):
    """
    Crée ou récupère le compte parent du tuteur d'un élève.

    Retourne : (user, cree, mot_de_passe_brut)
    - cree (bool) : True si le compte vient d'être créé.
    - mot_de_passe_brut (str | None) : le mot de passe en clair,
      disponible uniquement à la création. None si le compte existait déjà.
    """
    tuteur = eleve.tuteur
    if not tuteur:
        return None, False, None
    if tuteur.user_compte:
        return tuteur.user_compte, False, None

    # Username basé sur le téléphone ou le nom
    tel = re.sub(r'\D', '', tuteur.telephone or '')
    if tel:
        base = f"p{tel[-8:]}"
    else:
        base = f"{(tuteur.nom or '')[:4]}{(tuteur.prenom or '')[:3]}"
    username = _generer_username(base)
    mdp = _generer_mot_de_passe()

    user = User.objects.create_user(
        username=username,
        password=mdp,
        first_name=tuteur.prenom,
        last_name=tuteur.nom,
        role=User.ROLE_PARENT,
        etablissement=etab,
    )
    tuteur.user_compte = user
    tuteur.save()
    return user, True, mdp


# ── Vues ──────────────────────────────────────────────────────────────────────

@login_required
@role_required('admin', 'secretariat')
def generer_acces_eleve(request, eleve_pk):
    """Génère les comptes et affiche la fiche d'accès pour un élève."""
    etab = request.etablissement
    if not etab:
        return redirect('dashboard')
    eleve = get_object_or_404(Eleve, pk=eleve_pk, etablissement=etab)

    compte_eleve, cree_eleve, mdp_eleve = creer_compte_eleve(eleve, etab)
    compte_parent, cree_parent, mdp_parent = creer_compte_parent(eleve, etab)

    if request.method == 'POST' and request.POST.get('action') == 'reinitialiser':
        cible = request.POST.get('cible', 'tous')
        if cible in ('tous', 'eleve') and compte_eleve:
            mdp_eleve = _generer_mot_de_passe()
            compte_eleve.set_password(mdp_eleve)
            compte_eleve.save(update_fields=['password'])
        if cible in ('tous', 'parent') and compte_parent:
            mdp_parent = _generer_mot_de_passe()
            compte_parent.set_password(mdp_parent)
            compte_parent.save(update_fields=['password'])
        messages.success(request, "Nouveaux mots de passe générés avec succès. Imprimez cette fiche immédiatement.")
    else:
        if cree_eleve:
            messages.success(request, f"Compte élève créé : {compte_eleve.username}")
        if cree_parent:
            messages.success(request, f"Compte parent créé : {compte_parent.username}")
        if not cree_eleve and not cree_parent:
            messages.info(request, "Les comptes existaient déjà. Les mots de passe ne sont pas ré-affichés par sécurité.")

    inscription = eleve.get_inscription_active()
    return render(request, 'accounts/fiche_acces.html', {
        'eleve': eleve,
        'etab': etab,
        'inscription': inscription,
        'compte_eleve': compte_eleve,
        'compte_parent': compte_parent,
        # Les mots de passe ne sont disponibles qu'à la création ou après réinitialisation.
        'mdp_eleve': mdp_eleve,
        'mdp_parent': mdp_parent,
        'today': timezone.now().date(),
    })


@login_required
@role_required('admin', 'secretariat')
def generer_acces_classe(request, classe_pk):
    """
    Génère les comptes pour toute une classe et affiche le récapitulatif.

    Les mots de passe générés sont retournés uniquement à la création ou réinitialisation.
    Ils doivent être imprimés immédiatement via la fiche d'accès classe.
    """
    from etablissements.models import Classe
    etab = request.etablissement
    if not etab:
        return redirect('dashboard')
    classe = get_object_or_404(Classe, pk=classe_pk, etablissement=etab)
    inscriptions = classe.inscriptions.filter(is_active=True).select_related('eleve__tuteur')
    reinit_tous = (request.method == 'POST' and request.POST.get('action') == 'reinitialiser')

    resultats = []
    for insc in inscriptions:
        eleve = insc.eleve
        ce, cre_e, mdp_e = creer_compte_eleve(eleve, etab)
        cp, cre_p, mdp_p = creer_compte_parent(eleve, etab)
        if reinit_tous:
            if ce and not mdp_e:
                mdp_e = _generer_mot_de_passe()
                ce.set_password(mdp_e)
                ce.save(update_fields=['password'])
            if cp and not mdp_p:
                mdp_p = _generer_mot_de_passe()
                cp.set_password(mdp_p)
                cp.save(update_fields=['password'])
        resultats.append({
            'eleve': eleve,
            'compte_eleve': ce,
            'compte_parent': cp,
            'mdp_eleve': mdp_e,
            'mdp_parent': mdp_p,
            'nouveau_eleve': cre_e,
            'nouveau_parent': cre_p,
        })

    nb_nouveaux = sum(1 for r in resultats if r['nouveau_eleve'] or r['nouveau_parent'])
    return render(request, 'accounts/fiche_acces_classe.html', {
        'classe': classe,
        'etab': etab,
        'resultats': resultats,
        'nb_nouveaux': nb_nouveaux,
        'today': timezone.now().date(),
    })


def _peut_gerer_compte(acteur, cible):
    """Un admin d'établissement ne peut pas agir sur un super_admin."""
    if cible.role == 'super_admin' and acteur.role != 'super_admin':
        return False
    return True


@login_required
@role_required('admin')
def liste_utilisateurs(request):
    """
    Liste des utilisateurs avec possibilité de créer/modifier.
    Sécurité (P0) : réservé au Directeur (admin) et au super_admin.
    Le secrétariat n'a plus accès à cette vue (escalade de privilèges).
    """
    etab = request.etablissement
    role_filtre = request.GET.get('role', '')
    users = User.objects.filter(etablissement=etab).order_by('role', 'last_name', 'first_name')
    if role_filtre:
        users = users.filter(role=role_filtre)

    if request.method == 'POST':
        if not etab:
            messages.error(request, "Aucun établissement sélectionné.")
            return redirect(request.path)
        action = request.POST.get('action')

        if action == 'creer':
            username = request.POST.get('username', '').strip()
            prenom   = request.POST.get('prenom', '').strip()
            nom      = request.POST.get('nom', '').strip()
            role     = request.POST.get('role', 'enseignant')
            mdp      = request.POST.get('password', '')

            if role not in ROLES_STAFF:
                messages.error(request, "Rôle invalide.")
            elif not (username and prenom and nom):
                messages.error(request, "Tous les champs sont obligatoires.")
            elif not re.match(r'^[\w.@+-]+$', username):
                messages.error(request, "Nom d'utilisateur invalide. Utilisez uniquement des lettres, chiffres et @/./+/-/_")
            elif User.objects.filter(username=username).exists():
                messages.error(request, f"L'identifiant '{username}' est déjà utilisé.")
            elif _valider_mdp(request, mdp, User(username=username, first_name=prenom, last_name=nom)):
                u = User.objects.create_user(
                    username=username, password=mdp,
                    first_name=prenom, last_name=nom,
                    role=role, etablissement=etab,
                )
                messages.success(request, f"Utilisateur '{u.get_full_name()}' créé avec le rôle {u.get_role_display()}.")

        elif action == 'changer_mdp':
            u_pk = request.POST.get('user_pk')
            nouveau_mdp = request.POST.get('nouveau_mdp', '').strip()
            u = get_object_or_404(User, pk=u_pk, etablissement=etab)
            if not _peut_gerer_compte(request.user, u):
                messages.error(request, "Action non autorisée sur ce compte.")
            elif not nouveau_mdp:
                messages.error(request, "Veuillez saisir un nouveau mot de passe.")
            elif _valider_mdp(request, nouveau_mdp, u):
                u.set_password(nouveau_mdp)
                u.save()
                if u.pk == request.user.pk:
                    # Évite la déconnexion brutale de l'utilisateur courant
                    update_session_auth_hash(request, u)
                messages.success(request, f"Mot de passe modifié pour {u.get_full_name()}.")

        elif action == 'modifier_user':
            u_pk      = request.POST.get('user_pk')
            prenom    = request.POST.get('prenom', '').strip()
            nom       = request.POST.get('nom', '').strip()
            username  = request.POST.get('username', '').strip()
            role      = request.POST.get('role', '').strip()
            if not (u_pk and prenom and nom and username and role in ROLES_STAFF):
                messages.error(request, "Tous les champs sont obligatoires et le rôle doit être valide.")
            elif not re.match(r'^[\w.@+-]+$', username):
                messages.error(request, "Identifiant invalide. Utilisez uniquement lettres, chiffres et @/./+/-/_")
            else:
                u = get_object_or_404(User, pk=u_pk, etablissement=etab)
                if not _peut_gerer_compte(request.user, u):
                    messages.error(request, "Action non autorisée sur ce compte.")
                elif u.pk == request.user.pk and role != u.role:
                    messages.error(request, "Vous ne pouvez pas modifier votre propre rôle.")
                elif username != u.username and User.objects.filter(username=username).exists():
                    messages.error(request, f"L'identifiant '{username}' est déjà utilisé.")
                else:
                    u.first_name = prenom
                    u.last_name  = nom
                    u.username   = username
                    u.role       = role
                    u.save()
                    messages.success(request, f"Utilisateur '{u.get_full_name()}' modifié avec succès.")

        elif action == 'toggle_actif':
            u_pk = request.POST.get('user_pk')
            u = get_object_or_404(User, pk=u_pk, etablissement=etab)
            if u == request.user:
                messages.error(request, "Vous ne pouvez pas désactiver votre propre compte.")
            elif not _peut_gerer_compte(request.user, u):
                messages.error(request, "Action non autorisée sur ce compte.")
            else:
                u.is_active = not u.is_active
                u.save()
                messages.success(request, f"Compte {'activé' if u.is_active else 'désactivé'}.")
        return redirect(request.path)

    return render(request, 'accounts/liste_utilisateurs.html', {
        'users': users,
        'roles': User.ROLES,
        'role_filtre': role_filtre,
        'roles_staff': ROLES_STAFF,
        'is_espionnage': bool(request.session.get('_impersonate_original_pk')),
    })


@login_required
def se_connecter_comme(request, user_pk):
    """
    Mode espionnage : permet au super_admin de se connecter en tant qu'un autre utilisateur.
    L'identifiant original est sauvegardé en session pour permettre le retour.
    """
    if request.user.role != 'super_admin':
        messages.error(request, "Accès réservé au Super Administrateur.")
        return redirect('liste_utilisateurs')

    cible = get_object_or_404(User, pk=user_pk)

    # Empêcher de s'impersoner soi-même ou un autre super_admin
    if cible == request.user:
        messages.warning(request, "Vous êtes déjà connecté avec ce compte.")
        return redirect('liste_utilisateurs')
    if cible.role == 'super_admin':
        messages.error(request, "Impossible de se connecter comme un autre Super Administrateur.")
        return redirect('liste_utilisateurs')

    original_pk = request.user.pk
    etab_id = request.session.get('etablissement_id')

    # auth_login() vide la session lors d'un changement d'utilisateur :
    # on écrit donc la clé d'espionnage APRÈS la connexion.
    cible.backend = 'django.contrib.auth.backends.ModelBackend'
    auth_login(request, cible)
    request.session['_impersonate_original_pk'] = original_pk
    if etab_id and not cible.etablissement_id:
        request.session['etablissement_id'] = etab_id

    messages.info(request, f"Mode espionnage actif — connecté comme {cible.get_full_name() or cible.username}. Cliquez sur l'icône pour revenir.")
    return redirect('dashboard')


@login_required
def quitter_espionnage(request):
    """
    Quitte le mode espionnage et reconnecte le super_admin original.
    """
    original_pk = request.session.get('_impersonate_original_pk')
    if not original_pk:
        messages.warning(request, "Vous n'êtes pas en mode espionnage.")
        return redirect('dashboard')

    original = User.objects.filter(pk=original_pk, role='super_admin', is_active=True).first()
    request.session.pop('_impersonate_original_pk', None)
    if not original:
        messages.error(request, "Compte d'origine introuvable ou désactivé.")
        return redirect('dashboard')

    original.backend = 'django.contrib.auth.backends.ModelBackend'
    auth_login(request, original)

    messages.success(request, f"Mode espionnage terminé. Bienvenue à nouveau, {original.get_full_name() or original.username}.")
    return redirect('liste_utilisateurs')
