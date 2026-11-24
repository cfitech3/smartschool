"""
Garde-fou d'isolation Multi-Tenant « By Construction » — SmartSchool ERP.

Principe :
  - `EtablissementMiddleware` positionne l'identifiant du tenant actif et le
    drapeau d'application stricte dans des `ContextVar` isolées par requête.
  - Les modèles sensibles héritant de `TenantSafeMixin` refusent toute écriture
    (`.save()`) ou suppression (`.delete()`) sur un enregistrement appartenant
    à un autre établissement que celui de la requête courante (sauf `super_admin`
    ou bloc explicite `with tenant_bypass():`).
"""
from contextlib import contextmanager
from contextvars import ContextVar
from django.core.exceptions import PermissionDenied

_current_tenant_id: ContextVar[int | None] = ContextVar("smartschool_tenant_id", default=None)
_enforce_guard: ContextVar[bool] = ContextVar("smartschool_enforce_tenant_guard", default=False)


class TenantIsolationError(PermissionDenied):
    """Levée lorsqu'une opération tente de muter les données d'un autre établissement."""


def set_tenant_context(etablissement_id: int | None, enforce: bool = False):
    t1 = _current_tenant_id.set(etablissement_id)
    t2 = _enforce_guard.set(enforce)
    return t1, t2


def reset_tenant_context(tokens):
    t1, t2 = tokens
    _current_tenant_id.reset(t1)
    _enforce_guard.reset(t2)


def get_current_tenant_id() -> int | None:
    return _current_tenant_id.get()


@contextmanager
def tenant_bypass():
    """Désactive temporairement le garde-fou pour une opération système contrôlée."""
    tok = _enforce_guard.set(False)
    try:
        yield
    finally:
        _enforce_guard.reset(tok)


class TenantSafeMixin:
    """
    Mixin pour modèles portant un champ `etablissement` (FK).
    Bloque toute écriture/suppression inter-établissements lors d'une requête HTTP
    d'un utilisateur non-SuperAdmin.
    """
    tenant_field_name = "etablissement_id"

    def _check_tenant_isolation(self):
        if not _enforce_guard.get():
            return
        active_tid = _current_tenant_id.get()
        obj_tid = getattr(self, self.tenant_field_name, None)
        if active_tid is not None and obj_tid is not None and int(obj_tid) != int(active_tid):
            raise TenantIsolationError(
                f"Violation d'isolation multi-tenant sur {self.__class__.__name__} "
                f"(objet etab={obj_tid}, contexte actif={active_tid})."
            )

    def save(self, *args, **kwargs):
        self._check_tenant_isolation()
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        self._check_tenant_isolation()
        return super().delete(*args, **kwargs)
