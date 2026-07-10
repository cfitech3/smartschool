from etablissements.models import AnneeScolaire
from notes.models import LogModificationNote

def global_context(request):
    context = {'app_name': 'SmartSchool ERP'}
    if request.user.is_authenticated:
        context['current_etablissement'] = getattr(request, 'etablissement', None)
        if request.etablissement:
            context['annee_active'] = AnneeScolaire.objects.filter(
                etablissement=request.etablissement, is_active=True
            ).first()
            if request.user.is_admin:
                context['notifs_non_lues'] = LogModificationNote.objects.filter(
                    note_periode__eleve__etablissement=request.etablissement,
                    notif_envoyee=True, notif_lue=False
                ).count()
                from notes.models import Reclamation, MessageFamille
                context['nb_reclamations_attente'] = Reclamation.objects.filter(
                    eleve__etablissement=request.etablissement, statut='en_attente'
                ).count()
                context['nb_messages_non_lus'] = MessageFamille.objects.filter(
                    etablissement=request.etablissement, statut='non_lu'
                ).count()
        if request.user.role == 'super_admin':
            from etablissements.models import Etablissement
            context['tous_etablissements'] = Etablissement.objects.filter(is_active=True)
    return context
