from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import Q
from .models import Matiere, Periode, NotePeriode, Bulletin
from etablissements.models import Classe, AnneeScolaire, ModeleDocument
from eleves.models import Eleve, Inscription
from decimal import Decimal, ROUND_HALF_UP
from core.cycle_filter import get_cycles_actifs_ids, get_classes_actives, get_eleves_actifs, get_inscriptions_actives


def require_etab(fn):
    def wrapper(request, *args, **kwargs):
        if not request.etablissement:
            return redirect('dashboard')
        return fn(request, *args, **kwargs)
    wrapper.__name__ = fn.__name__
    return wrapper


def calculer_bulletin_mali(eleve, periode, matieres):
    """
    Calcule le bulletin selon le format malien :
    - moy_classe (m) sur 20
    - moy_compo (n) sur 40
    - moyenne_finale = (m + n/2) / 2 ... ou plus précisément (m + n_ramene_20) / 2
    - moy_coeffic = moyenne_finale × coefficient
    - total_coeffic = somme des moy_coeffic
    - total_coef = somme des coefficients
    - moyenne_generale = total_coeffic / total_coef
    """
    lignes = []
    total_coeffic = Decimal('0')
    total_coef = 0

    for matiere in matieres:
        note = NotePeriode.objects.filter(
            eleve=eleve, matiere=matiere, periode=periode
        ).first()

        if note:
            moy_c = float(note.moy_classe) if note.moy_classe is not None else None
            moy_n = float(note.moy_compo) if note.moy_compo is not None else None
            moy_finale = note.moyenne_finale
            moy_coeff = note.moy_coeffic
            appre = note.appreciation
            note_max_c = float(note.note_max_classe)
            note_max_n = float(note.note_max_compo)
        else:
            moy_c = None
            moy_n = None
            moy_finale = None
            moy_coeff = None
            appre = ''
            note_max_c = 20
            note_max_n = 40

        if moy_coeff is not None:
            total_coeffic += Decimal(str(moy_coeff))
            total_coef += matiere.coefficient

        lignes.append({
            'matiere': matiere,
            'moy_classe': moy_c,
            'moy_compo': moy_n,
            'note_max_classe': note_max_c,
            'note_max_compo': note_max_n,
            'moyenne_finale': moy_finale,
            'moy_coeffic': moy_coeff,
            'appreciation': appre,
        })

    moy_generale = round(float(total_coeffic) / total_coef, 2) if total_coef > 0 else None
    return lignes, moy_generale, float(total_coeffic), total_coef


@login_required
@require_etab
def saisie_notes_mali(request):
    """Saisie avec les deux colonnes : moy_classe + moy_compo"""
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
            note = NotePeriode.objects.filter(
                eleve=insc.eleve, matiere=matiere, periode=periode, classe=classe
            ).first()
            eleves_data.append({
                'eleve': insc.eleve,
                'note': note,
            })

    if request.method == 'POST' and classe and periode and matiere:
        note_max_c = Decimal(request.POST.get('note_max_classe', '20'))
        note_max_n = Decimal(request.POST.get('note_max_compo', '40'))
        saved = 0

        inscriptions = classe.inscriptions.filter(is_active=True).select_related('eleve')
        for insc in inscriptions:
            mc = request.POST.get(f'mc_{insc.eleve.pk}', '').strip()
            mn = request.POST.get(f'mn_{insc.eleve.pk}', '').strip()

            if mc or mn:
                defaults = {
                    'note_max_classe': note_max_c,
                    'note_max_compo': note_max_n,
                    'saisi_par': request.user,
                }
                if mc:
                    defaults['moy_classe'] = Decimal(mc.replace(',', '.'))
                if mn:
                    defaults['moy_compo'] = Decimal(mn.replace(',', '.'))

                NotePeriode.objects.update_or_create(
                    eleve=insc.eleve, matiere=matiere,
                    classe=classe, periode=periode,
                    defaults=defaults
                )
                saved += 1

        messages.success(request, f"{saved} note(s) enregistree(s) — {matiere.nom} — {classe.nom}")
        return redirect(f"{request.path}?classe={classe_id}&periode={periode_id}&matiere={matiere_id}")

    return render(request, 'notes/saisie_notes_mali.html', {
        'classes': classes, 'periodes': periodes, 'matieres': matieres,
        'classe': classe, 'periode': periode, 'matiere': matiere,
        'eleves_data': eleves_data,
        'classe_id': classe_id, 'periode_id': periode_id, 'modele_actif': modele_actif, 'matiere_id': matiere_id,
    })


