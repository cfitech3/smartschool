"""
Génère le bulletin en utilisant les paramètres du ModeleDocument
"""
from django.shortcuts import render, get_object_or_404
from django.contrib.auth.decorators import login_required
from etablissements.models import ModeleDocument, AnneeScolaire
from eleves.models import Eleve, Inscription
from notes.models import Matiere, Periode
from notes.services import calculer_bulletin, get_matieres_pour_eleve


def require_etab(fn):
    def wrapper(request, *args, **kwargs):
        if not request.etablissement:
            from django.shortcuts import redirect
            return redirect('dashboard')
        return fn(request, *args, **kwargs)
    wrapper.__name__ = fn.__name__
    return wrapper


@login_required
@require_etab
def bulletin_custom(request, eleve_pk, periode_pk, modele_pk=None):
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
        numero = periode_pk
        matieres = get_matieres_pour_eleve(eleve, annee, classe_pour_matieres)
        from notes.services import calculer_bulletin_composition
        lignes, moy_generale, total_coeffic, total_coef = calculer_bulletin_composition(eleve, annee, numero, matieres)
        periode = None
    else:
        periode = get_object_or_404(Periode, pk=periode_pk, etablissement=etab)
        matieres = get_matieres_pour_eleve(eleve, periode, classe_pour_matieres)
        lignes, moy_generale, total_coeffic, total_coef = calculer_bulletin(eleve, periode, matieres)

    # Récupérer le modèle actif ou spécifié
    if modele_pk:
        modele = get_object_or_404(ModeleDocument, pk=modele_pk, etablissement=etab)
    else:
        modele = ModeleDocument.objects.filter(
            etablissement=etab,
            type_document='bulletin',
            is_actif=True
        ).first()

    # Rang + moy premier
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
            # Autres cycles : rang basé sur NotePeriode
            from notes.views_notes import calculer_rangs_classe
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
            if moy_generale >= 16:   appre_directeur = 'Excellent Travail'
            elif moy_generale >= 14: appre_directeur = 'Bon Travail'
            elif moy_generale >= 12: appre_directeur = 'Travail Assez Bien'
            elif moy_generale >= 10: appre_directeur = 'Travail Passable'
            elif moy_generale >= 6:  appre_directeur = 'Travail Insuffisant'
            else:                     appre_directeur = 'Travail Très Insuffisant'

    return render(request, 'notes/bulletin_custom.html', {
        'eleve': eleve, 'periode': periode, 'annee': annee,
        'etab': etab, 'modele': modele, 'inscription': inscription,
        'lignes': lignes, 'moy_generale': moy_generale,
        'total_coeffic': total_coeffic, 'total_coef': total_coef,
        'rang': rang, 'effectif': effectif, 'moy_premier': moy_premier,
        'appre_directeur': appre_directeur,
    })
