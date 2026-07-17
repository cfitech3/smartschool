"""
Moteur d'alertes pour les administrateurs d'établissement.
Utilisé par : directeur, secrétariat, comptable, surveillant.
"""
from django.utils import timezone
from django.db.models import Count, Sum, Q
import datetime


def get_alertes_etablissement(etab, annee, user_role):
    """
    Retourne une liste d'alertes contextuelles selon le rôle.
    Chaque alerte : {type, niveau, titre, detail, url, count}
    niveaux : 'danger' | 'warning' | 'info'
    """
    today = timezone.now().date()
    alertes = []

    from eleves.models import Presence, Inscription, Eleve
    from finances.models import Paiement, TypeFrais
    from notes.models import Periode, NotePeriode, EmploiDuTemps, Reclamation, MessageFamille
    from core.cycle_filter import get_cycles_actifs_ids, get_eleves_actifs, get_classes_actives
    from etablissements.models import Classe

    cycles_ids = get_cycles_actifs_ids(etab)

    # ── ALERTES COMMUNES : directeur + secrétariat ────────────────────────────
    if user_role in ('admin', 'secretariat', 'super_admin'):

        # Élèves absents 3+ jours consécutifs
        eleves_absences = {}
        presences_recentes = Presence.objects.filter(
            classe__etablissement=etab,
            classe__niveau__cycle__in=cycles_ids,
            date__gte=today - datetime.timedelta(days=7),
            statut='absent'
        ).values('eleve_id', 'date').order_by('eleve_id', '-date')

        from collections import defaultdict
        absences_par_eleve = defaultdict(list)
        for p in presences_recentes:
            absences_par_eleve[p['eleve_id']].append(p['date'])

        eleves_3plus = []
        for eleve_id, dates in absences_par_eleve.items():
            dates_sorted = sorted(set(dates), reverse=True)
            consecutifs = 0
            for i, d in enumerate(dates_sorted):
                if i == 0:
                    consecutifs = 1
                elif (dates_sorted[i-1] - d).days == 1:
                    consecutifs += 1
                else:
                    break
            if consecutifs >= 3:
                eleves_3plus.append(eleve_id)

        if eleves_3plus:
            alertes.append({
                'type': 'absences_consecutives',
                'niveau': 'danger',
                'titre': f'{len(eleves_3plus)} élève(s) absent(s) 3+ jours consécutifs',
                'detail': 'Ces élèves nécessitent un suivi immédiat',
                'url': '/eleves/presences/',
                'count': len(eleves_3plus),
                'icone': '🚨',
            })

        # Réclamations en attente
        nb_reclam = Reclamation.objects.filter(
            eleve__etablissement=etab, statut='en_attente'
        ).count()
        if nb_reclam > 0:
            alertes.append({
                'type': 'reclamations',
                'niveau': 'warning',
                'titre': f'{nb_reclam} réclamation(s) en attente',
                'detail': 'Des parents attendent une réponse',
                'url': '/reclamations/',
                'count': nb_reclam,
                'icone': '📋',
            })

        # Messages non lus
        nb_msg = MessageFamille.objects.filter(
            expediteur__etablissement=etab, statut='non_lu'
        ).count()
        if nb_msg > 0:
            alertes.append({
                'type': 'messages',
                'niveau': 'info',
                'titre': f'{nb_msg} message(s) non lu(s) des familles',
                'detail': 'Messages reçus de parents ou élèves',
                'url': '/messages/',
                'count': nb_msg,
                'icone': '💬',
            })

        # Classes sans appel aujourd'hui (après 8h)
        heure = timezone.now().hour
        if heure >= 8:
            toutes = Classe.objects.filter(etablissement=etab)
            if annee:
                toutes = toutes.filter(annee=annee)
            avec_appel = Presence.objects.filter(
                classe__etablissement=etab, date=today
            ).values_list('classe_id', flat=True).distinct()
            sans_appel = toutes.exclude(pk__in=avec_appel).count()
            if sans_appel > 0:
                alertes.append({
                    'type': 'appel_manquant',
                    'niveau': 'warning',
                    'titre': f'{sans_appel} classe(s) sans appel aujourd\'hui',
                    'detail': f'Appel non marqué au {today.strftime("%d/%m/%Y")}',
                    'url': '/eleves/presences/',
                    'count': sans_appel,
                    'icone': '📝',
                })

    # ── ALERTES FINANCES : directeur + comptable ──────────────────────────────
    if user_role in ('admin', 'comptable', 'super_admin'):

        # Élèves en retard de paiement ce mois
        eleves_ids = get_eleves_actifs(etab).values_list('pk', flat=True)
        payes_ids = Paiement.objects.filter(
            etablissement=etab, statut='valide',
            date_paiement__month=today.month,
            date_paiement__year=today.year,
        ).values_list('eleve_id', flat=True).distinct()
        nb_retard = len(set(eleves_ids) - set(payes_ids))
        if nb_retard > 0:
            alertes.append({
                'type': 'retard_paiement',
                'niveau': 'danger' if nb_retard > 20 else 'warning',
                'titre': f'{nb_retard} élève(s) sans paiement ce mois',
                'detail': 'Frais de scolarité non réglés pour ce mois',
                'url': '/finances/rapport/',
                'count': nb_retard,
                'icone': '💳',
            })

        # Paiements en attente de validation
        nb_attente = Paiement.objects.filter(
            etablissement=etab, statut='en_attente'
        ).count()
        if nb_attente > 0:
            alertes.append({
                'type': 'paiements_attente',
                'niveau': 'warning',
                'titre': f'{nb_attente} paiement(s) en attente de validation',
                'detail': 'Paiements reçus mais non encore validés',
                'url': '/finances/',
                'count': nb_attente,
                'icone': '⏳',
            })

    # ── ALERTES NOTES : directeur + enseignants ───────────────────────────────
    if user_role in ('admin', 'enseignant', 'super_admin'):

        periode_active = Periode.objects.filter(
            etablissement=etab, is_active=True
        ).first()

        if periode_active and periode_active.date_fin:
            jours_restants = (periode_active.date_fin - today).days
            if 0 < jours_restants <= 7:
                # Compter les enseignants qui n'ont pas saisi leurs notes
                enseignants = EmploiDuTemps.objects.filter(
                    classe__etablissement=etab
                ).values_list('enseignant_id', flat=True).distinct()
                notes_saisies = NotePeriode.objects.filter(
                    periode=periode_active
                ).values_list('saisi_par_id', flat=True).distinct()
                en_retard = len(set(enseignants) - set(notes_saisies))
                if en_retard > 0:
                    alertes.append({
                        'type': 'notes_manquantes',
                        'niveau': 'danger' if jours_restants <= 3 else 'warning',
                        'titre': f'Clôture période dans {jours_restants} jour(s)',
                        'detail': f'{en_retard} enseignant(s) n\'ont pas encore saisi leurs notes',
                        'url': '/notes/logs/',
                        'count': en_retard,
                        'icone': '📚',
                    })

    # ── ALERTES SURVEILLANT ───────────────────────────────────────────────────
    if user_role in ('surveillant', 'admin', 'super_admin'):

        # Élèves avec 5+ absences ce mois
        debut_mois = today.replace(day=1)
        frequents = Presence.objects.filter(
            classe__etablissement=etab,
            classe__niveau__cycle__in=cycles_ids,
            date__gte=debut_mois,
            statut='absent'
        ).values('eleve_id').annotate(nb=Count('id')).filter(nb__gte=5)
        if frequents.count() > 0:
            alertes.append({
                'type': 'absenteisme',
                'niveau': 'warning',
                'titre': f'{frequents.count()} élève(s) avec 5+ absences ce mois',
                'detail': 'Absentéisme fréquent à surveiller',
                'url': '/notes/absences/',
                'count': frequents.count(),
                'icone': '📊',
            })

    # Trier : danger en premier, puis warning, puis info
    ordre = {'danger': 0, 'warning': 1, 'info': 2}
    alertes.sort(key=lambda a: ordre.get(a['niveau'], 3))

    return alertes
