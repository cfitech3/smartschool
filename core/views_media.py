"""
Service sécurisé des fichiers médias (`/media/`) avec contrôle d'accès Multi-Tenant.

- Les logos d'établissements / divisions / plateforme restent publics (page de login).
- Les photos d'élèves (mineurs) et d'utilisateurs exigent une authentification
  et vérifient le rattachement au même établissement (ou à la famille concernée).
- Supporte l'en-tête `X-Accel-Redirect` en production derrière Nginx si
  `USE_X_ACCEL_REDIRECT=True`.
"""
import mimetypes
import os
from pathlib import Path
from django.conf import settings
from django.http import FileResponse, Http404, HttpResponse, HttpResponseForbidden
from django.utils._os import safe_join

PUBLIC_MEDIA_PREFIXES = (
    "etablissements/logos/",
    "divisions/logos/",
    "plateforme/",
)


def _normalize_rel_path(raw_path: str) -> str:
    return (raw_path or "").replace("\\", "/").lstrip("/")


def _is_authorized_for_media(request, rel_path: str) -> bool:
    if any(rel_path.startswith(p) for p in PUBLIC_MEDIA_PREFIXES):
        return True

    user = getattr(request, "user", None)
    if not user or not user.is_authenticated:
        return False
    if getattr(user, "role", None) == "super_admin":
        return True

    etab = getattr(request, "etablissement", None)
    etab_id = getattr(etab, "pk", None) or getattr(user, "etablissement_id", None)

    if rel_path.startswith("eleves/"):
        from eleves.models import Eleve
        eleve = Eleve.objects.filter(photo=rel_path).only("id", "etablissement_id").first()
        if not eleve:
            return False
        if user.role in ("parent", "eleve"):
            from core.views_espace_famille import get_eleves_accessibles
            return get_eleves_accessibles(user).filter(pk=eleve.pk).exists()
        return etab_id is not None and eleve.etablissement_id == etab_id

    if rel_path.startswith("users/"):
        from accounts.models import User
        owner = User.objects.filter(photo=rel_path).only("id", "etablissement_id").first()
        if not owner:
            return False
        if owner.pk == user.pk:
            return True
        return etab_id is not None and owner.etablissement_id == etab_id

    return etab_id is not None


def protected_media_serve(request, path: str):
    rel_path = _normalize_rel_path(path)
    if not rel_path:
        raise Http404("Fichier introuvable.")

    try:
        full_path = Path(safe_join(str(settings.MEDIA_ROOT), rel_path))
    except Exception:
        raise Http404("Chemin invalide.")

    if not _is_authorized_for_media(request, rel_path):
        return HttpResponseForbidden("Accès refusé à cette ressource média.")

    if not full_path.is_file():
        raise Http404("Fichier média introuvable.")

    is_public = any(rel_path.startswith(p) for p in PUBLIC_MEDIA_PREFIXES)

    if os.environ.get("USE_X_ACCEL_REDIRECT", "False") == "True":
        content_type, _ = mimetypes.guess_type(str(full_path))
        resp = HttpResponse(content_type=content_type or "application/octet-stream")
        resp["X-Accel-Redirect"] = f"/protected-media/{rel_path}"
    else:
        content_type, _ = mimetypes.guess_type(str(full_path))
        resp = FileResponse(open(full_path, "rb"), content_type=content_type or "application/octet-stream")

    resp["X-Content-Type-Options"] = "nosniff"
    resp["Cache-Control"] = "public, max-age=86400" if is_public else "private, no-store"
    return resp
