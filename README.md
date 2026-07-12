# SmartSchool ERP

Application de gestion scolaire multi-établissements (ERP) robuste, sécurisée et performante.

## 🚀 Fonctionnalités Principales

- **Administration multi-établissements** : Gérez plusieurs écoles/lycées depuis une seule interface avec isolation stricte des données.
- **Gestion des Évaluations & Bulletins** : Saisie des notes, clôture de période, génération de bulletins ultra-rapide (O(1) sur le rendu) avec support des systèmes éducatifs maliens et universitaires.
- **Finances & Caisse** : Suivi des paiements, bourses, annulations avec traçabilité, alertes de retards de paiement, reçus au format PDF.
- **Espace Famille** : Portail dédié aux parents pour consulter les absences, notes, et soumettre des réclamations avec notification automatique.
- **Emplois du temps** : Création visuelle d'emplois du temps et prévention des chevauchements de cours (salles, classes, enseignants).

## 🛠 Prérequis

- Python 3.9+
- PostgreSQL (fortement recommandé en production)
- Wkhtmltopdf (requis pour la génération des bulletins/reçus au format PDF)

## 💻 Déploiement en Production

Pour déployer SmartSchool ERP de manière sécurisée en production, suivez ces instructions.

### 1. Variables d'environnement

En production (`DEBUG=False`), l'application nécessite que des variables soient définies dans l'environnement du serveur (ou via un fichier `.env` si vous utilisez des outils comme `python-dotenv` ou Docker).

Copiez le fichier d'exemple et renseignez-le :
```bash
cp .env.example .env
```
Assurez-vous de générer une clé secrète longue et unique, et de renseigner vos noms de domaines dans `ALLOWED_HOSTS`.

### 2. Base de données (PostgreSQL)

Ne pas utiliser SQLite en production. Modifiez `DATABASE_URL` :
```bash
DATABASE_URL=postgresql://user:password@localhost:5432/smartschool
```

### 3. Installation et Lancement (Serveur)

```bash
# Créer et activer un environnement virtuel
python -m venv venv
source venv/bin/activate

# Installer les dépendances
pip install -r requirements.txt

# Créer les tables et appliquer les migrations
python manage.py migrate

# Collecter les fichiers statiques (nécessaire pour WhiteNoise / Nginx)
python manage.py collectstatic --noinput

# Lancer Gunicorn (Recommandé)
gunicorn smartschool.wsgi:application --bind 0.0.0.0:8000 --workers 3
```

> Note sur les fichiers médias : Par défaut, l'application est configurée avec un fallback `django.views.static.serve` pour les fichiers médias afin qu'ils s'affichent sans configuration Nginx initiale (pratique pour Heroku / Cpanel basique). Toutefois, il est recommandé de servir `/media/` via un serveur Nginx.

## 🔐 Sécurité

Cette application force les redirections HTTPS et sécurise les cookies de sessions (CSRF, HSTS) automatiquement lorsque `DEBUG=False` est détecté dans les variables d'environnement. Ne changez jamais ces configurations en production.
