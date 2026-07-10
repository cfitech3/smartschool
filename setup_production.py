"""
SmartSchool — Script d'initialisation PRODUCTION
À lancer UNE SEULE FOIS après les migrations sur PythonAnywhere.

Usage :
    python setup_production.py

Ce script crée :
  1. Le compte Super Administrateur
  2. Les 4 cycles scolaires maliens
  3. Les séries du lycée
  4. Les modèles de documents par défaut

Il ne crée PAS de données de démo (élèves, notes, paiements...).
"""
import os, sys, django, getpass

# ── Configuration ──────────────────────────────────────────────
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'smartschool.settings')
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
django.setup()

from accounts.models import User
from etablissements.models import Cycle, SerieLycee

print("=" * 55)
print("  SmartSchool — Initialisation Production")
print("=" * 55)

# ── 1. COMPTE SUPER ADMINISTRATEUR ─────────────────────────────
print("\n[1/3] Création du compte Super Administrateur\n")

# Vérifier si un superadmin existe déjà
if User.objects.filter(role='super_admin').exists():
    existing = User.objects.filter(role='super_admin').first()
    print(f"  ⚠️  Un Super Admin existe déjà : '{existing.username}'")
    reponse = input("  Voulez-vous en créer un autre ? (o/N) : ").strip().lower()
    if reponse != 'o':
        print("  → Création ignorée.")
        superadmin = existing
    else:
        superadmin = None
else:
    superadmin = None

if superadmin is None:
    print("  Entrez les informations du Super Administrateur :")

    while True:
        username = input("  Identifiant (username) : ").strip()
        if not username:
            print("  ❌ L'identifiant ne peut pas être vide.")
            continue
        if User.objects.filter(username=username).exists():
            print(f"  ❌ L'identifiant '{username}' est déjà utilisé.")
            continue
        break

    prenom = input("  Prénom : ").strip() or "Super"
    nom    = input("  Nom    : ").strip() or "Admin"
    email  = input("  Email  : ").strip() or ""

    while True:
        mdp = getpass.getpass("  Mot de passe (invisible) : ")
        if len(mdp) < 8:
            print("  ❌ Minimum 8 caractères.")
            continue
        mdp2 = getpass.getpass("  Confirmer le mot de passe : ")
        if mdp != mdp2:
            print("  ❌ Les mots de passe ne correspondent pas.")
            continue
        break

    superadmin = User.objects.create_superuser(
        username=username,
        email=email,
        password=mdp,
    )
    superadmin.role       = 'super_admin'
    superadmin.first_name = prenom
    superadmin.last_name  = nom
    superadmin.save()

    print(f"\n  ✅ Super Admin créé : {prenom} {nom} (@{username})")

# ── 2. CYCLES SCOLAIRES MALIENS ────────────────────────────────
print("\n[2/3] Cycles scolaires maliens\n")

cycles_config = [
    ('premier_cycle', '1er Cycle Fondamental',     'compo',  10, 'Certificat de Fin de 1er Cycle', 1),
    ('second_cycle',  '2ème Cycle Fondamental',    'compo',  10, 'DEF (Diplôme d\'Études Fondamentales)', 2),
    ('lycee',         'Lycée',                     'direct', 10, 'Baccalauréat', 3),
    ('universite',    'Université',                'credit', 10, 'Licence / Master / Doctorat', 4),
]

for type_c, nom, mode, seuil, diplome, ordre in cycles_config:
    # Chercher un établissement existant
    from etablissements.models import Etablissement
    etab = Etablissement.objects.first()
    if not etab:
        print(f"  ⚠️  Aucun établissement trouvé — les cycles seront créés à la création du 1er établissement.")
        break

    cycle, created = Cycle.objects.get_or_create(
        etablissement=etab,
        type_cycle=type_c,
        defaults={
            'nom': nom, 'mode_calcul': mode,
            'note_passage': seuil, 'diplome_prepare': diplome, 'ordre': ordre,
        }
    )
    sym = '✅ Créé' if created else '→ Existait'
    print(f"  {sym} : {nom}")

# Séries lycée
lycee = Cycle.objects.filter(type_cycle='lycee').first()
if lycee:
    series = [
        ('A', 'Lettres et Sciences Humaines', 1),
        ('B', 'Sciences Économiques et Sociales', 2),
        ('C', 'Mathématiques et Physique', 3),
        ('D', 'Sciences de la Nature et de la Vie', 4),
        ('T', 'Technique', 5),
    ]
    for code, nom_s, ordre_s in series:
        _, created = SerieLycee.objects.get_or_create(
            cycle=lycee, code=code,
            defaults={'nom': nom_s, 'ordre': ordre_s}
        )
    print(f"  ✅ 5 séries lycée (A, B, C, D, T)")

# ── 3. RÉSUMÉ ──────────────────────────────────────────────────
print("\n[3/3] Résumé\n")
print(f"  Super Admin   : {superadmin.first_name} {superadmin.last_name} (@{superadmin.username})")
print(f"  Cycles        : {Cycle.objects.count()} cycles")
print(f"  Séries lycée  : {SerieLycee.objects.count()} séries")

print("""
╔══════════════════════════════════════════════════════╗
║  PROCHAINES ÉTAPES                                   ║
║                                                      ║
║  1. Connectez-vous sur votre site avec :             ║
║     → Identifiant : votre username                   ║
║     → Mot de passe : celui que vous venez de saisir  ║
║                                                      ║
║  2. Allez dans Paramètres → Créer votre établissement║
║                                                      ║
║  3. Créez les utilisateurs (directeurs, comptables,  ║
║     enseignants...) depuis Utilisateurs              ║
║                                                      ║
║  4. Créez les classes et inscrivez les élèves        ║
╚══════════════════════════════════════════════════════╝
""")
