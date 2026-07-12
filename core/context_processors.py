from django.core.cache import cache
from etablissements.models import AnneeScolaire
from notes.models import LogModificationNote

def global_context(request):
    context = {'app_name': 'SmartSchool ERP'}
    if request.user.is_authenticated:
        context['current_etablissement'] = getattr(request, 'etablissement', None)
        if request.etablissement:
            etab_id = request.etablissement.pk
            
            # P2.6 Cache de l'année active
            cache_key_annee = f"annee_active_{etab_id}"
            annee = cache.get(cache_key_annee)
            if annee is None:
                annee = AnneeScolaire.objects.filter(etablissement_id=etab_id, is_active=True).first()
                cache.set(cache_key_annee, annee, 3600)  # 1 heure
            context['annee_active'] = annee

            if request.user.is_admin:
                # Cache des compteurs de notifications (5 minutes)
                cache_key_notifs = f"admin_notifs_{etab_id}"
                notifs = cache.get(cache_key_notifs)
                if notifs is None:
                    from notes.models import Reclamation, MessageFamille
                    notifs = {
                        'notifs_non_lues': LogModificationNote.objects.filter(
                            note_periode__eleve__etablissement_id=etab_id,
                            notif_envoyee=True, notif_lue=False
                        ).count(),
                        'nb_reclamations_attente': Reclamation.objects.filter(
                            eleve__etablissement_id=etab_id, statut='en_attente'
                        ).count(),
                        'nb_messages_non_lus': MessageFamille.objects.filter(
                            etablissement_id=etab_id, statut='non_lu'
                        ).count()
                    }
                    cache.set(cache_key_notifs, notifs, 300)
                
                context.update(notifs)

        if request.user.role == 'super_admin':
            cache_key_etabs = "tous_etablissements_actifs"
            etabs = cache.get(cache_key_etabs)
            if etabs is None:
                from etablissements.models import Etablissement
                etabs = list(Etablissement.objects.filter(is_active=True))
                cache.set(cache_key_etabs, etabs, 3600)
            context['tous_etablissements'] = etabs

    return context
