from django.contrib.auth.signals import user_logged_in, user_login_failed
from django.dispatch import receiver


def _get_ip(request):
    if not request: return None
    xff = request.META.get('HTTP_X_FORWARDED_FOR', '')
    return xff.split(',')[0].strip() or request.META.get('REMOTE_ADDR')


def _get_ua(request):
    if not request: return ''
    return request.META.get('HTTP_USER_AGENT', '')[:300]


@receiver(user_logged_in)
def log_connexion_succes(sender, request, user, **kwargs):
    try:
        from accounts.models import JournalConnexion
        JournalConnexion.objects.create(
            user=user, username=user.username, statut='succes',
            ip=_get_ip(request), user_agent=_get_ua(request),
            etablissement=getattr(user, 'etablissement', None),
        )
    except Exception:
        pass


@receiver(user_login_failed)
def log_connexion_echec(sender, credentials, request, **kwargs):
    try:
        from accounts.models import JournalConnexion, User
        username = credentials.get('username', '')
        user = User.objects.filter(username=username).first()
        statut = 'bloque' if user and not user.is_active else 'echec'
        JournalConnexion.objects.create(
            user=user, username=username, statut=statut,
            ip=_get_ip(request), user_agent=_get_ua(request),
            etablissement=getattr(user, 'etablissement', None) if user else None,
        )
    except Exception:
        pass
