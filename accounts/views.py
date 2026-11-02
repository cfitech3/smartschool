from django.shortcuts import render, redirect
from accounts.permissions import role_required
from django.contrib.auth import authenticate, login, logout
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_POST
from .models import User


def _redirection_sure(request):
    """
    Retourne l'URL cible après connexion en s'assurant qu'elle appartient
    au même hôte (protection contre les open-redirect via ?next=).
    """
    cible = request.GET.get('next', '')
    if cible and url_has_allowed_host_and_scheme(
        url=cible,
        allowed_hosts={request.get_host()},
        require_https=request.is_secure(),
    ):
        return cible
    return 'dashboard'

def login_view(request):
    if request.user.is_authenticated: return redirect('dashboard')
    if request.method == 'POST':
        # P3.5 : Rate limiting sur le login
        from django.core.cache import cache
        from django.middleware.csrf import rotate_token

        # IP réelle du client — ne JAMAIS faire confiance à X-Forwarded-For
        # fourni par le client (contournable). On utilise uniquement REMOTE_ADDR
        # (adresse TCP vue par Django/Gunicorn). Si un proxy de confiance est en
        # place, configurer SECURE_PROXY_SSL_HEADER et un middleware dédié.
        ip = request.META.get('REMOTE_ADDR') or 'unknown'
        uname = (request.POST.get('username') or '').strip().lower()

        cache_key = f'login_attempts_{ip}_{uname}'
        attempts = cache.get(cache_key, 0)

        if attempts >= 5:
            messages.error(request, 'Trop de tentatives infructueuses pour ce compte. Veuillez réessayer dans 15 minutes.')
            return render(request, 'accounts/login.html', {})

        user = authenticate(request, username=request.POST.get('username'), password=request.POST.get('password'))
        if user:
            cache.delete(cache_key)  # Réinitialiser après succès
            login(request, user)
            rotate_token(request)    # ← Force un nouveau token CSRF après login
            return redirect(_redirection_sure(request))
        else:
            cache.set(cache_key, attempts + 1, 900)  # Bloquer pendant 15 mins
            messages.error(request, f'Identifiant ou mot de passe incorrect. ({4 - attempts} essais restants)')
    return render(request, 'accounts/login.html', {})

def login_portail(request, code_etab):
    if request.user.is_authenticated: return redirect('dashboard')
    from etablissements.models import Etablissement
    from django.shortcuts import get_object_or_404
    etab = get_object_or_404(Etablissement, code__iexact=code_etab, is_active=True)
    
    if request.method == 'POST':
        # Same rate limiting logic (par IP + identifiant)
        from django.core.cache import cache
        from django.middleware.csrf import rotate_token
        ip = request.META.get('REMOTE_ADDR') or 'unknown'
        uname = (request.POST.get('username') or '').strip().lower()
        cache_key = f'login_attempts_{ip}_{uname}'
        attempts = cache.get(cache_key, 0)
        
        if attempts >= 5:
            messages.error(request, 'Trop de tentatives infructueuses pour ce compte. Veuillez réessayer dans 15 minutes.')
            return render(request, 'accounts/login.html', {'portail_etab': etab})
            
        user = authenticate(request, username=request.POST.get('username'), password=request.POST.get('password'))
        if user:
            if user.role != 'super_admin' and user.etablissement_id != etab.pk:
                cache.set(cache_key, attempts + 1, 900)
                messages.error(request, "Ce compte n'appartient pas à cet établissement.")
                return render(request, 'accounts/login.html', {'portail_etab': etab})
            cache.delete(cache_key)
            login(request, user)
            rotate_token(request)
            return redirect(_redirection_sure(request))
        else:
            cache.set(cache_key, attempts + 1, 900)
            messages.error(request, f'Identifiant ou mot de passe incorrect. ({4 - attempts} essais restants)')
            
    return render(request, 'accounts/login.html', {'portail_etab': etab})

@require_POST
def logout_view(request):
    """Déconnexion POST uniquement — protège contre le logout-CSRF via liens GET."""
    logout(request)
    return redirect('login')

@login_required
def profil(request):
    if request.method == 'POST':
        action = request.POST.get('action', '')
        if action == 'changer_mdp':
            from django.contrib.auth import update_session_auth_hash
            from django.contrib.auth.password_validation import validate_password
            from django.core.exceptions import ValidationError
            ancien_mdp = request.POST.get('ancien_mdp', '')
            nouveau_mdp = request.POST.get('nouveau_mdp', '')
            confirmer_mdp = request.POST.get('confirmer_mdp', '')
            if not request.user.check_password(ancien_mdp):
                messages.error(request, "L'ancien mot de passe est incorrect.")
                return redirect('profil')
            if nouveau_mdp != confirmer_mdp:
                messages.error(request, "Les nouveaux mots de passe ne correspondent pas.")
                return redirect('profil')
            try:
                validate_password(nouveau_mdp, user=request.user)
            except ValidationError as e:
                for err in e.messages:
                    messages.error(request, err)
                return redirect('profil')
            request.user.set_password(nouveau_mdp)
            request.user.save(update_fields=['password'])
            update_session_auth_hash(request, request.user)
            messages.success(request, "Mot de passe modifié avec succès.")
            return redirect('profil')

        photo = request.FILES.get('photo')
        if photo:
            from etablissements.views import _valider_photo
            err = _valider_photo(photo)
            if err:
                messages.error(request, err)
                return redirect('profil')
            request.user.photo = photo
            request.user.save()
            messages.success(request, 'Photo de profil mise à jour avec succès.')
            return redirect('profil')
    return render(request, 'accounts/profil.html', {'user': request.user})
