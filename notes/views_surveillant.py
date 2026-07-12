from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import Count, Q
from django.utils import timezone
from .models import Matiere, Periode, NotePeriode
from eleves.models import Eleve, Presence, Inscription
from etablissements.models import Classe, AnneeScolaire
from decimal import Decimal
import datetime
from core.cycle_filter import get_cycles_actifs_ids, get_classes_actives, get_eleves_actifs, get_inscriptions_actives


def require_etab(fn):
    def wrapper(request, *args, **kwargs):
        if not request.etablissement:
            return redirect('dashboard')
        return fn(request, *args, **kwargs)
    wrapper.__name__ = fn.__name__
    return wrapper


def require_surveillant(fn):
    def wrapper(request, *args, **kwargs):
        if not (request.user.is_surveillant or request.user.is_admin):
            messages.error(request, "Acces reserve au surveillant general.")
            return redirect('dashboard')
        return fn(request, *args, **kwargs)
    wrapper.__name__ = fn.__name__
    return wrapper


@login_required
@require_etab
@require_surveillant
def saisie_conduite(request):
    """Saisie de la note de conduite par le surveillant général."""
    etab = request.etablissement
    annee = AnneeScolaire.objects.filter(etablissement=etab, is_active=True).first()
    classes = get_classes_actives(etab, annee) if annee else []
    periodes = Periode.objects.filter(etablissement=etab, annee=annee) if annee else []
    matiere_conduite = Matiere.objects.filter(etablissement=etab, is_conduite=True).first()

    classe_id  = request.GET.get('classe')
    periode_id = request.GET.get('periode')
    classe  = get_object_or_404(Classe,  pk=classe_id,  etablissement=etab) if classe_id  else None
    periode = get_object_or_404(Periode, pk=periode_id, etablissement=etab) if periode_id else None

    eleves_data = []
    if classe and periode and matiere_conduite:
        inscriptions = classe.inscriptions.filter(is_active=True).select_related('eleve').order_by('eleve__nom')
        for insc in inscriptions:
            note = NotePeriode.objects.filter(
                eleve=insc.eleve, matiere=matiere_conduite, periode=periode, classe=classe
            ).first()
            # Compter les absences pour aide à la saisie
            nb_absences = Presence.objects.filter(
                eleve=insc.eleve, classe=classe, statut='absent'
            ).count()
            nb_retards = Presence.objects.filter(
                eleve=insc.eleve, classe=classe, statut='retard'
            ).count()
            eleves_data.append({
                'eleve': insc.eleve,
                'note': note,
                'nb_absences': nb_absences,
                'nb_retards': nb_retards,
                'conduite_suggeree': _suggerer_conduite(nb_absences, nb_retards),
            })

    if request.method == 'POST' and classe and periode and matiere_conduite:
        saved = 0
        for insc in classe.inscriptions.filter(is_active=True).select_related('eleve'):
            nc = request.POST.get(f'nc_{insc.eleve.pk}', '').strip()
            if nc:
                try:
                    valeur = Decimal(nc.replace(',','.'))
                    if 0 <= valeur <= 20:
                        note, created = NotePeriode.objects.update_or_create(
                            eleve=insc.eleve, matiere=matiere_conduite,
                            classe=classe, periode=periode,
                            defaults={
                                'note_conduite': valeur,
                                'saisi_par': request.user,
                            }
                        )
                        # Appliquer modifie_par seulement si c'est une mise à jour (pas une création)
                        if not created:
                            note.modifie_par = request.user
                            note.save(update_fields=['modifie_par'])
                        from .views_notes import enregistrer_log
                        enregistrer_log(note, request.user, 'note_conduite', None, valeur)
                        saved += 1
                except Exception:
                    pass
        messages.success(request, f"{saved} note(s) de conduite enregistree(s). Le directeur a ete notifie.")
        return redirect(f"{request.path}?classe={classe_id}&periode={periode_id}")

    return render(request, 'notes/saisie_conduite.html', {
        'classes': classes, 'periodes': periodes,
        'classe': classe, 'periode': periode,
        'eleves_data': eleves_data,
        'matiere_conduite': matiere_conduite,
        'classe_id': classe_id, 'periode_id': periode_id,
    })


def _suggerer_conduite(nb_absences, nb_retards):
    """Suggère une note de conduite selon les absences."""
    score = 20 - (nb_absences * 1.5) - (nb_retards * 0.5)
    return max(0, round(score, 1))


@login_required
@require_etab
@require_surveillant
def rapport_absences(request):
    """Rapport des absences pour le surveillant général."""
    etab = request.etablissement
    annee = AnneeScolaire.objects.filter(etablissement=etab, is_active=True).first()
    classes = get_classes_actives(etab, annee) if annee else []
    today = timezone.now().date()

    classe_id = request.GET.get('classe')
    mois = request.GET.get('mois', today.strftime('%Y-%m'))
    vue = request.GET.get('vue', 'jour')  # jour, mois, eleve

    classe = get_object_or_404(Classe, pk=classe_id, etablissement=etab) if classe_id else None

    # Absences du jour (toutes classes)
    absences_jour = Presence.objects.filter(
        classe__etablissement=etab,
        date=today,
        statut__in=['absent','retard']
    ).select_related('eleve','classe').order_by('classe__nom','eleve__nom')

    # Statistiques par élève (mois sélectionné)
    stats_eleves = []
    if classe:
        try:
            annee_str, mois_num = mois.split('-')
            inscriptions = classe.inscriptions.filter(is_active=True).select_related('eleve')
            for insc in inscriptions:
                presences = Presence.objects.filter(
                    eleve=insc.eleve, classe=classe,
                    date__year=annee_str, date__month=mois_num
                )
                total = presences.count()
                absents = presences.filter(statut='absent').count()
                retards = presences.filter(statut='retard').count()
                justifies = presences.filter(statut='justifie').count()
                stats_eleves.append({
                    'eleve': insc.eleve,
                    'total': total,
                    'absents': absents,
                    'retards': retards,
                    'justifies': justifies,
                    'non_justifies': max(0, absents - justifies),
                    'alerte': absents >= 3,
                })
            stats_eleves.sort(key=lambda x: x['absents'], reverse=True)
        except ValueError:
            pass

    # Élèves avec 3+ absences ce mois (toutes classes)
    alertes = []
    try:
        annee_str, mois_num = mois.split('-')
        for eleve in get_eleves_actifs(etab):
            nb = Presence.objects.filter(
                eleve=eleve, statut='absent',
                date__year=annee_str, date__month=mois_num
            ).count()
            if nb >= 3:
                alertes.append({'eleve': eleve, 'nb_absences': nb, 'inscription': eleve.get_inscription_active()})
        alertes.sort(key=lambda x: x['nb_absences'], reverse=True)
    except ValueError:
        pass

    return render(request, 'notes/rapport_absences.html', {
        'classes': classes, 'classe': classe, 'classe_id': classe_id,
        'absences_jour': absences_jour,
        'stats_eleves': stats_eleves,
        'alertes': alertes,
        'mois': mois, 'today': today, 'vue': vue,
    })
