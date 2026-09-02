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


def calculer_bulletin_composition(eleve, annee, numero, matieres):
    """
    Calcule le 'bulletin de composition' pour le 1er cycle fondamental.

    Au 1er cycle :
    - Les notes sont sur 10 (note_max = 10)
    - Le coefficient est 1 pour toutes les matières
    - Pas de conversion en /20 : la note est affichée directement /10
    - La moyenne générale est calculée sur 10

    Retourne: lignes, moyenne_generale, total_coeffic, total_coef
    """
    from .models import Composition

    lignes = []
    total_coeffic = Decimal('0')
    total_coef = 0

    for mat in matieres:
        if mat.is_conduite:
            continue  # la conduite n'a pas de composition individuelle
        # Les compositions du 1er cycle sont liées à l'année scolaire (annee),
        # et non à une période (trimestre). On cherche par annee.
        compo = Composition.objects.filter(
            eleve=eleve, matiere=mat, annee=annee, numero=numero
        ).first()

        # Coef forcé à 1 pour le 1er cycle
        coef = 1

        if compo and compo.note is not None:
            # note_max est 10 par défaut pour le 1er cycle
            note_sur_10 = round((float(compo.note) / float(compo.note_max)) * 10, 2)
            moy_coeff = round(note_sur_10 * coef, 2)  # coef=1 => moy_coeff = note
            total_coeffic += Decimal(str(moy_coeff))
            total_coef += coef
            appre = (
                'Tres-Bien'  if note_sur_10 >= 8 else
                'Bien'       if note_sur_10 >= 7 else
                'Assez-Bien' if note_sur_10 >= 6 else
                'Passable'   if note_sur_10 >= 5 else
                'Mal'        if note_sur_10 >= 3 else 'Tres Mal'
            )
            lignes.append({
                'matiere': mat,
                'note': note_sur_10,
                'moy_coeffic': moy_coeff,
                'appreciation': appre,
                'coef': coef,
            })
        else:
            lignes.append({
                'matiere': mat, 'note': None, 'moy_coeffic': None,
                'appreciation': '', 'coef': coef,
            })

    moy_gen = None
    if total_coef > 0:
        moy_gen = round(float(total_coeffic) / total_coef, 2)

    lignes.sort(key=lambda l: l['matiere'].nom)
    return lignes, moy_gen, total_coeffic, total_coef


def get_matieres_pour_eleve(eleve, annee_ou_periode, classe=None):
    """
    Retourne les matières de l'élève.
    annee_ou_periode peut être une AnneeScolaire (1er cycle avec Composition)
    ou une Periode (autres cycles avec NotePeriode).
    """
    from etablissements.models import AffectationMatiere, AnneeScolaire
    from .models import Matiere, NotePeriode
    mat_ids = set()

    if isinstance(annee_ou_periode, AnneeScolaire):
        # 1er cycle : on récupère les matières via les affectations de la classe
        annee = annee_ou_periode
        if classe:
            mat_ids.update(
                AffectationMatiere.objects.filter(classe=classe, annee=annee)
                .values_list('matiere_id', flat=True)
            )
    else:
        # Autres cycles : annee_ou_periode est une Periode
        periode = annee_ou_periode
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
