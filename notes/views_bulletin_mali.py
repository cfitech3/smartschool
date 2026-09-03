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
def telecharger_bulletin_pdf_mali(request, eleve_pk, periode_pk):
    """Télécharge le bulletin en format PDF."""
    etab = request.etablissement
    eleve = get_object_or_404(Eleve, pk=eleve_pk, etablissement=etab)
    annee = AnneeScolaire.objects.filter(etablissement=etab, is_active=True).first()
    inscription = eleve.get_inscription_active()
    
    is_premier_cycle = False
    if inscription and inscription.classe.niveau and inscription.classe.niveau.cycle:
        cycle = inscription.classe.niveau.cycle
        is_premier_cycle = cycle.is_premier_cycle and cycle.utilise_compositions_multiples

    classe_pour_matieres = inscription.classe if inscription else None
    
    if is_premier_cycle:
        # Pour le 1er cycle, periode_pk est en fait le numero de composition
        numero = periode_pk
        matieres = get_matieres_pour_eleve(eleve, annee, classe_pour_matieres)
        from notes.services import calculer_bulletin_composition
        lignes, moy_generale, total_coeffic, total_coef = calculer_bulletin_composition(eleve, annee, numero, matieres)
        # Adapt data for PDF generator since it expects NotePeriode format
        for ligne in lignes:
            ligne['moy_classe'] = None
            ligne['moy_compo'] = ligne['note']
            ligne['moyenne_finale'] = ligne['note']
            ligne['moy_coeffic'] = ligne['note']
        periode = None
    else:
        periode = get_object_or_404(Periode, pk=periode_pk, etablissement=etab)
        matieres = get_matieres_pour_eleve(eleve, periode, classe_pour_matieres)
        lignes, moy_generale, total_coeffic, total_coef = calculer_bulletin(eleve, periode, matieres)

    rang = None
    moy_premier = None
    effectif = 0
    if inscription:
        classe = inscription.classe
        effectif = classe.inscriptions.filter(is_active=True).count()

        if is_premier_cycle:
            # 1er cycle : rang basé sur les Compositions
            from notes.views_notes import calculer_rangs_classe_composition
            rangs_classe = calculer_rangs_classe_composition(classe, annee, numero, matieres)
            rang = rangs_classe.get(eleve.pk)
            if rangs_classe:
                pk_premier = next((pk for pk, r in rangs_classe.items() if r == 1), None)
                if pk_premier is not None:
                    from notes.services import calculer_bulletin_composition
                    _, moy_premier, _, _ = calculer_bulletin_composition(
                        Eleve.objects.get(pk=pk_premier), annee, numero, matieres
                    )
        else:
            rangs_classe = calculer_rangs_classe(classe, periode, matieres)
            rang = rangs_classe.get(eleve.pk)
            if rangs_classe:
                pk_premier = next((pk for pk, r in rangs_classe.items() if r == 1), None)
                if pk_premier is not None:
                    _, moy_premier, _, _ = calculer_bulletin(Eleve.objects.get(pk=pk_premier), periode, matieres)

    appre_directeur = ''
    if moy_generale is not None:
        if is_premier_cycle:
            if moy_generale >= 8: appre_directeur = 'Excellent Travail'
            elif moy_generale >= 6.5: appre_directeur = 'Bon Travail'
            elif moy_generale >= 5: appre_directeur = 'Travail Passable'
            else: appre_directeur = 'Travail Insuffisant'
        else:
            if moy_generale >= 16: appre_directeur = 'Excellent Travail'
            elif moy_generale >= 14: appre_directeur = 'Bon Travail'
            elif moy_generale >= 12: appre_directeur = 'Travail Assez Bien'
            elif moy_generale >= 10: appre_directeur = 'Travail Passable'
            elif moy_generale >= 6:  appre_directeur = 'Travail Insuffisant'
            else: appre_directeur = 'Travail Très Insuffisant'

    response = HttpResponse(content_type='application/pdf')
    periode_label = f"Composition_{numero}" if is_premier_cycle else periode.libelle
    response['Content-Disposition'] = f'attachment; filename="Bulletin_{eleve.nom}_{eleve.prenom}_{periode_label}.pdf"'
    
    modele = ModeleDocument.objects.filter(etablissement=etab, type_document='bulletin', is_actif=True).first()

    generer_bulletin_pdf(response, eleve, periode, annee, etab, inscription, lignes, moy_generale, total_coeffic, total_coef, rang, effectif, appre_directeur, modele, is_premier_cycle=is_premier_cycle, moy_premier=moy_premier)
    
    return response