@login_required
@require_etab
def bulletin_mali(request, eleve_pk, periode_pk):
    """Génère le bulletin au format malien officiel"""
    etab = request.etablissement
    eleve = get_object_or_404(Eleve, pk=eleve_pk, etablissement=etab)
    periode = get_object_or_404(Periode, pk=periode_pk, etablissement=etab)
    annee = AnneeScolaire.objects.filter(etablissement=etab, is_active=True).first()
    inscription = eleve.get_inscription_active()
    matieres = Matiere.objects.filter(etablissement=etab).order_by('nom')

    lignes, moy_generale, total_coeffic, total_coef = calculer_bulletin_mali(eleve, periode, matieres)

    # Rang dans la classe
    rang = None
    moy_premier = None
    effectif = 0
    if inscription:
        classe = inscription.classe
        effectif = classe.inscriptions.filter(is_active=True).count()
        moyennes_classe = []
        for insc in classe.inscriptions.filter(is_active=True).select_related('eleve'):
            _, moy, _, _ = calculer_bulletin_mali(insc.eleve, periode, matieres)
            if moy is not None:
                moyennes_classe.append((insc.eleve.pk, moy))

        moyennes_classe.sort(key=lambda x: x[1], reverse=True)
        if moyennes_classe:
            moy_premier = moyennes_classe[0][1]
        for i, (epk, _) in enumerate(moyennes_classe, 1):
            if epk == eleve.pk:
                rang = i
                break

    # Appréciation directeur
    appre_directeur = ''
    if moy_generale is not None:
        if moy_generale >= 16: appre_directeur = 'Excellent Travail'
        elif moy_generale >= 14: appre_directeur = 'Bon Travail'
        elif moy_generale >= 12: appre_directeur = 'Travail Assez Bien'
        elif moy_generale >= 10: appre_directeur = 'Travail Passable'
        elif moy_generale >= 6:  appre_directeur = 'Travail Insuffisant'
        else: appre_directeur = 'Travail Très Insuffisant'

    # Paramètres établissement
    try:
        params = etab.parametres
    except:
        params = None

    return render(request, 'notes/bulletin_mali.html', {
        'eleve': eleve,
        'periode': periode,
        'annee': annee,
        'etab': etab,
        'params': params,
        'inscription': inscription,
        'lignes': lignes,
        'moy_generale': moy_generale,
        'total_coeffic': total_coeffic,
        'total_coef': total_coef,
        'rang': rang,
        'effectif': effectif,
        'moy_premier': moy_premier,
        'appre_directeur': appre_directeur,
    })


@login_required
@require_etab
def bulletins_classe_mali(request):
    """Liste des bulletins d'une classe pour impression groupée"""
    etab = request.etablissement
    annee = AnneeScolaire.objects.filter(etablissement=etab, is_active=True).first()
    classes = get_classes_actives(etab, annee) if annee else []
    periodes = Periode.objects.filter(etablissement=etab, annee=annee) if annee else []

    classe_id = request.GET.get('classe')
    periode_id = request.GET.get('periode')
    classe = get_object_or_404(Classe, pk=classe_id, etablissement=etab) if classe_id else None
    periode = get_object_or_404(Periode, pk=periode_id, etablissement=etab) if periode_id else None

    resultats = []
    matieres = Matiere.objects.filter(etablissement=etab).order_by('nom')

    if classe and periode:
        inscriptions = classe.inscriptions.filter(is_active=True).select_related('eleve').order_by('eleve__nom')
        for insc in inscriptions:
            _, moy, total_coeff, total_c = calculer_bulletin_mali(insc.eleve, periode, matieres)
            resultats.append({'eleve': insc.eleve, 'moyenne': moy})

        resultats.sort(key=lambda x: x['moyenne'] or 0, reverse=True)
        for i, r in enumerate(resultats, 1):
            r['rang'] = i
        moy_premier = resultats[0]['moyenne'] if resultats else None
    else:
        moy_premier = None

    modele_actif = ModeleDocument.objects.filter(etablissement=etab, type_document='bulletin', is_actif=True).first() if etab else None
    return render(request, 'notes/bulletins_classe_mali.html', {
        'classes': classes, 'periodes': periodes,
        'classe': classe, 'periode': periode,
        'resultats': resultats,
        'moy_premier': moy_premier,
        'classe_id': classe_id, 'periode_id': periode_id, 'modele_actif': modele_actif,
    })
