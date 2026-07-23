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
