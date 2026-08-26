"""
SmartSchool ERP — Données de test : Compositions 1er Cycle Fondamental
======================================================================
Ce script ajoute des compositions /10 pour les élèves du 1er cycle
sans toucher aux autres données existantes.

Usage : python manage.py shell < setup_test_compositions.py
   ou : python setup_test_compositions.py (depuis la racine du projet)
"""
import os, sys, django, random
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'smartschool.settings')
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
django.setup()

from decimal import Decimal
from etablissements.models import Etablissement, AnneeScolaire, Cycle
from eleves.models import Eleve, Inscription
from notes.models import Matiere, Composition
from accounts.models import User

print("=" * 60)
print("  SmartSchool — Test Compositions 1er Cycle /10")
print("=" * 60)

# ── 1. Récupérer l'établissement et l'année active ──────────────
etab = Etablissement.objects.first()
if not etab:
    print("❌ Aucun établissement trouvé. Lance setup_demo.py d'abord.")
    sys.exit(1)

annee = AnneeScolaire.objects.filter(etablissement=etab, is_active=True).first()
if not annee:
    print("❌ Aucune année scolaire active trouvée.")
    sys.exit(1)

print(f"\n✅ Établissement : {etab.nom}")
print(f"✅ Année active  : {annee.libelle}")

# ── 2. Vérifier le cycle 1er cycle ──────────────────────────────
cycle = Cycle.objects.filter(etablissement=etab, type_cycle='premier_cycle').first()
if not cycle:
    print("❌ Aucun cycle 'premier_cycle' trouvé.")
    sys.exit(1)

# S'assurer que nb_compositions_trimestre >= 2
if cycle.nb_compositions_trimestre < 2:
    cycle.nb_compositions_trimestre = 3
    cycle.note_passage = Decimal('5')
    cycle.note_max = Decimal('10')
    cycle.save()
    print(f"⚙️  Cycle mis à jour : {cycle.nb_compositions_trimestre} compositions, note_max=10, passage=5")
else:
    print(f"✅ Cycle 1er cycle  : {cycle.nb_compositions_trimestre} compositions/trimestre")

nb_compos = cycle.nb_compositions_trimestre

# ── 3. Récupérer les matières du 1er cycle (hors conduite) ──────
from etablissements.models import MatiereCycle
matieres_cycle = list(
    MatiereCycle.objects.filter(cycle=cycle)
    .select_related('matiere')
    .exclude(matiere__is_conduite=True)
    .values_list('matiere', flat=True)
)
matieres = list(Matiere.objects.filter(pk__in=matieres_cycle, etablissement=etab))

if not matieres:
    # Fallback : toutes les matières de l'étab hors conduite
    matieres = list(Matiere.objects.filter(etablissement=etab, is_conduite=False))

if not matieres:
    print("❌ Aucune matière disponible.")
    sys.exit(1)

print(f"✅ Matières        : {len(matieres)} ({', '.join(m.nom for m in matieres[:5])}{'...' if len(matieres) > 5 else ''})")

# ── 4. Récupérer les inscriptions du 1er cycle ──────────────────
inscriptions_1er = []
for insc in Inscription.objects.filter(
    eleve__etablissement=etab, annee=annee, is_active=True
).select_related('eleve', 'classe__niveau__cycle'):
    if (insc.classe.niveau and
        insc.classe.niveau.cycle and
        insc.classe.niveau.cycle.type_cycle == 'premier_cycle'):
        inscriptions_1er.append(insc)

if not inscriptions_1er:
    print("❌ Aucun élève inscrit en 1er cycle pour cette année.")
    sys.exit(1)

print(f"✅ Élèves 1er cycle : {len(inscriptions_1er)}")

# ── 5. Nettoyage des anciennes compositions de test ─────────────
deleted, _ = Composition.objects.filter(
    eleve__etablissement=etab, annee=annee
).delete()
print(f"\n🧹 Compositions existantes supprimées : {deleted}")

# ── 6. Créer les compositions ────────────────────────────────────
directeur = User.objects.filter(etablissement=etab, role='directeur').first() \
            or User.objects.filter(etablissement=etab).first()

created = 0
random.seed(42)  # Reproductible

# Profils de notes pour simuler la variété
def note_aleatoire(profil='moyen'):
    if profil == 'excellent':
        return round(random.uniform(8.0, 10.0), 2)
    elif profil == 'bien':
        return round(random.uniform(6.5, 8.5), 2)
    elif profil == 'moyen':
        return round(random.uniform(4.5, 7.5), 2)
    elif profil == 'faible':
        return round(random.uniform(2.0, 5.5), 2)
    else:  # absent
        return None

profils = ['excellent', 'bien', 'bien', 'moyen', 'moyen', 'moyen', 'faible']

print(f"\n[6/6] Génération des compositions ({nb_compos} par élève × {len(matieres)} matières)...")

for insc in inscriptions_1er:
    eleve = insc.eleve
    profil = random.choice(profils)

    for numero in range(1, nb_compos + 1):
        for mat in matieres:
            note_val = note_aleatoire(profil)
            # Légère variation par composition
            if note_val is not None:
                variation = random.uniform(-0.5, 0.5)
                note_val = max(0, min(10, round(note_val + variation, 2)))

            Composition.objects.create(
                eleve=eleve,
                matiere=mat,
                classe=insc.classe,
                annee=annee,
                numero=numero,
                note=Decimal(str(note_val)) if note_val is not None else None,
                note_max=Decimal('10'),
                saisi_par=directeur,
            )
            created += 1

print(f"\n{'='*60}")
print(f"✅ Compositions créées : {created}")
print(f"   → {len(inscriptions_1er)} élèves × {nb_compos} compositions × {len(matieres)} matières")
print(f"\n📋 Résumé par élève :")
for insc in inscriptions_1er[:5]:
    compos = Composition.objects.filter(eleve=insc.eleve, annee=annee)
    notes = [c.note for c in compos if c.note is not None]
    moy = round(sum(float(n) for n in notes) / len(notes), 2) if notes else 0
    print(f"   {insc.eleve.nom} {insc.eleve.prenom} — {insc.classe.nom} — moy brute: {moy}/10")

if len(inscriptions_1er) > 5:
    print(f"   ... et {len(inscriptions_1er) - 5} autres élèves")

print(f"\n🔗 Tester sur :")
print(f"   /notes/bulletin-composition/<eleve_pk>/<annee_pk>/1/")
print(f"   Année PK = {annee.pk}")
print(f"   Exemple élève PK = {inscriptions_1er[0].eleve.pk}")
print(f"   → /notes/bulletin-composition/{inscriptions_1er[0].eleve.pk}/{annee.pk}/1/")
print("=" * 60)
