from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import HttpResponse
from django.db.models import Avg, Count, Q
from django.utils import timezone
from .models import NotePeriode, Matiere, Periode
from etablissements.models import Classe, AnneeScolaire
from eleves.models import Eleve, Inscription
from decimal import Decimal
from core.cycle_filter import get_cycles_actifs_ids, get_classes_actives, get_eleves_actifs, get_inscriptions_actives


def require_etab(fn):
    def wrapper(request, *args, **kwargs):
        if not request.etablissement:
            return redirect('dashboard')
        return fn(request, *args, **kwargs)
    wrapper.__name__ = fn.__name__
    return wrapper


def calculer_moyenne_eleve(eleve, periode, matieres):
    """Calcule la moyenne pondérée d'un élève pour une période."""
    total_points = Decimal('0')
    total_coef = 0
    resultats = []
    for matiere in matieres:
        notes = Note.objects.filter(eleve=eleve, matiere=matiere, periode=periode)
        if notes.exists():
            moy_matiere = sum(n.valeur_sur_20 for n in notes) / notes.count()
            total_points += Decimal(str(moy_matiere)) * matiere.coefficient
            total_coef += matiere.coefficient
            resultats.append({
                'matiere': matiere,
                'notes': list(notes),
                'moyenne': round(moy_matiere, 2),
            })
        else:
            resultats.append({'matiere': matiere, 'notes': [], 'moyenne': None})
    moyenne_gen = round(total_points / total_coef, 2) if total_coef else None
    return moyenne_gen, resultats


@login_required
@require_etab
def saisie_notes(request):
    etab = request.etablissement
    annee = AnneeScolaire.objects.filter(etablissement=etab, is_active=True).first()
    classes = get_classes_actives(etab, annee) if annee else []
    periodes = Periode.objects.filter(etablissement=etab, annee=annee) if annee else []
    matieres = Matiere.objects.filter(etablissement=etab)

    classe_id = request.GET.get('classe')
    periode_id = request.GET.get('periode')
    matiere_id = request.GET.get('matiere')

    classe = get_object_or_404(Classe, pk=classe_id, etablissement=etab) if classe_id else None
    periode = get_object_or_404(Periode, pk=periode_id, etablissement=etab) if periode_id else None
    matiere = get_object_or_404(Matiere, pk=matiere_id, etablissement=etab) if matiere_id else None

    eleves_data = []
    if classe and periode and matiere:
        inscriptions = classe.inscriptions.filter(is_active=True).select_related('eleve').order_by('eleve__nom')
        for insc in inscriptions:
            notes_eleve = Note.objects.filter(
                eleve=insc.eleve, matiere=matiere, periode=periode, classe=classe
            ).order_by('date_saisie')
            eleves_data.append({'eleve': insc.eleve, 'notes': notes_eleve})

    if request.method == 'POST' and classe and periode and matiere:
        type_note = request.POST.get('type_note', 'devoir')
        note_max = Decimal(request.POST.get('note_max', '20'))
        saved = 0
        for key, val in request.POST.items():
            if key.startswith('note_') and val.strip():
                eleve_id = key.split('_')[1]
                try:
                    valeur = Decimal(val.replace(',', '.'))
                    if 0 <= valeur <= note_max:
                        eleve = get_object_or_404(Eleve, pk=eleve_id, etablissement=etab)
                        Note.objects.create(
                            eleve=eleve, matiere=matiere, classe=classe,
                            periode=periode, type_note=type_note,
                            valeur=valeur, note_max=note_max,
                            saisi_par=request.user
                        )
                        saved += 1
                except Exception:
                    pass
        messages.success(request, f"{saved} note(s) enregistree(s) pour {matiere.nom} — {classe.nom}")
        return redirect(f"{request.path}?classe={classe_id}&periode={periode_id}&matiere={matiere_id}")

    return render(request, 'notes/saisie_notes.html', {
        'classes': classes, 'periodes': periodes, 'matieres': matieres,
        'classe': classe, 'periode': periode, 'matiere': matiere,
        'eleves_data': eleves_data,
        'types_note': Note.TYPES,
        'classe_id': classe_id, 'periode_id': periode_id, 'matiere_id': matiere_id,
    })


