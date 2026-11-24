import datetime
import time
from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login, logout, update_session_auth_hash
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.utils import timezone
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_POST
from .models import User, JournalConnexion
from .totp import (
    build_otpauth_uri,
    consume_backup_code,
    generate_backup_codes,
    generate_totp_secret,
    verify_totp_code,
)

PRE_2FA_MAX_AGE_SECONDS = 300  # 5 minutes pour saisir le code 2FA


def _redirection_sure(request):
    """
    Retourne l'URL cible après connexion en s'assurant qu'elle appartient
    au même hôte (protection contre les open-redirect via ?next=).
    """
    cible = request.GET.get('next', '') or request.POST.get('next', '')
    if cible and url_has_allowed_host_and_scheme(
        url=cible,
        allowed_hosts={request.get_host()},
        require_https=request.is_secure(),
    ):
        return cible
    return 'dashboard'


def _login_rate_limit_state(request):
    """
    Rate-limiting hybride Cache + Base SQL (`JournalConnexion`) sur 15 minutes.
    Garantit le blocage après 5 échecs même sous Gunicorn multi-workers sans Redis.
    """
    from django.core.cache import cache
    ip = request.META.get('REMOTE_ADDR') or 'unknown'
    uname = (request.POST.get('username') or '').strip().lower()
    cache_key = f'login_attempts_{ip}_{uname}'
    cache_attempts = cache.get(cache_key, 0)

    depuis = timezone.now() - datetime.timedelta(minutes=15)
    sql_qs = JournalConnexion.objects.filter(statut='echec', date__gte=depuis)
    if uname:
        sql_qs = sql_qs.filter(username__iexact=uname, ip=ip if ip != 'unknown' else None)
    else:
        sql_qs = sql_qs.filter(ip=ip if ip != 'unknown' else None)
    sql_attempts = sql_qs.count()

    return cache, cache_key, max(cache_attempts, sql_attempts)


def _finaliser_connexion_ou_2fa(request, user, cache, cache_key):
    """Termine la connexion ou redirige vers l'étape TOTP 2FA si activée sur le compte."""
    from django.middleware.csrf import rotate_token
    cache.delete(cache_key)
    cible = _redirection_sure(request)
    if getattr(user, 'totp_enabled', False) and getattr(user, 'totp_secret', ''):
        request.session['_pre_2fa_user_pk'] = user.pk
        request.session['_pre_2fa_ts'] = int(time.time())
        request.session['_pre_2fa_next'] = cible
        return redirect('verify_2fa')
    login(request, user)
    rotate_token(request)
    return redirect(cible)


def login_view(request):
    if request.user.is_authenticated:
        return redirect('dashboard')
    if request.method == 'POST':
        cache, cache_key, attempts = _login_rate_limit_state(request)
        if attempts >= 5:
            messages.error(request, 'Trop de tentatives infructueuses pour ce compte. Veuillez réessayer dans 15 minutes.')
            return render(request, 'accounts/login.html', {})

        user = authenticate(request, username=request.POST.get('username'), password=request.POST.get('password'))
        if user:
            return _finaliser_connexion_ou_2fa(request, user, cache, cache_key)
        cache.set(cache_key, attempts + 1, 900)
        messages.error(request, f'Identifiant ou mot de passe incorrect. ({max(0, 4 - attempts)} essais restants)')
    return render(request, 'accounts/login.html', {})


def login_portail(request, code_etab):
    if request.user.is_authenticated:
        return redirect('dashboard')
    from etablissements.models import Etablissement
    from django.shortcuts import get_object_or_404
    etab = get_object_or_404(Etablissement, code__iexact=code_etab, is_active=True)

    if request.method == 'POST':
        cache, cache_key, attempts = _login_rate_limit_state(request)
        if attempts >= 5:
            messages.error(request, 'Trop de tentatives infructueuses pour ce compte. Veuillez réessayer dans 15 minutes.')
            return render(request, 'accounts/login.html', {'portail_etab': etab})

        user = authenticate(request, username=request.POST.get('username'), password=request.POST.get('password'))
        if user:
            if user.role != 'super_admin' and user.etablissement_id != etab.pk:
                cache.set(cache_key, attempts + 1, 900)
                messages.error(request, "Ce compte n'appartient pas à cet établissement.")
                return render(request, 'accounts/login.html', {'portail_etab': etab})
            return _finaliser_connexion_ou_2fa(request, user, cache, cache_key)
        cache.set(cache_key, attempts + 1, 900)
        messages.error(request, f'Identifiant ou mot de passe incorrect. ({max(0, 4 - attempts)} essais restants)')

    return render(request, 'accounts/login.html', {'portail_etab': etab})


