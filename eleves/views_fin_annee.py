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
from notes.models import Periode, Matiere
from notes.services import calculer_bulletin
from core.cycle_filter import get_classes_actives


def _get_classe_suivante(classe_actuelle, annee_suivante=None):
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
    # Prendre la première classe du niveau suivant (même filière en priorité si renseignée)
    qs = Classe.objects.filter(
        etablissement=classe_actuelle.etablissement,
        niveau=niveau_suivant,
    )
    if annee_suivante:
        qs_annee = qs.filter(annee=annee_suivante)
        if classe_actuelle.filiere:
            cl_fil = qs_annee.filter(filiere__iexact=classe_actuelle.filiere).first()
            if cl_fil:
                return cl_fil
        classe_suiv = qs_annee.first()
        if classe_suiv:
            return classe_suiv
    if classe_actuelle.filiere:
        cl_fil = qs.filter(filiere__iexact=classe_actuelle.filiere).first()
        if cl_fil:
            return cl_fil
    return qs.first()


def _calculer_moyennes_annuelles_classe(eleves_list, classe, annee):
    """
    Calcule en lot (O(1) requêtes SQL) la moyenne annuelle de tous les élèves
    d'une classe sur l'année scolaire donnée, en respectant les coefficients de
    série/cycle. Retourne un dict {eleve_pk: moyenne_ou_None}.
    """
    from decimal import Decimal
    from notes.services import get_matieres_pour_classe, get_coefficients_map, calculer_bulletin

    eleves_ids = [e.pk for e in eleves_list]
    resultats = {eid: None for eid in eleves_ids}
    if not eleves_ids or not annee:
        return resultats

    cycle = classe.niveau.cycle if (classe.niveau and classe.niveau.cycle) else None

    # ── UNIVERSITÉ : NoteUE /20 pondérées par crédits ECTS (1 requête) ───────
    if cycle and cycle.is_universite:
        from notes.models import NoteUE
        pts_map = {eid: 0.0 for eid in eleves_ids}
        cred_map = {eid: 0 for eid in eleves_ids}
        for n in NoteUE.objects.filter(eleve_id__in=eleves_ids, periode__annee=annee).select_related('ue'):
            if n.note_retenue is not None:
                c = n.ue.credits or 1
                pts_map[n.eleve_id] += float(n.note_retenue) * c
                cred_map[n.eleve_id] += c
        for eid in eleves_ids:
            if cred_map[eid] > 0:
                resultats[eid] = round(pts_map[eid] / cred_map[eid], 2)
        return resultats

    # ── 1ER CYCLE : Compositions /10 (1 requête) ─────────────────────────────
    if cycle and cycle.is_premier_cycle and cycle.utilise_compositions_multiples:
        from notes.models import Composition
        tot_map = {eid: Decimal('0') for eid in eleves_ids}
        cnt_map = {eid: 0 for eid in eleves_ids}
        for c in Composition.objects.filter(
            eleve_id__in=eleves_ids, classe=classe, annee=annee
        ).exclude(note__isnull=True):
            if c.note_max:
                tot_map[c.eleve_id] += (c.note / c.note_max) * 10
                cnt_map[c.eleve_id] += 1
        for eid in eleves_ids:
            if cnt_map[eid] > 0:
                resultats[eid] = round(float(tot_map[eid] / cnt_map[eid]), 2)
        return resultats

    # ── AUTRES CYCLES : NotePeriode préchargées sur toutes les périodes ──────
    from notes.models import NotePeriode
    periodes = list(Periode.objects.filter(etablissement=classe.etablissement, annee=annee))
    if not periodes:
        return resultats

    matieres = list(get_matieres_pour_classe(classe).filter(is_conduite=False))
    if not matieres:
        matieres = list(Matiere.objects.filter(etablissement=classe.etablissement, is_conduite=False))
    coefs_map = get_coefficients_map(classe, matieres)

    notes_par_periode = {p.pk: {} for p in periodes}
    for np in NotePeriode.objects.filter(
        eleve_id__in=eleves_ids, periode__in=periodes
    ).select_related('matiere').order_by('date_modif', 'pk'):
        key = (np.eleve_id, np.matiere_id)
        if np.classe_id == classe.pk or key not in notes_par_periode[np.periode_id]:
            notes_par_periode[np.periode_id][key] = np

    for eleve in eleves_list:
        total_points = 0.0
        nb_per = 0
        for p in periodes:
            _, moy_p, _, _ = calculer_bulletin(
                eleve, p, matieres,
                index_notes=notes_par_periode[p.pk],
                classe=classe,
                coefs_map=coefs_map,
            )
            if moy_p is not None:
                total_points += float(moy_p)
                nb_per += 1
        if nb_per > 0:
            resultats[eleve.pk] = round(total_points / nb_per, 2)
    return resultats


