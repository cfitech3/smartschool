"""
Paramètres Django — SmartSchool ERP
====================================
Toutes les valeurs sensibles proviennent de variables d'environnement.
En développement, créez un fichier .env à la racine du projet.
En production, définissez ces variables dans votre environnement système.

Variables requises en production (DEBUG=False) :
  SECRET_KEY          Clé secrète Django (min. 50 caractères)
  ALLOWED_HOSTS       Hostnames séparés par des virgules (ex: monecole.ml,www.monecole.ml)
  DATABASE_URL        (optionnel) URL PostgreSQL — ex: postgresql://user:pass@host:5432/dbname
                      Si absente, SQLite est utilisé (dev uniquement, non recommandé en prod)
"""
import os
from pathlib import Path
from django.core.exceptions import ImproperlyConfigured

BASE_DIR = Path(__file__).resolve().parent.parent

# ── Environnement : production ou développement ──────────────────────────────
DEBUG = os.environ.get('DEBUG', 'True') == 'True'


def _get_env(var_name, default=None, required_in_prod=False):
    """
    Lit une variable d'environnement.
    Si required_in_prod=True et que DEBUG=False, lève ImproperlyConfigured
    plutôt que d'utiliser la valeur par défaut.
    """
    value = os.environ.get(var_name, default)
    if not DEBUG and required_in_prod and not value:
        raise ImproperlyConfigured(
            f"La variable d'environnement '{var_name}' est obligatoire en production "
            f"(DEBUG=False). Définissez-la dans votre environnement ou fichier .env."
        )
    return value


# ── Clé secrète ──────────────────────────────────────────────────────────────
# En développement, une valeur par défaut est acceptable.
# En production (DEBUG=False), la clé DOIT être définie dans l'environnement.
SECRET_KEY = _get_env(
    'SECRET_KEY',
    default='django-smartschool-dev-key-insecure-ne-pas-utiliser-en-production',
    required_in_prod=True,
)

# ── Hôtes autorisés ──────────────────────────────────────────────────────────
# En développement, '*' est acceptable.
# En production, definir ALLOWED_HOSTS avec les vrais noms de domaine.
_allowed_hosts_env = os.environ.get('ALLOWED_HOSTS', '')
if _allowed_hosts_env:
    ALLOWED_HOSTS = [h.strip() for h in _allowed_hosts_env.split(',') if h.strip()]
    # Toujours autoriser PythonAnywhere
    if 'cfitech2.pythonanywhere.com' not in ALLOWED_HOSTS:
        ALLOWED_HOSTS.append('cfitech2.pythonanywhere.com')
elif DEBUG:
    # Développement local : accepte localhost et 127.0.0.1
    ALLOWED_HOSTS = ['localhost', '127.0.0.1', '0.0.0.0']
else:
    raise ImproperlyConfigured(
        "La variable d'environnement 'ALLOWED_HOSTS' est obligatoire en production. "
        "Exemple : ALLOWED_HOSTS=monecole.ml,www.monecole.ml"
    )

# ── Applications installées ───────────────────────────────────────────────────
INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'crispy_forms',
    'crispy_bootstrap5',
    'accounts',
    'core',
    'etablissements',
    'eleves',
    'finances',
    'notes',
]

# ── Middleware ────────────────────────────────────────────────────────────────
MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    'core.middleware.EtablissementMiddleware',
]

ROOT_URLCONF = 'smartschool.urls'
TEMPLATES = [{
    'BACKEND': 'django.template.backends.django.DjangoTemplates',
    'DIRS': [BASE_DIR / 'templates'],
    'APP_DIRS': True,
    'OPTIONS': {'context_processors': [
        'django.template.context_processors.debug',
        'django.template.context_processors.request',
        'django.contrib.auth.context_processors.auth',
        'django.contrib.messages.context_processors.messages',
        'core.context_processors.global_context',
    ]},
}]

WSGI_APPLICATION = 'smartschool.wsgi.application'

# ── Base de données ───────────────────────────────────────────────────────────
# PostgreSQL est recommandé en production.
# Définir DATABASE_URL pour utiliser PostgreSQL.
# Format : postgresql://utilisateur:motdepasse@hote:5432/nom_base
#
# Si DATABASE_URL est absent, SQLite est utilisé comme fallback (développement uniquement).
_database_url = os.environ.get('DATABASE_URL', '')

if _database_url:
    # Parsing manuel de l'URL PostgreSQL pour ne pas dépendre de dj-database-url
    # Format attendu : postgresql://user:password@host:port/dbname
    import re
    _db_match = re.match(
        r'^postgresql://(?P<user>[^:]+):(?P<password>[^@]+)@(?P<host>[^:/]+):?(?P<port>\d+)?/(?P<name>.+)$',
        _database_url
    )
    if _db_match:
        _db = _db_match.groupdict()
        DATABASES = {
            'default': {
                'ENGINE': 'django.db.backends.postgresql',
                'NAME': _db['name'],
                'USER': _db['user'],
                'PASSWORD': _db['password'],
                'HOST': _db['host'],
                'PORT': _db.get('port') or '5432',
                'CONN_MAX_AGE': 60,  # Connexions persistantes (perf)
                'OPTIONS': {
                    'connect_timeout': 10,
                },
            }
        }
    else:
        raise ImproperlyConfigured(
            f"Le format de DATABASE_URL est invalide. "
            f"Format attendu : postgresql://utilisateur:motdepasse@hote:5432/nom_base"
        )