@login_required
@require_etab
def releve_notes_classe(request):
    etab = request.etablissement
    annee = AnneeScolaire.objects.filter(etablissement=etab, is_active=True).first()
    classes = get_classes_actives(etab, annee) if annee else []
    periodes = Periode.objects.filter(etablissement=etab, annee=annee) if annee else []

    classe_id = request.GET.get('classe')
    periode_id = request.GET.get('periode')
    classe = get_object_or_404(Classe, pk=classe_id, etablissement=etab) if classe_id else None
    periode = get_object_or_404(Periode, pk=periode_id, etablissement=etab) if periode_id else None

    tableau = []
    matieres = []
    if classe and periode:
        matieres = Matiere.objects.filter(etablissement=etab)
        inscriptions = classe.inscriptions.filter(is_active=True).select_related('eleve').order_by('eleve__nom')
        resultats = []
        for insc in inscriptions:
            moy, detail = calculer_moyenne_eleve(insc.eleve, periode, matieres)
            resultats.append({'eleve': insc.eleve, 'moyenne': moy, 'detail': detail})

        # Classement
        resultats_avec_moy = [r for r in resultats if r['moyenne'] is not None]
        resultats_avec_moy.sort(key=lambda x: x['moyenne'], reverse=True)
        for i, r in enumerate(resultats_avec_moy):
            r['rang'] = i + 1
        tableau = resultats

    return render(request, 'notes/releve_classe.html', {
        'classes': classes, 'periodes': periodes,
        'classe': classe, 'periode': periode,
        'tableau': tableau, 'matieres': matieres,
        'classe_id': classe_id, 'periode_id': periode_id,
    })


@login_required
@require_etab
def generer_bulletins(request):
    etab = request.etablissement
    annee = AnneeScolaire.objects.filter(etablissement=etab, is_active=True).first()
    classes = get_classes_actives(etab, annee) if annee else []
    periodes = Periode.objects.filter(etablissement=etab, annee=annee) if annee else []

    classe_id = request.GET.get('classe')
    periode_id = request.GET.get('periode')
    classe = get_object_or_404(Classe, pk=classe_id, etablissement=etab) if classe_id else None
    periode = get_object_or_404(Periode, pk=periode_id, etablissement=etab) if periode_id else None

    bulletins = []
    if classe and periode:
        matieres = Matiere.objects.filter(etablissement=etab)
        inscriptions = classe.inscriptions.filter(is_active=True).select_related('eleve')
        resultats = []
        for insc in inscriptions:
            moy, detail = calculer_moyenne_eleve(insc.eleve, periode, matieres)
            resultats.append({'eleve': insc.eleve, 'moyenne': moy, 'detail': detail})

        # Classement
        resultats_avec_moy = [r for r in resultats if r['moyenne'] is not None]
        resultats_avec_moy.sort(key=lambda x: x['moyenne'], reverse=True)

        for i, r in enumerate(resultats_avec_moy):
            bul, _ = Bulletin.objects.update_or_create(
                eleve=r['eleve'], periode=periode,
                defaults={
                    'classe': classe, 'annee': annee,
                    'moyenne_generale': r['moyenne'],
                    'rang': i + 1,
                    'effectif_classe': len(resultats),
                    'is_valide': True,
                }
            )
            bulletins.append({'bulletin': bul, 'detail': r['detail'], 'rang': i + 1})

        if request.method == 'POST':
            messages.success(request, f"{len(bulletins)} bulletin(s) genere(s) pour {classe.nom} — {periode.libelle}")
            return redirect(f"{request.path}?classe={classe_id}&periode={periode_id}")

    return render(request, 'notes/bulletins.html', {
        'classes': classes, 'periodes': periodes,
        'classe': classe, 'periode': periode,
        'bulletins': bulletins,
        'classe_id': classe_id, 'periode_id': periode_id,
    })


@login_required
@require_etab
def bulletin_eleve(request, eleve_pk, periode_pk):
    etab = request.etablissement
    eleve = get_object_or_404(Eleve, pk=eleve_pk, etablissement=etab)
    periode = get_object_or_404(Periode, pk=periode_pk, etablissement=etab)
    matieres = Matiere.objects.filter(etablissement=etab)
    moyenne, detail = calculer_moyenne_eleve(eleve, periode, matieres)
    bulletin = Bulletin.objects.filter(eleve=eleve, periode=periode).first()
    inscription = eleve.get_inscription_active()

    return render(request, 'notes/bulletin_detail.html', {
        'eleve': eleve, 'periode': periode,
        'detail': detail, 'moyenne': moyenne,
        'bulletin': bulletin,
        'inscription': inscription,
        'etablissement': etab,
    })