def _calculer_moyenne_annuelle(eleve, classe, annee):
    """Compatibilité unitaire : délègue au calcul batch pour un seul élève."""
    return _calculer_moyennes_annuelles_classe([eleve], classe, annee).get(eleve.pk)


@login_required
def assistant_fin_annee(request):
    if request.user.role not in ('admin', 'super_admin', 'secretariat'):
        messages.error(request, "Accès refusé.")
        return redirect('dashboard')

    etab = request.etablissement
    if not etab:
        return redirect('dashboard')
    annees = AnneeScolaire.objects.filter(etablissement=etab).order_by('-date_debut')
    annee_active = annees.filter(is_active=True).first()
    classes = get_classes_actives(etab, annee_active, user=request.user) if annee_active else []

    classe_actuelle_id = request.GET.get('classe_actuelle') or request.POST.get('classe_actuelle')
    annee_suivante_id  = request.GET.get('annee_suivante')  or request.POST.get('annee_suivante')
    etape = request.GET.get('etape', '1')  # 1=selection, 2=decisions, 3=recapitulatif

    classe_actuelle = None
    annee_suivante  = None
    eleves_data     = []

    if classe_actuelle_id and annee_suivante_id:
        classe_actuelle = get_object_or_404(Classe, pk=classe_actuelle_id, etablissement=etab)
        annee_suivante  = get_object_or_404(AnneeScolaire, pk=annee_suivante_id, etablissement=etab)
        classe_suivante_suggeree = _get_classe_suivante(classe_actuelle, annee_suivante)

        cycle_actuel = classe_actuelle.niveau.cycle if classe_actuelle.niveau else None
        note_passage = float(cycle_actuel.note_passage if cycle_actuel else 10)
        if cycle_actuel and cycle_actuel.is_premier_cycle and cycle_actuel.utilise_compositions_multiples and note_passage > 10:
            note_passage = note_passage / 2.0

        inscriptions = list(classe_actuelle.inscriptions.filter(
            annee=annee_active, is_active=True
        ).select_related('eleve'))
        eleves_inscrits = [i.eleve for i in inscriptions]
        deja_inscrits_ids = set(
            Inscription.objects.filter(
                eleve_id__in=[e.pk for e in eleves_inscrits], annee=annee_suivante
            ).values_list('eleve_id', flat=True)
        )
        moyennes_map = _calculer_moyennes_annuelles_classe(eleves_inscrits, classe_actuelle, annee_active)

        for insc in inscriptions:
            eleve = insc.eleve
            deja_inscrit = eleve.pk in deja_inscrits_ids
            moyenne = moyennes_map.get(eleve.pk)

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

                    if decision == 'admis':
                        if not classe_suivante_id:
                            raise ValueError("Veuillez sélectionner une classe de destination pour les élèves admis.")
                        classe_dest = get_object_or_404(Classe, pk=classe_suivante_id, etablissement=etab)
                        Inscription.objects.filter(
                            eleve=eleve, annee=annee_active
                        ).update(is_active=False)
                        Inscription.objects.create(
                            eleve=eleve, classe=classe_dest,
                            annee=annee_suivante, statut='actif', is_active=True
                        )
                        nb_admis += 1

                    elif decision == 'redouble':
                        classe_redouble = Classe.objects.filter(
                            etablissement=etab, annee=annee_suivante,
                            nom=classe_actuelle.nom, niveau=classe_actuelle.niveau
                        ).first()
                        if not classe_redouble:
                            classe_redouble = Classe.objects.create(
                                etablissement=etab, annee=annee_suivante,
                                niveau=classe_actuelle.niveau, nom=classe_actuelle.nom,
                                capacite_max=classe_actuelle.capacite_max,
                                salle=classe_actuelle.salle,
                                serie=classe_actuelle.serie,
                                division=classe_actuelle.division,
                                filiere=classe_actuelle.filiere,
                                semestre_actif=classe_actuelle.semestre_actif,
                            )
                        Inscription.objects.filter(
                            eleve=eleve, annee=annee_active
                        ).update(is_active=False)
                        Inscription.objects.create(
                            eleve=eleve, classe=classe_redouble,
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
                f" Passages traités : {nb_admis} admis, {nb_redouble} redoublant(s), {nb_exclus} exclu(s) — Année {annee_suivante.libelle}."
            )
            return redirect('assistant_fin_annee')

        except Exception as ex:
            messages.error(request, f"Erreur : {str(ex)}")

    # ── CLÔTURE ANNÉE ──────────────────────────────────────────────────────
    if request.method == 'POST' and request.POST.get('action') == 'cloturer_annee':
        if not request.user.is_admin:
            messages.error(request, "Seul l'administrateur de l'établissement peut clôturer l'année scolaire.")
            return redirect('assistant_fin_annee')
        annee_a_cloturer_id = request.POST.get('annee_a_cloturer')
        annee_a_activer_id  = request.POST.get('annee_a_activer')

        # Garde-fou CRITIQUE : ne jamais laisser l'établissement sans
        # aucune année active. Sans ça, tous les dashboards, listes de
        # classes et formulaires se vident silencieusement (aucune
        # erreur visible), rendant la plateforme inutilisable jusqu'à
        # ce qu'un administrateur comprenne le problème.
        if not annee_a_cloturer_id or not annee_a_activer_id:
            messages.error(
                request,
                " Vous devez sélectionner à la fois l'année à clôturer ET "
                "la nouvelle année à activer. Aucune des deux actions n'a été appliquée."
            )
            return redirect('assistant_fin_annee')

        if annee_a_cloturer_id == annee_a_activer_id:
            messages.error(
                request,
                " L'année à clôturer et la nouvelle année active ne peuvent pas être identiques."
            )
            return redirect('assistant_fin_annee')

        try:
            with transaction.atomic():
                AnneeScolaire.objects.filter(pk=annee_a_cloturer_id, etablissement=etab).update(is_active=False)
                AnneeScolaire.objects.filter(pk=annee_a_activer_id, etablissement=etab).update(is_active=True)

                # Vérification finale : s'assurer qu'il reste bien EXACTEMENT
                # une année active pour cet établissement après l'opération.
                nb_actives = AnneeScolaire.objects.filter(etablissement=etab, is_active=True).count()
                if nb_actives != 1:
                    raise ValueError(
                        f"Incohérence détectée : {nb_actives} année(s) active(s) "
                        f"après l'opération (1 attendue). Opération annulée."
                    )

            from django.core.cache import cache
            cache.delete(f"annee_active_{etab.pk}")
            messages.success(request, " Année clôturée et nouvelle année activée.")
        except Exception as ex:
            messages.error(request, f"Erreur clôture : {str(ex)}")
        return redirect('assistant_fin_annee')

    classe_suivante_suggeree = _get_classe_suivante(classe_actuelle, annee_suivante) if classe_actuelle else None

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

    toutes_classes_qs = Classe.objects.filter(etablissement=etab)
    if annee_suivante and toutes_classes_qs.filter(annee=annee_suivante).exists():
        toutes_classes_qs = toutes_classes_qs.filter(annee=annee_suivante)

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
        'toutes_classes': toutes_classes_qs.order_by('niveau__ordre', 'nom'),
    })
