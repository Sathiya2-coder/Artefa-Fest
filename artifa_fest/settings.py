import os
from pathlib import Path
import logging
try:
    import dj_database_url
except ImportError:
    dj_database_url = None


BASE_DIR = Path(__file__).resolve().parent.parent

SECRET_KEY = 'django-insecure-your-secret-key-here'

DEBUG = True

ALLOWED_HOSTS = ['127.0.0.1', 'localhost', 'testserver', '.trycloudflare.com', '.vercel.app', '*']

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'core.apps.CoreConfig',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    # 'core.middleware.ErrorLogMiddleware',
]

ROOT_URLCONF = 'artifa_fest.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [os.path.join(BASE_DIR, 'templates')],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'artifa_fest.wsgi.application'

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': os.path.join(BASE_DIR, 'db.sqlite3'),
    }
}

if dj_database_url:
    # Use dj_database_url if available (production/vercel)
    db_from_env = dj_database_url.config(conn_max_age=600)
    if db_from_env and 'ENGINE' in db_from_env:
        DATABASES['default'] = db_from_env
    
    # Handle Custom Prefixes (e.g., NEON_URL, PRODUCTION_URL, etc.)
    for key, value in os.environ.items():
        if key.endswith('_URL') and value.startswith(('postgres://', 'postgresql://')):
            DATABASES['default'] = dj_database_url.parse(value)
            break
else:
    # Print a warning locally if dj_database_url is missing
    print("Warning: dj_database_url not found, falling back to local SQLite.")


AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]
# Consolidated ALLOWED_HOSTS above

CSRF_TRUSTED_ORIGINS = [
    "https://*.trycloudflare.com",
    "https://*.vercel.app",
]

SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')

LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'UTC'
USE_I18N = True
USE_TZ = True

STATIC_URL = 'static/'
STATICFILES_DIRS = [os.path.join(BASE_DIR, 'static')]
STATIC_ROOT = os.path.join(BASE_DIR, 'staticfiles')
STATICFILES_STORAGE = 'whitenoise.storage.CompressedStaticFilesStorage'
WHITENOISE_MANIFEST_STRICT = False

MEDIA_URL = '/media/'
MEDIA_ROOT = os.path.join(BASE_DIR, 'media')

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# Email Configuration
EMAIL_BACKEND = 'django.core.mail.backends.console.EmailBackend'
DEFAULT_FROM_EMAIL = 'noreply@artifafest.edu'
# For production, use:
# EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
# EMAIL_HOST = 'your-email-host.com'
# EMAIL_PORT = 587
# EMAIL_USE_TLS = True
# EMAIL_HOST_USER = 'your-email@example.com'
# EMAIL_HOST_PASSWORD = 'your-password'

# Email Configuration (Gmail)
EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
EMAIL_HOST = 'smtp.gmail.com'
EMAIL_PORT = 587
EMAIL_USE_TLS = True
EMAIL_HOST_USER = 'manomarisamy2@gmail.com'  # Change this to your Gmail address
EMAIL_HOST_PASSWORD = 'ksto sbkl cvzi vrat'  # Use Gmail App Password (not regular password)
DEFAULT_FROM_EMAIL = 'manomarisamy2@gmail.com'

# Django Messages Configuration for Bootstrap alerts
from django.contrib.messages import constants as message_constants
MESSAGE_TAGS = {
    message_constants.DEBUG: 'debug',
    message_constants.INFO: 'info',
    message_constants.SUCCESS: 'success',
    message_constants.WARNING: 'warning',
    message_constants.ERROR: 'danger',  # Bootstrap uses 'danger' instead of 'error'
}

# Session Configuration
SESSION_ENGINE = 'django.contrib.sessions.backends.db'
SESSION_COOKIE_AGE = 86400 * 7  # 7 days in seconds
SESSION_COOKIE_HTTPONLY = True  # Only accessible via HTTP, not JavaScript
SESSION_COOKIE_SECURE = False  # Set to True in production with HTTPS
SESSION_SAVE_EVERY_REQUEST = True  # Save session on every request
SESSION_EXPIRE_AT_BROWSER_CLOSE = False  # Keep session after browser closes

# Logging Configuration
# On Vercel, we only use console logging
IS_VERCEL = 'VERCEL' in os.environ

# Logging Configuration
IS_VERCEL = 'VERCEL' in os.environ

if IS_VERCEL:
    # Minimal logging for Vercel to avoid startup crashes
    LOGGING = {
        'version': 1,
        'disable_existing_loggers': False,
        'handlers': {
            'console': {
                'class': 'logging.StreamHandler',
            },
        },
        'root': {
            'handlers': ['console'],
            'level': 'DEBUG',
        },
    }
else:
    LOGS_DIR = os.path.join(BASE_DIR, 'logs')
    os.makedirs(LOGS_DIR, exist_ok=True)
    LOGGING = {
        'version': 1,
        'disable_existing_loggers': False,
        'formatters': {
            'verbose': {
                'format': '{levelname} {asctime} {module} {process:d} {message}',
                'style': '{',
            },
        },
        'handlers': {
            'console': {
                'level': 'DEBUG',
                'class': 'logging.StreamHandler',
            },
            'file': {
                'level': 'DEBUG',
                'class': 'logging.handlers.RotatingFileHandler',
                'filename': os.path.join(LOGS_DIR, 'app.log'),
                'maxBytes': 1024 * 1024 * 5,
                'backupCount': 5,
                'formatter': 'verbose',
            },
        },
        'loggers': {
            'django': {
                'handlers': ['console', 'file'],
                'level': 'INFO',
                'propagate': True,
            },
            'core': {
                'handlers': ['console', 'file'],
                'level': 'DEBUG',
                'propagate': True,
            },
        },
    }
