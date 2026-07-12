from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import Q
from django.http import HttpResponse
from .models import Matiere, Periode, NotePeriode, Bulletin
from .services import calculer_bulletin, get_matieres_pour_eleve, get_matieres_pour_classe
from .views_notes import calculer_rangs_classe
from .pdf_generator import generer_bulletin_pdf
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

    # Récupérer le modèle de document actif pour le bulletin (utilisé éventuellement dans le template)
    modele_actif = ModeleDocument.objects.filter(
        etablissement=etab, type_document='bulletin', is_actif=True
    ).first() if etab else None

    return render(request, 'notes/saisie_notes_mali.html', {
        'classes': classes, 'periodes': periodes, 'matieres': matieres,
        'classe': classe, 'periode': periode, 'matiere': matiere,
        'eleves_data': eleves_data,
        'modele_actif': modele_actif,
        'classe_id': classe_id, 'periode_id': periode_id, 'matiere_id': matiere_id,
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
    
    classe_pour_matieres = inscription.classe if inscription else None
    matieres = get_matieres_pour_eleve(eleve, periode, classe_pour_matieres)

    lignes, moy_generale, total_coeffic, total_coef = calculer_bulletin(eleve, periode, matieres)

    # Rang dans la classe : calcul O(n) via un seul batch SQL
    rang = None
    moy_premier = None
    effectif = 0
    if inscription:
        classe = inscription.classe
        effectif = classe.inscriptions.filter(is_active=True).count()

        rangs_classe = calculer_rangs_classe(classe, periode, matieres)
        rang = rangs_classe.get(eleve.pk)

        # Retrouver la moyenne du premier élève classé
        if rangs_classe:
            pk_premier = next(
                (pk for pk, r in rangs_classe.items() if r == 1), None
            )
            if pk_premier is not None:
                _, moy_premier, _, _ = calculer_bulletin(
                    Eleve.objects.get(pk=pk_premier), periode, matieres
                )

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
    classe  = get_object_or_404(Classe,  pk=classe_id,  etablissement=etab) if classe_id  else None
    periode = get_object_or_404(Periode, pk=periode_id, etablissement=etab) if periode_id else None

    resultats = []
    moy_premier = None
    modele_actif = ModeleDocument.objects.filter(etablissement=etab, type_document='bulletin', is_actif=True).first()

    if classe and periode:
        matieres = get_matieres_pour_classe(classe, periode)
        inscriptions = classe.inscriptions.filter(is_active=True).select_related('eleve').order_by('eleve__nom')

        # P2.5 : Préchargement des notes pour éviter N+1 requêtes
        toutes_notes = NotePeriode.objects.filter(classe=classe, periode=periode)
        index_notes = {(n.eleve_id, n.matiere_id): n for n in toutes_notes}

        # Calcul global des rangs en O(n)
        rangs_dict = calculer_rangs_classe(classe, periode, matieres)

        for insc in inscriptions:
            _, moy, _, _ = calculer_bulletin(insc.eleve, periode, matieres, index_notes=index_notes)
            resultats.append({
                'eleve': insc.eleve,
                'moyenne': moy,
                'rang': rangs_dict.get(insc.eleve_id),
            })

        # Trier par rang croissant (les élèves sans notes n'ont pas de rang)
        resultats.sort(key=lambda x: (x['rang'] is None, x['rang'] or 9999))
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

@login_required
def telecharger_bulletin_pdf_mali(request, eleve_pk, periode_pk):
    """Télécharge le bulletin en format PDF."""
    etab = request.etablissement
    eleve = get_object_or_404(Eleve, pk=eleve_pk, etablissement=etab)
    periode = get_object_or_404(Periode, pk=periode_pk, etablissement=etab)
    annee = AnneeScolaire.objects.filter(etablissement=etab, is_active=True).first()
    inscription = eleve.get_inscription_active()
    
    classe_pour_matieres = inscription.classe if inscription else None
    matieres = get_matieres_pour_eleve(eleve, periode, classe_pour_matieres)
    lignes, moy_generale, total_coeffic, total_coef = calculer_bulletin(eleve, periode, matieres)

    rang = None
    moy_premier = None
    effectif = 0
    if inscription:
        classe = inscription.classe
        effectif = classe.inscriptions.filter(is_active=True).count()
        rangs_classe = calculer_rangs_classe(classe, periode, matieres)
        rang = rangs_classe.get(eleve.pk)
        if rangs_classe:
            pk_premier = next((pk for pk, r in rangs_classe.items() if r == 1), None)
            if pk_premier is not None:
                _, moy_premier, _, _ = calculer_bulletin(Eleve.objects.get(pk=pk_premier), periode, matieres)

    appre_directeur = ''
    if moy_generale is not None:
        if moy_generale >= 16: appre_directeur = 'Excellent Travail'
        elif moy_generale >= 14: appre_directeur = 'Bon Travail'
        elif moy_generale >= 12: appre_directeur = 'Travail Assez Bien'
        elif moy_generale >= 10: appre_directeur = 'Travail Passable'
        elif moy_generale >= 6:  appre_directeur = 'Travail Insuffisant'
        else: appre_directeur = 'Travail Très Insuffisant'

    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="Bulletin_{eleve.nom}_{eleve.prenom}_{periode.libelle}.pdf"'
    
    modele = ModeleDocument.objects.filter(etablissement=etab, type_document='bulletin', is_actif=True).first()

    generer_bulletin_pdf(response, eleve, periode, annee, etab, inscription, lignes, moy_generale, total_coeffic, total_coef, rang, effectif, appre_directeur, modele)
    
    return response
