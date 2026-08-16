from decimal import Decimal
from .models import NotePeriode

def calculer_bulletin(eleve, periode, matieres, index_notes=None):
    """
    Calcule le bulletin (commun ou malien).
    Si index_notes (dict {(eleve_id, matiere_id): note}) est fourni,
    évite les requêtes SQL (utile pour les traitements par lot O(n)).
    Retourne: lignes, moyenne_generale, total_coeffic, total_coef
    """
    lignes = []
    total_coeffic = Decimal('0')
    total_coef = 0

    for mat in matieres:
        if index_notes is not None:
            note = index_notes.get((eleve.pk, mat.pk))
        else:
            note = NotePeriode.objects.filter(eleve=eleve, matiere=mat, periode=periode).first()
        if note:
            moy_finale = note.moyenne_finale
            moy_coeff  = note.moy_coeffic
            appre      = note.appreciation
            if moy_coeff is not None:
                total_coeffic += Decimal(str(moy_coeff))
                total_coef += mat.coefficient
            lignes.append({
                'matiere': mat,
                'moy_classe': float(note.moy_classe) if note.moy_classe is not None else None,
                'moy_compo': float(note.moy_compo) if note.moy_compo is not None else None,
                'note_conduite': float(note.note_conduite) if note.note_conduite is not None else None,
                'moyenne_finale': moy_finale,
                'moy_coeffic': moy_coeff,
                'appreciation': appre,
                'note_max_classe': float(note.note_max_classe),
                'note_max_compo': float(note.note_max_compo),
            })
        else:
            lignes.append({
                'matiere': mat,
                'moy_classe': None, 'moy_compo': None, 'note_conduite': None,
                'moyenne_finale': None, 'moy_coeffic': None, 'appreciation': '',
                'note_max_classe': 20.0, 'note_max_compo': 40.0,
            })

    moy_gen = None
    if total_coef > 0:
        moy_gen = round(float(total_coeffic) / total_coef, 2)

    # Conduite toujours en dernière ligne du bulletin
    lignes.sort(key=lambda l: (1 if l['matiere'].is_conduite else 0, l['matiere'].nom))

    return lignes, moy_gen, total_coeffic, total_coef


def calculer_bulletin_composition(eleve, periode, numero, matieres):
    """
    Calcule le 'bulletin de composition' : pour le 1er cycle fondamental
    avec compositions multiples, chaque composition (1 à 9) génère son
    propre document, listant la note obtenue à CETTE composition précise
    pour chaque matière — distinct du bulletin trimestriel classique qui,
    lui, affiche Moy.Classe + Moy.Compo (moyenne des compositions).

    Retourne: lignes, moyenne_generale, total_coeffic, total_coef
    (même structure que calculer_bulletin, pour réutiliser les mêmes
    templates/logique d'affichage).
    """
    from .models import Composition

    lignes = []
    total_coeffic = Decimal('0')
    total_coef = 0

    for mat in matieres:
        if mat.is_conduite:
            continue  # la conduite n'a pas de composition individuelle
        compo = Composition.objects.filter(
            eleve=eleve, matiere=mat, periode=periode, numero=numero
        ).first()

        if compo and compo.note is not None:
            note_sur_20 = round((float(compo.note) / float(compo.note_max)) * 20, 2)
            moy_coeff = round(note_sur_20 * mat.coefficient, 2)
            total_coeffic += Decimal(str(moy_coeff))
            total_coef += mat.coefficient
            appre = (
                'Tres-Bien' if note_sur_20 >= 16 else
                'Bien' if note_sur_20 >= 14 else
                'Assez-Bien' if note_sur_20 >= 12 else
                'Passable' if note_sur_20 >= 10 else
                'Mal' if note_sur_20 >= 6 else 'Tres Mal'
            )
            lignes.append({
                'matiere': mat, 'note': note_sur_20, 'moy_coeffic': moy_coeff,
                'appreciation': appre,
            })
        else:
            lignes.append({
                'matiere': mat, 'note': None, 'moy_coeffic': None, 'appreciation': '',
            })

    moy_gen = None
    if total_coef > 0:
        moy_gen = round(float(total_coeffic) / total_coef, 2)

    lignes.sort(key=lambda l: l['matiere'].nom)
    return lignes, moy_gen, total_coeffic, total_coef


def get_matieres_pour_eleve(eleve, periode, classe=None):
    from etablissements.models import AffectationMatiere
    from .models import Matiere, NotePeriode
    mat_ids = set()
    
    if classe:
        mat_ids.update(
            AffectationMatiere.objects.filter(classe=classe, annee=periode.annee)
            .values_list('matiere_id', flat=True)
        )
    
    mat_ids.update(
        NotePeriode.objects.filter(eleve=eleve, periode=periode)
        .values_list('matiere_id', flat=True)
    )
    
    return Matiere.objects.filter(id__in=mat_ids).order_by('nom')


def get_matieres_pour_classe(classe, periode):
    from etablissements.models import AffectationMatiere
    from .models import Matiere, NotePeriode
    mat_ids = set()
    
    mat_ids.update(
        AffectationMatiere.objects.filter(classe=classe, annee=periode.annee)
        .values_list('matiere_id', flat=True)
    )
    
    mat_ids.update(
        NotePeriode.objects.filter(classe=classe, periode=periode)
        .values_list('matiere_id', flat=True)
    )
    
    return Matiere.objects.filter(id__in=mat_ids).order_by('nom')