else:
    # SQLite en fallback — uniquement acceptable en développement
    if not DEBUG:
        import warnings
        warnings.warn(
            "⚠️  AVERTISSEMENT : Aucune DATABASE_URL définie en production. "
            "SQLite est utilisé, ce qui n'est pas recommandé pour un déploiement multi-utilisateurs. "
            "Définissez DATABASE_URL avec une URL PostgreSQL.",
            RuntimeWarning,
            stacklevel=2,
        )
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.sqlite3',
            'NAME': BASE_DIR / 'smartschool.db',
            'OPTIONS': {
                'timeout': 20,  # attend 20s avant "database is locked"
            },
        }
    }

# ── Authentification ──────────────────────────────────────────────────────────
AUTH_USER_MODEL = 'accounts.User'
LOGIN_URL = '/auth/login/'
LOGIN_REDIRECT_URL = '/dashboard/'
LOGOUT_REDIRECT_URL = '/auth/login/'
AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
        'OPTIONS': {'min_length': 8},
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
]

# ── Internationalisation ──────────────────────────────────────────────────────
LANGUAGE_CODE = 'fr-fr'
TIME_ZONE = 'Africa/Bamako'
USE_I18N = True
USE_TZ = True

# ── Fichiers statiques & médias ───────────────────────────────────────────────
STATIC_URL = '/static/'
STATICFILES_DIRS = [BASE_DIR / 'static']
STATIC_ROOT = BASE_DIR / 'staticfiles'
STATICFILES_STORAGE = 'whitenoise.storage.CompressedManifestStaticFilesStorage'
MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'

# ── Divers ────────────────────────────────────────────────────────────────────
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'
CRISPY_ALLOWED_TEMPLATE_PACKS = "bootstrap5"
CRISPY_TEMPLATE_PACK = "bootstrap5"
# SessionStorage est plus sûr que CookieStorage : les messages ne sont pas
# exposés ni manipulables côté client.
MESSAGE_STORAGE = 'django.contrib.messages.storage.session.SessionStorage'
# ── Cache ─────────────────────────────────────────────────────────────────────
# ARCH-002 : LocMemCache n'est pas partagé entre workers Gunicorn.
# En production multi-workers, définir CACHE_BACKEND=redis ou CACHE_BACKEND=file.
#
# CACHE_BACKEND=redis  → Redis (production recommandée, nécessite REDIS_URL)
#                         ex: REDIS_URL=redis://127.0.0.1:6379/0
# CACHE_BACKEND=file   → Fichier local (PythonAnywhere, mono-worker)
# CACHE_BACKEND=locmem → Mémoire locale (développement uniquement, défaut)

_cache_backend = os.environ.get('CACHE_BACKEND', 'locmem').lower()

if _cache_backend == 'redis':
    _redis_url = os.environ.get('REDIS_URL', 'redis://127.0.0.1:6379/0')
    CACHES = {
        'default': {
            'BACKEND': 'django.core.cache.backends.redis.RedisCache',
            'LOCATION': _redis_url,
            'TIMEOUT': 300,
            'OPTIONS': {
                'socket_connect_timeout': 5,
                'socket_timeout': 5,
            },
        }
    }
elif _cache_backend == 'file':
    CACHES = {
        'default': {
            'BACKEND': 'django.core.cache.backends.filebased.FileBasedCache',
            'LOCATION': os.environ.get('CACHE_FILE_PATH', BASE_DIR / '.cache' / 'smartschool'),
            'TIMEOUT': 300,
        }
    }
else:
    # locmem : uniquement pour développement local (défaut)
    if not DEBUG and _cache_backend == 'locmem':
        import warnings
        warnings.warn(
            "⚠️  CACHE LocMemCache utilisé en production. "
            "Les caches ne sont pas partagés entre workers Gunicorn. "
            "Définissez CACHE_BACKEND=redis ou CACHE_BACKEND=file.",
            RuntimeWarning,
            stacklevel=2,
        )
    CACHES = {
        'default': {
            'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
            'TIMEOUT': 300,
        }
    }


# ── Sécurité renforcée en production (DEBUG=False) ────────────────────────────
if not DEBUG:
    # Forcer HTTPS
    SECURE_SSL_REDIRECT = True
    SECURE_HSTS_SECONDS = 31536000       # 1 an
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_HSTS_PRELOAD = True

    # Cookies sécurisés (HTTPS uniquement)
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True

    # Protection contre le clickjacking
    X_FRAME_OPTIONS = 'DENY'

    # Empêcher le sniffing de type MIME
    SECURE_CONTENT_TYPE_NOSNIFF = True

    # Activer le filtre XSS du navigateur
    SECURE_BROWSER_XSS_FILTER = True

