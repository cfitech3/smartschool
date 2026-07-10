from etablissements.models import Etablissement


class EtablissementMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        request.etablissement = None
        if request.user.is_authenticated:
            if hasattr(request.user, 'etablissement') and request.user.etablissement:
                # Cas normal : utilisateur rattaché à un établissement
                request.etablissement = request.user.etablissement

            elif request.user.role == 'super_admin':
                # Super admin : chercher l'établissement en session d'abord
                etab_id = request.session.get('etablissement_id')
                if etab_id:
                    try:
                        request.etablissement = Etablissement.objects.get(pk=etab_id)
                    except Etablissement.DoesNotExist:
                        pass
                # Si pas en session → prendre le premier établissement disponible
                if not request.etablissement:
                    premier = Etablissement.objects.filter(is_active=True).first()
                    if premier:
                        request.etablissement = premier
                        request.session['etablissement_id'] = premier.pk

        return self.get_response(request)
