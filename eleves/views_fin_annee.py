"""
Assistant de fin d'année scolaire — Version complète.
Fonctionnalités :
  - Calcul automatique des moyennes → décision proposée (admis/redouble)
  - Classe suivante suggérée automatiquement selon l'ordre des niveaux
  - Décision manuelle corrigeable (admis / redouble / exclu)
  - Récapitulatif avant validation définitive
  - Clôture de l'année active + activation de la suivante
"""
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from eleves.models import Eleve, Inscription
from etablissements.models import Classe, AnneeScolaire, Niveau
from notes.models import Periode
from notes.views import calculer_moyenne_eleve
from notes.models import Matiere
from core.cycle_filter import get_classes_actives


def _get_classe_suivante(classe_actuelle):
    """
    Retourne la classe suggérée pour l'année suivante :
    même nom mais niveau d'ordre supérieur.
    """
    niveau = classe_actuelle.niveau
    if not niveau:
        return None
    # Trouver le niveau suivant dans le même cycle (ordre + 1)
    niveaux_cycle = Niveau.objects.filter(
        cycle=niveau.cycle, ordre__gt=niveau.ordre
    ).order_by('ordre')
    niveau_suivant = niveaux_cycle.first()
    if not niveau_suivant:
        return None
    # Prendre la première classe du niveau suivant (même établissement)
    classe_suiv = Classe.objects.filter(
        etablissement=classe_actuelle.etablissement,
        niveau=niveau_suivant,
    ).first()
    return classe_suiv


def _calculer_moyenne_annuelle(eleve, classe, annee):
    """Calcule la moyenne annuelle d'un élève sur toutes les périodes actives."""
    periodes = Periode.objects.filter(etablissement=classe.etablissement, is_active=True)
    if not periodes.exists():
        periodes = Periode.objects.filter(etablissement=classe.etablissement)

    total_points = 0.0
    total_coef = 0.0

    for periode in periodes:
        try:
            matieres = Matiere.objects.filter(etablissement=classe.etablissement)
            moy, _ = calculer_moyenne_eleve(eleve, periode, matieres)
            if moy is not None:
                total_points += float(moy)
                total_coef += 1
        except Exception:
            continue

    if total_coef == 0:
        return None
    return round(total_points / total_coef, 2)


