import time
from django.conf import settings
from django.contrib import messages
from django.contrib.auth import login as auth_login
from django.http import HttpResponseForbidden
from django.shortcuts import redirect
from django.urls import reverse
from core.tenancy import set_tenant_context, reset_tenant_context
from etablissements.models import Etablissement

IMPERSONATE_MAX_SECONDS = 1800  # 30 minutes maximum en mode espionnage
SESSION_TOUCH_INTERVAL_SECONDS = 900  # Rafraîchit l'expiration de session toutes les 15 min max


def _get_etab_cached(etab_id: int | None):
    if not etab_id:
        return None
    from django.core.cache import cache
    ck = f"etab_mw_{etab_id}"
    etab = cache.get(ck)
    if etab is None:
        etab = Etablissement.objects.filter(pk=etab_id).first()
        if etab is not None:
            cache.set(ck, etab, 60)
    return etab


class SecurityHeadersMiddleware:
    """
    Injecte les en-têtes HTTP de défense en profondeur sur chaque réponse :
      - Content-Security-Policy (CSP)
      - Permissions-Policy
      - Referrer-Policy
      - Cross-Origin-Opener-Policy
    """
    CSP_POLICY = (
        "default-src 'self'; "
        "script-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; "
        "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com https://cdn.jsdelivr.net; "
        "font-src 'self' data: https://fonts.gstatic.com https://cdn.jsdelivr.net; "
        "img-src 'self' data: blob:; "
        "connect-src 'self'; "
        "object-src 'none'; "
        "base-uri 'self'; "
        "frame-ancestors 'none'; "
        "form-action 'self'"
    )

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        response.setdefault("Content-Security-Policy", self.CSP_POLICY)
        response.setdefault("Permissions-Policy", "camera=(), microphone=(), geolocation=(), payment=(), usb=()")
        response.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
        response.setdefault("Cross-Origin-Opener-Policy", "same-origin")
        return response


class EtablissementMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        request.etablissement = None
        admin_prefix = "/" + getattr(settings, "ADMIN_URL_PATH", "admin/").lstrip("/")

        # Verrouillage strict de l'interface Django /admin/ au seul Super Administrateur
        if request.path.startswith(admin_prefix):
            if not request.user.is_authenticated:
                return redirect("login")
            if getattr(request.user, "role", None) != "super_admin":
                return HttpResponseForbidden("Accès à la console système réservé au Super Administrateur.")

        enforce_guard = False
        if request.user.is_authenticated:
            now_ts = int(time.time())
            last_touch = request.session.get("_last_touch") or 0
            if (now_ts - int(last_touch)) >= SESSION_TOUCH_INTERVAL_SECONDS:
                request.session["_last_touch"] = now_ts

            # Expiration automatique du mode espionnage après 30 minutes
            orig_pk = request.session.get("_impersonate_original_pk")
            if orig_pk:
                started_at = request.session.get("_impersonate_started_at") or 0
                if started_at and (now_ts - int(started_at)) > IMPERSONATE_MAX_SECONDS:
                    from accounts.models import User
                    request.session.pop("_impersonate_original_pk", None)
                    request.session.pop("_impersonate_started_at", None)
                    original = User.objects.filter(pk=orig_pk, role="super_admin", is_active=True).first()
                    if original:
                        original.backend = "django.contrib.auth.backends.ModelBackend"
                        auth_login(request, original)
                        messages.warning(request, "Session d'espionnage expirée automatiquement après 30 minutes.")
                        return redirect("liste_utilisateurs")

            URLS_LIBRES = [
                reverse("login"), reverse("logout"),
                admin_prefix, "/static/", "/media/",
                "/etablissements/gerer/",
            ]
            path = request.path

            if request.user.role == "super_admin" or request.session.get("_impersonate_original_pk"):
                etab_id = request.session.get("etablissement_id")
                if etab_id:
                    request.etablissement = _get_etab_cached(etab_id)
                if not request.etablissement and getattr(request.user, "etablissement_id", None):
                    request.etablissement = _get_etab_cached(request.user.etablissement_id)
                if not request.etablissement:
                    premier = Etablissement.objects.filter(is_active=True).first()
                    if premier:
                        request.etablissement = premier
                        request.session["etablissement_id"] = premier.pk
                if request.user.role != "super_admin" and request.etablissement:
                    enforce_guard = True

            elif getattr(request.user, "etablissement_id", None):
                etab = _get_etab_cached(request.user.etablissement_id) or request.user.etablissement
                if not etab.is_active and request.user.role != "super_admin":
                    libre = any(path.startswith(u) for u in URLS_LIBRES)
                    if not libre and path != "/acces-bloque/":
                        return redirect("acces_bloque")
                request.etablissement = etab
                enforce_guard = True

        tokens = set_tenant_context(
            getattr(request.etablissement, "pk", None),
            enforce=enforce_guard,
        )
        try:
            return self.get_response(request)
        finally:
            reset_tenant_context(tokens)
