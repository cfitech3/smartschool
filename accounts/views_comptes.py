"""
Gestion des comptes élève et parent :
- Création automatique à l'inscription
- Fiche d'accès imprimable individuelle
- Génération en masse par classe
"""
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.utils import timezone
from accounts.models import User
from accounts.permissions import role_required
from eleves.models import Eleve, Inscription


def _generer_username(base, tentative=0):
    """Génère un username unique."""
    username = base if tentative == 0 else f"{base}{tentative}"
    if not User.objects.filter(username=username).exists():
        return username
    return _generer_username(base, tentative + 1)


def _mdp_depuis_naissance(eleve):
    """Mot de passe par défaut = date de naissance DDMMYYYY."""
    return eleve.date_naissance.strftime('%d%m%Y')


def creer_compte_eleve(eleve, etab):
    """Crée ou récupère le compte de connexion d'un élève."""
    if eleve.user_compte:
        return eleve.user_compte, False  # déjà existant

    # Username = matricule en minuscules sans tirets
    username = eleve.matricule.lower().replace('-', '').replace(' ', '')
    username = _generer_username(username)
    mdp = _mdp_depuis_naissance(eleve)

    user = User.objects.create_user(
        username=username,
        password=mdp,
        first_name=eleve.prenom,
        last_name=eleve.nom,
        role='eleve',
        etablissement=etab,
    )
    eleve.user_compte = user
    eleve.save()
    return user, True


def creer_compte_parent(eleve, etab):
    """Crée ou récupère le compte parent du tuteur d'un élève."""
    tuteur = eleve.tuteur
    if not tuteur:
        return None, False
    if tuteur.user_compte:
        return tuteur.user_compte, False

    # Username = tel sans espaces/+ ou nom.prenom
    tel = (tuteur.telephone or '').replace('+', '').replace(' ', '').replace('-', '')
    if tel:
        base = f"p{tel[-8:]}"
    else:
        base = f"{tuteur.nom[:4].lower()}{tuteur.prenom[:3].lower()}"
    username = _generer_username(base)
    # Mot de passe = téléphone ou date naissance enfant
    mdp = tel[-8:] if len(tel) >= 8 else _mdp_depuis_naissance(eleve)

    user = User.objects.create_user(
        username=username,
        password=mdp,
        first_name=tuteur.prenom,
        last_name=tuteur.nom,
        role='parent',
        etablissement=etab,
    )
    tuteur.user_compte = user
    tuteur.save()
    return user, True


@login_required
@role_required('admin', 'secretariat')
def generer_acces_eleve(request, eleve_pk):
    """Génère les comptes et affiche la fiche d'accès pour un élève."""
    etab = request.etablissement
    eleve = get_object_or_404(Eleve, pk=eleve_pk, etablissement=etab)

    compte_eleve, cree_eleve = creer_compte_eleve(eleve, etab)
    compte_parent, cree_parent = creer_compte_parent(eleve, etab)

    if cree_eleve:
        messages.success(request, f"Compte élève créé : {compte_eleve.username}")
    if cree_parent:
        messages.success(request, f"Compte parent créé : {compte_parent.username}")
    if not cree_eleve and not cree_parent:
        messages.info(request, "Les comptes existaient déjà.")

    inscription = eleve.get_inscription_active()
    return render(request, 'accounts/fiche_acces.html', {
        'eleve': eleve,
        'etab': etab,
        'inscription': inscription,
        'compte_eleve': compte_eleve,
        'compte_parent': compte_parent,
        'mdp_eleve': _mdp_depuis_naissance(eleve),
        'mdp_parent': (eleve.tuteur.telephone or '').replace('+', '').replace(' ', '')[-8:] if eleve.tuteur else '—',
        'today': timezone.now().date(),
    })


@login_required
@role_required('admin', 'secretariat')
def generer_acces_classe(request, classe_pk):
    """Génère les comptes pour toute une classe et affiche le récap."""
    from etablissements.models import Classe
    etab = request.etablissement
    classe = get_object_or_404(Classe, pk=classe_pk, etablissement=etab)
    inscriptions = classe.inscriptions.filter(is_active=True).select_related('eleve__tuteur')

    resultats = []
    for insc in inscriptions:
        eleve = insc.eleve
        ce, cre_e = creer_compte_eleve(eleve, etab)
        cp, cre_p = creer_compte_parent(eleve, etab)
        resultats.append({
            'eleve': eleve,
            'compte_eleve': ce,
            'compte_parent': cp,
            'mdp_eleve': _mdp_depuis_naissance(eleve),
            'mdp_parent': (eleve.tuteur.telephone or '').replace('+','').replace(' ','')[-8:] if eleve.tuteur else '—',
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
            mdp      = request.POST.get('password', 'admin123')
            if username and prenom and nom:
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