@login_required
def assistant_fin_annee(request):
    if request.user.role not in ('admin', 'super_admin', 'secretariat'):
        messages.error(request, "Accès refusé.")
        return redirect('dashboard')

    etab = request.etablissement
    annees = AnneeScolaire.objects.filter(etablissement=etab).order_by('-date_debut')
    annee_active = annees.filter(is_active=True).first()
    classes = get_classes_actives(etab, annee_active) if annee_active else []

    classe_actuelle_id = request.GET.get('classe_actuelle') or request.POST.get('classe_actuelle')
    annee_suivante_id  = request.GET.get('annee_suivante')  or request.POST.get('annee_suivante')
    etape = request.GET.get('etape', '1')  # 1=selection, 2=decisions, 3=recapitulatif

    classe_actuelle = None
    annee_suivante  = None
    eleves_data     = []

    if classe_actuelle_id and annee_suivante_id:
        classe_actuelle = get_object_or_404(Classe, pk=classe_actuelle_id, etablissement=etab)
        annee_suivante  = get_object_or_404(AnneeScolaire, pk=annee_suivante_id, etablissement=etab)
        classe_suivante_suggeree = _get_classe_suivante(classe_actuelle)

        note_passage = float(
            classe_actuelle.niveau.cycle.note_passage
            if classe_actuelle.niveau and classe_actuelle.niveau.cycle
            else 10
        )

        inscriptions = classe_actuelle.inscriptions.filter(
            annee=annee_active, is_active=True
        ).select_related('eleve')

        for insc in inscriptions:
            eleve = insc.eleve
            deja_inscrit = Inscription.objects.filter(
                eleve=eleve, annee=annee_suivante
            ).exists()

            # Calcul moyenne annuelle
            moyenne = _calculer_moyenne_annuelle(eleve, classe_actuelle, annee_active)

            # Décision suggérée automatiquement
            if moyenne is None:
                decision_suggeree = 'sans_note'
            elif float(moyenne) >= note_passage:
                decision_suggeree = 'admis'
            else:
                decision_suggeree = 'redouble'

            eleves_data.append({
                'inscription': insc,
                'eleve': eleve,
                'moyenne': moyenne,
                'note_passage': note_passage,
                'decision_suggeree': decision_suggeree,
                'deja_inscrit': deja_inscrit,
            })

    # ── ÉTAPE 3 : Validation finale ────────────────────────────────────────
    if request.method == 'POST' and request.POST.get('action') == 'valider':
        classe_suivante_id = request.POST.get('classe_suivante_globale')
        decisions = {}

        for key, val in request.POST.items():
            if key.startswith('decision_'):
                eleve_pk = key.replace('decision_', '')
                decisions[eleve_pk] = val

        try:
            with transaction.atomic():
                nb_admis = nb_redouble = nb_exclus = 0
                for eleve_pk, decision in decisions.items():
                    eleve = get_object_or_404(Eleve, pk=eleve_pk, etablissement=etab)

                    if Inscription.objects.filter(eleve=eleve, annee=annee_suivante).exists():
                        continue

                    if decision == 'admis' and classe_suivante_id:
                        classe_dest = get_object_or_404(Classe, pk=classe_suivante_id, etablissement=etab)
                        Inscription.objects.create(
                            eleve=eleve, classe=classe_dest,
                            annee=annee_suivante, statut='actif', is_active=True
                        )
                        nb_admis += 1

                    elif decision == 'redouble':
                        Inscription.objects.create(
                            eleve=eleve, classe=classe_actuelle,
                            annee=annee_suivante, statut='actif', is_active=True
                        )
                        nb_redouble += 1

                    elif decision == 'exclu':
                        # Marquer l'inscription actuelle comme inactive
                        Inscription.objects.filter(
                            eleve=eleve, annee=annee_active
                        ).update(is_active=False, statut='exclu')
                        nb_exclus += 1

            messages.success(
                request,
                f"✅ Passages traités : {nb_admis} admis, {nb_redouble} redoublant(s), {nb_exclus} exclu(s) — Année {annee_suivante.libelle}."
            )
            return redirect('assistant_fin_annee')

        except Exception as ex:
            messages.error(request, f"Erreur : {str(ex)}")

    # ── CLÔTURE ANNÉE ──────────────────────────────────────────────────────
    if request.method == 'POST' and request.POST.get('action') == 'cloturer_annee':
        annee_a_cloturer_id = request.POST.get('annee_a_cloturer')
        annee_a_activer_id  = request.POST.get('annee_a_activer')

        try:
            with transaction.atomic():
                if annee_a_cloturer_id:
                    AnneeScolaire.objects.filter(pk=annee_a_cloturer_id, etablissement=etab).update(is_active=False)
                if annee_a_activer_id:
                    AnneeScolaire.objects.filter(pk=annee_a_activer_id, etablissement=etab).update(is_active=True)
            messages.success(request, "✅ Année clôturée et nouvelle année activée.")
        except Exception as ex:
            messages.error(request, f"Erreur clôture : {str(ex)}")
        return redirect('assistant_fin_annee')

    classe_suivante_suggeree = _get_classe_suivante(classe_actuelle) if classe_actuelle else None

    # Stats récapitulatif
    stats = None
    if eleves_data:
        stats = {
            'total': len(eleves_data),
            'avec_notes': sum(1 for e in eleves_data if e['moyenne'] is not None),
            'admis_auto': sum(1 for e in eleves_data if e['decision_suggeree'] == 'admis'),
            'redouble_auto': sum(1 for e in eleves_data if e['decision_suggeree'] == 'redouble'),
            'sans_notes': sum(1 for e in eleves_data if e['decision_suggeree'] == 'sans_note'),
            'deja_inscrits': sum(1 for e in eleves_data if e['deja_inscrit']),
        }

    return render(request, 'eleves/assistant_fin_annee.html', {
        'annees': annees,
        'annee_active': annee_active,
        'classes': classes,
        'classe_actuelle': classe_actuelle,
        'annee_suivante': annee_suivante,
        'classe_suivante_suggeree': classe_suivante_suggeree,
        'eleves_data': eleves_data,
        'classe_actuelle_id': classe_actuelle_id,
        'annee_suivante_id': annee_suivante_id,
        'stats': stats,
        'toutes_classes': Classe.objects.filter(etablissement=etab).order_by('niveau__ordre', 'nom'),
    })
