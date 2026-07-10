"""Vues dédiées au cycle université : saisie notes UE + relevé LMD."""
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from decimal import Decimal
from etablissements.models import Classe, AnneeScolaire, UEUniversite
from notes.models import NoteUE, Periode
from eleves.models import Eleve
from core.cycle_filter import get_cycles_actifs_ids, get_classes_actives, get_eleves_actifs, get_inscriptions_actives


def req(fn):
    def w(request, *a, **k):
        if not request.etablissement: return redirect("dashboard")
        return fn(request, *a, **k)
    w.__name__ = fn.__name__; return w


@login_required
@req
def saisie_notes_ue(request):
    etab    = request.etablissement
    annee   = AnneeScolaire.objects.filter(etablissement=etab, is_active=True).first()
    # Classes université uniquement
    classes = Classe.objects.filter(
        etablissement=etab, annee=annee,
        niveau__cycle__type_cycle='universite'
    ).select_related('niveau', 'niveau__cycle').order_by('niveau__ordre', 'nom')

    classe_id  = request.GET.get('classe')
    periode_id = request.GET.get('periode')
    semestre   = request.GET.get('semestre', '1')

    classe  = Classe.objects.filter(pk=classe_id, etablissement=etab).first() if classe_id else None
    periodes = Periode.objects.filter(etablissement=etab, annee=annee) if annee else []
    periode = Periode.objects.filter(pk=periode_id, etablissement=etab).first() if periode_id else None

    ues_data = []
    if classe and classe.niveau and classe.niveau.cycle:
        cycle_univ = classe.niveau.cycle
        ues = UEUniversite.objects.filter(
            cycle=cycle_univ, semestre=int(semestre)
        ).order_by('code')

        inscriptions = classe.inscriptions.filter(is_active=True).select_related('eleve')
        eleves_list  = [i.eleve for i in inscriptions]

        for ue in ues:
            notes_existantes = {}
            if periode:
                for n in NoteUE.objects.filter(ue=ue, classe=classe, periode=periode):
                    notes_existantes[n.eleve_id] = n
            ues_data.append({
                'ue': ue,
                'notes': {e.pk: notes_existantes.get(e.pk) for e in eleves_list}
            })

    if request.method == 'POST' and classe and periode:
        cycle_univ = classe.niveau.cycle
        ues = UEUniversite.objects.filter(cycle=cycle_univ, semestre=int(semestre))
        inscriptions = classe.inscriptions.filter(is_active=True).select_related('eleve')

        nb_saisies = 0
        for ue in ues:
            for insc in inscriptions:
                eleve = insc.eleve
                note_val = request.POST.get(f'note_{ue.pk}_{eleve.pk}')
                ratt_val = request.POST.get(f'ratt_{ue.pk}_{eleve.pk}')

                if note_val and note_val.strip():
                    try:
                        note_dec = Decimal(str(round(float(note_val), 2)))
                        ratt_dec = None
                        if ratt_val and ratt_val.strip():
                            ratt_dec = Decimal(str(round(float(ratt_val), 2)))

                        obj, created = NoteUE.objects.get_or_create(
                            eleve=eleve, ue=ue, classe=classe, periode=periode,
                            defaults={'note': note_dec, 'note_rattrapage': ratt_dec,
                                      'saisi_par': request.user}
                        )
                        if not created:
                            obj.note = note_dec
                            obj.note_rattrapage = ratt_dec
                            obj.saisi_par = request.user
                            obj.save()
                        nb_saisies += 1
                    except (ValueError, Exception):
                        pass

        messages.success(request, f"{nb_saisies} notes enregistrées.")
        return redirect(f"{request.path}?classe={classe_id}&periode={periode_id}&semestre={semestre}")

    semestres_cycle = []
    if classe and classe.niveau and classe.niveau.cycle:
        semestres_cycle = list(
            UEUniversite.objects.filter(cycle=classe.niveau.cycle)
            .values_list('semestre', flat=True).distinct().order_by('semestre')
        )

    return render(request, 'notes/saisie_notes_ue.html', {
        'classes': classes, 'classe': classe, 'periodes': periodes, 'periode': periode,
        'classe_id': classe_id, 'periode_id': periode_id,
        'semestre': semestre, 'semestres_cycle': semestres_cycle,
        'ues_data': ues_data,
        'eleves_list': [i.eleve for i in classe.inscriptions.filter(is_active=True).select_related('eleve')] if classe else [],
    })


@login_required
@req
def releve_notes_lmd(request, eleve_pk, periode_pk):
    """Relevé de notes LMD (bulletin université)."""
    from django.utils import timezone
    from etablissements.models import ModeleDocument
    etab    = request.etablissement
    eleve   = get_object_or_404(Eleve, pk=eleve_pk, etablissement=etab)
    periode = get_object_or_404(Periode, pk=periode_pk, etablissement=etab)
    annee   = periode.annee
    insc    = eleve.get_inscription_active()
    modele  = ModeleDocument.objects.filter(etablissement=etab, type_document='releve_notes', is_actif=True).first()

    # Notes UE pour cette période
    notes_ue = NoteUE.objects.filter(
        eleve=eleve, periode=periode
    ).select_related('ue').order_by('ue__semestre', 'ue__code')

    # Regrouper par semestre
    semestres = {}
    total_credits_obtenus = 0
    total_credits_requis  = 0
    total_points = 0

    for n in notes_ue:
        s = n.ue.semestre
        if s not in semestres:
            semestres[s] = {'ues': [], 'credits_obtenus': 0, 'credits_requis': 0, 'points': 0}
        semestres[s]['ues'].append(n)
        semestres[s]['credits_requis']  += n.ue.credits
        if n.credits_valides:
            semestres[s]['credits_obtenus'] += n.ue.credits
            total_credits_obtenus += n.ue.credits
        total_credits_requis += n.ue.credits
        if n.note_retenue:
            pts = float(n.note_retenue) * n.ue.coefficient
            semestres[s]['points'] += pts
            total_points += pts

    # Moyenne générale
    total_coef = sum(n.ue.coefficient for n in notes_ue)
    moy_generale = round(total_points / total_coef, 2) if total_coef > 0 else None

    # Mention générale
    mention = ''
    if moy_generale:
        if moy_generale >= 16: mention = 'Très Bien'
        elif moy_generale >= 14: mention = 'Bien'
        elif moy_generale >= 12: mention = 'Assez Bien'
        elif moy_generale >= 10: mention = 'Passable'
        else: mention = 'Insuffisant — Ajourné'

    return render(request, 'notes/releve_lmd.html', {
        'eleve': eleve, 'periode': periode, 'annee': annee,
        'etab': etab, 'modele': modele, 'inscription': insc,
        'notes_ue': notes_ue, 'semestres': semestres,
        'total_credits_obtenus': total_credits_obtenus,
        'total_credits_requis': total_credits_requis,
        'moy_generale': moy_generale, 'mention': mention,
        'today': timezone.now().date(),
    })
