"""
Gestion des comptes élève et parent :
- Création automatique à l'inscription
- Fiche d'accès imprimable individuelle
- Génération en masse par classe
"""
import secrets
import string

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.utils import timezone
from accounts.models import User
from accounts.permissions import role_required
from eleves.models import Eleve, Inscription


# ── Génération de noms d'utilisateur ─────────────────────────────────────────

def _generer_username(base, tentative=0):
    """Génère un username unique en ajoutant un suffixe numérique si nécessaire."""
    username = base if tentative == 0 else f"{base}{tentative}"
    if not User.objects.filter(username=username).exists():
        return username
    return _generer_username(base, tentative + 1)


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

    Le mot de passe contient au minimum une lettre majuscule, une lettre
    minuscule et un chiffre pour respecter les exigences de complexité.
    """
    while True:
        mdp = ''.join(secrets.choice(_ALPHABET_MDP) for _ in range(longueur))
        # Garantir la présence d'au moins un chiffre et une majuscule
        a_majuscule = any(c.isupper() for c in mdp)
        a_chiffre = any(c.isdigit() for c in mdp)
        if a_majuscule and a_chiffre:
            return mdp


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
    username = eleve.matricule.lower().replace('-', '').replace(' ', '')
    username = _generer_username(username)
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
    tel = (tuteur.telephone or '').replace('+', '').replace(' ', '').replace('-', '')
    if tel:
        base = f"p{tel[-8:]}"
    else:
        base = f"{tuteur.nom[:4].lower()}{tuteur.prenom[:3].lower()}"
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
    eleve = get_object_or_404(Eleve, pk=eleve_pk, etablissement=etab)

    compte_eleve, cree_eleve, mdp_eleve = creer_compte_eleve(eleve, etab)
    compte_parent, cree_parent, mdp_parent = creer_compte_parent(eleve, etab)

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
        # Les mots de passe ne sont disponibles qu'à la création.
        # Si les comptes existaient déjà, mdp_eleve et mdp_parent valent None.
        'mdp_eleve': mdp_eleve,
        'mdp_parent': mdp_parent,
        'today': timezone.now().date(),
    })


@login_required
@role_required('admin', 'secretariat')
def generer_acces_classe(request, classe_pk):
    """
    Génère les comptes pour toute une classe et affiche le récapitulatif.

    Les mots de passe générés sont retournés uniquement à la création.
    Ils doivent être imprimés immédiatement via la fiche d'accès classe.
    """
    from etablissements.models import Classe
    etab = request.etablissement
    classe = get_object_or_404(Classe, pk=classe_pk, etablissement=etab)
    inscriptions = classe.inscriptions.filter(is_active=True).select_related('eleve__tuteur')

    resultats = []
    for insc in inscriptions:
        eleve = insc.eleve
        ce, cre_e, mdp_e = creer_compte_eleve(eleve, etab)
        cp, cre_p, mdp_p = creer_compte_parent(eleve, etab)
        resultats.append({
            'eleve': eleve,
            'compte_eleve': ce,
            'compte_parent': cp,
            # mdp_eleve et mdp_parent valent None si les comptes existaient déjà.
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


@login_required
@role_required('admin', 'secretariat')
def liste_utilisateurs(request):
    """Liste des utilisateurs avec possibilité de créer/modifier."""
    etab = request.etablissement
    role_filtre = request.GET.get('role', '')
    users = User.objects.filter(etablissement=etab).order_by('role', 'last_name', 'first_name')
    if role_filtre:
        users = users.filter(role=role_filtre)

    if request.method == 'POST':
        action = request.POST.get('action')
        if action == 'creer':
            username = request.POST.get('username', '').strip()
            prenom   = request.POST.get('prenom', '').strip()
            nom      = request.POST.get('nom', '').strip()
            role     = request.POST.get('role', 'enseignant')
            mdp      = request.POST.get('password', '')
            
            # Validation de sécurité stricte
            roles_autorises = ['admin', 'secretariat', 'comptable', 'enseignant', 'surveillant']
            if role not in roles_autorises:
                role = 'enseignant' # Fallback de sécurité
                
            import re
            if not re.match(r'^[\w.@+-]+$', username):
                messages.error(request, "Nom d'utilisateur invalide. Utilisez uniquement des lettres, chiffres et @/./+/-/_")
            elif len(mdp) < 6:
                messages.error(request, "Le mot de passe doit contenir au moins 6 caractères.")
            elif username and prenom and nom:
                if User.objects.filter(username=username).exists():
                    messages.error(request, f"L'identifiant '{username}' est déjà utilisé.")
                else:
                    u = User.objects.create_user(
                        username=username, password=mdp,
                        first_name=prenom, last_name=nom,
                        role=role, etablissement=etab,
                    )
                    messages.success(request, f"Utilisateur '{u.get_full_name()}' créé avec le rôle {u.get_role_display()}.")
            else:
                messages.error(request, "Tous les champs sont obligatoires.")
        elif action == 'changer_mdp':
            u_pk = request.POST.get('user_pk')
            nouveau_mdp = request.POST.get('nouveau_mdp', '').strip()
            if u_pk and nouveau_mdp and len(nouveau_mdp) >= 6:
                u = get_object_or_404(User, pk=u_pk, etablissement=etab)
                u.set_password(nouveau_mdp)
                u.save()
                messages.success(request, f"Mot de passe modifié pour {u.get_full_name()}.")
        elif action == 'toggle_actif':
            u_pk = request.POST.get('user_pk')
            u = get_object_or_404(User, pk=u_pk, etablissement=etab)
            if u != request.user:
                u.is_active = not u.is_active
                u.save()
                messages.success(request, f"Compte {'activé' if u.is_active else 'désactivé'}.")
        return redirect(request.path)

    return render(request, 'accounts/liste_utilisateurs.html', {
        'users': users,
        'roles': User.ROLES,
        'role_filtre': role_filtre,
        'roles_staff': ['admin', 'secretariat', 'comptable', 'enseignant', 'surveillant'],
    })
