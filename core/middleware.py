from etablissements.models import Etablissement
from django.shortcuts import redirect
from django.urls import reverse


class EtablissementMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        request.etablissement = None

        if request.user.is_authenticated:
            # URLs exclues du blocage établissement
            URLS_LIBRES = [
                reverse('login'), reverse('logout'),
                '/admin/', '/static/', '/media/',
                '/etablissements/gerer/',
            ]
            path = request.path

            if hasattr(request.user, 'etablissement') and request.user.etablissement:
                etab = request.user.etablissement

                # ── CHANTIER 3 : Blocage établissement inactif ──────────────
                if not etab.is_active and request.user.role != 'super_admin':
                    libre = any(path.startswith(u) for u in URLS_LIBRES)
                    if not libre and path != '/acces-bloque/':
                        return redirect('acces_bloque')

                request.etablissement = etab

            elif request.user.role == 'super_admin':
                # Super admin : session d'abord
                etab_id = request.session.get('etablissement_id')
                if etab_id:
                    try:
                        request.etablissement = Etablissement.objects.get(pk=etab_id)
                    except Etablissement.DoesNotExist:
                        pass
                if not request.etablissement:
                    premier = Etablissement.objects.filter(is_active=True).first()
                    if premier:
                        request.etablissement = premier
                        request.session['etablissement_id'] = premier.pk

        return self.get_response(request)