def verify_2fa(request):
    """Seconde étape d'authentification par code TOTP à 6 chiffres ou code de secours."""
    if request.user.is_authenticated:
        return redirect('dashboard')

    user_pk = request.session.get('_pre_2fa_user_pk')
    ts = request.session.get('_pre_2fa_ts') or 0
    if not user_pk or (int(time.time()) - int(ts)) > PRE_2FA_MAX_AGE_SECONDS:
        for k in ('_pre_2fa_user_pk', '_pre_2fa_ts', '_pre_2fa_next'):
            request.session.pop(k, None)
        messages.warning(request, "Session de vérification expirée. Veuillez vous reconnecter.")
        return redirect('login')

    user = User.objects.filter(pk=user_pk, is_active=True).first()
    if not user or not user.totp_enabled:
        return redirect('login')

    if request.method == 'POST':
        from django.core.cache import cache
        from django.middleware.csrf import rotate_token

        ip = request.META.get('REMOTE_ADDR') or 'unknown'
        rl_key = f'2fa_attempts_{ip}_{user.pk}'
        attempts = cache.get(rl_key, 0)
        if attempts >= 5:
            for k in ('_pre_2fa_user_pk', '_pre_2fa_ts', '_pre_2fa_next'):
                request.session.pop(k, None)
            messages.error(request, "Trop de codes 2FA invalides. Veuillez vous reconnecter.")
            return redirect('login')

        code = (request.POST.get('otp_code') or '').strip()
        ok = verify_totp_code(user.totp_secret, code)
        if not ok and '-' in code:
            ok, remaining_hashed = consume_backup_code(user.totp_backup_codes, code)
            if ok:
                user.totp_backup_codes = remaining_hashed
                user.save(update_fields=['totp_backup_codes'])

        if ok:
            cache.delete(rl_key)
            cible = request.session.pop('_pre_2fa_next', 'dashboard')
            request.session.pop('_pre_2fa_user_pk', None)
            request.session.pop('_pre_2fa_ts', None)
            user.backend = 'django.contrib.auth.backends.ModelBackend'
            login(request, user)
            rotate_token(request)
            return redirect(cible)

        cache.set(rl_key, attempts + 1, 600)
        messages.error(request, "Code de vérification invalide.")

    return render(request, 'accounts/verify_2fa.html', {'pending_username': user.username})


@require_POST
def logout_view(request):
    """Déconnexion POST uniquement — protège contre le logout-CSRF via liens GET."""
    logout(request)
    return redirect('login')


@login_required
def profil(request):
    from core.validators import sanitize_uploaded_image
    from core.verification_qr import generer_qr_svg

    nouveaux_codes_secours = request.session.pop('_totp_new_backup_codes', None)
    pending_secret = request.session.get('_totp_pending_secret', '')

    if request.method == 'POST':
        action = request.POST.get('action', '')

        if action == 'changer_mdp':
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

        if action == 'initier_2fa':
            request.session['_totp_pending_secret'] = generate_totp_secret()
            messages.info(request, "Scannez le QR Code avec votre application d'authentification puis saisissez le code à 6 chiffres.")
            return redirect('profil')

        if action == 'activer_2fa':
            code = (request.POST.get('otp_code') or '').strip()
            if not pending_secret or not verify_totp_code(pending_secret, code):
                messages.error(request, "Code à 6 chiffres invalide. Vérifiez l'heure de votre téléphone et réessayez.")
                return redirect('profil')
            plain_codes, hashed_codes = generate_backup_codes()
            request.user.totp_secret = pending_secret
            request.user.totp_enabled = True
            request.user.totp_backup_codes = hashed_codes
            request.user.save(update_fields=['totp_secret', 'totp_enabled', 'totp_backup_codes'])
            request.session.pop('_totp_pending_secret', None)
            request.session['_totp_new_backup_codes'] = plain_codes
            from etablissements.models import JournalAction
            JournalAction.log(
                request, 'autre', cible=request.user.username, etablissement=request.user.etablissement,
                detail=f"Activation de la double authentification (2FA TOTP) par {request.user.username}",
            )
            messages.success(request, "Double authentification (2FA) activée avec succès. Conservez précieusement vos codes de secours.")
            return redirect('profil')

        if action == 'desactiver_2fa':
            mdp = request.POST.get('mot_de_passe_confirm', '')
            if not request.user.check_password(mdp):
                messages.error(request, "Mot de passe incorrect. Impossible de désactiver la 2FA.")
                return redirect('profil')
            request.user.totp_enabled = False
            request.user.totp_secret = ''
            request.user.totp_backup_codes = ''
            request.user.save(update_fields=['totp_enabled', 'totp_secret', 'totp_backup_codes'])
            request.session.pop('_totp_pending_secret', None)
            from etablissements.models import JournalAction
            JournalAction.log(
                request, 'autre', cible=request.user.username, etablissement=request.user.etablissement,
                detail=f"Désactivation de la double authentification (2FA TOTP) par {request.user.username}",
            )
            messages.warning(request, "Double authentification désactivée.")
            return redirect('profil')

        photo = request.FILES.get('photo')
        if photo:
            clean_photo, err = sanitize_uploaded_image(photo)
            if err:
                messages.error(request, err)
                return redirect('profil')
            request.user.photo = clean_photo
            request.user.save(update_fields=['photo'])
            messages.success(request, 'Photo de profil nettoyée (sans EXIF) et mise à jour avec succès.')
            return redirect('profil')

    totp_qr_svg = ''
    if pending_secret and not request.user.totp_enabled:
        uri = build_otpauth_uri(pending_secret, request.user.username)
        totp_qr_svg = generer_qr_svg(uri, size=160)

    return render(request, 'accounts/profil.html', {
        'user': request.user,
        'pending_secret': pending_secret if not request.user.totp_enabled else '',
        'totp_qr_svg': totp_qr_svg,
        'nouveaux_codes_secours': nouveaux_codes_secours,
    })
