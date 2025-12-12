from pathlib import Path
import os
import dj_database_url
from decouple import config
from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent

# --- SEGURIDAD ---
SECRET_KEY = config('SECRET_KEY', default='fallback-secret-key-only-for-local')
DEBUG = True



# ✅ Cambia por tu dominio Render (lo obtendrás al desplegar)
ALLOWED_HOSTS = [
    'ede-evento.com',
    'www.ede-evento.com',
    'proyecto-entradas-excel-1.onrender.com',
    'localhost',
    '127.0.0.1',
]

# Para CSRF (Render requiere esto)
CSRF_TRUSTED_ORIGINS = [
    "https://proyecto-entradas-excel-1.onrender.com",
]

# --- TWILIO / WHAPI / IMGBB ---
TWILIO_ACCOUNT_SID = config("TWILIO_ACCOUNT_SID", default="")
TWILIO_AUTH_TOKEN = config("TWILIO_AUTH_TOKEN", default="")
TWILIO_WHATSAPP_NUMBER = config("TWILIO_WHATSAPP_NUMBER", default="")
WHAPI_TOKEN = config("WHAPI_TOKEN", default="")
IMGBB_API_KEY = config("IMGBB_API_KEY", default="")
TWILIO_PHONE_NUMBER = config("TWILIO_PHONE_NUMBER", default="")
BASE_URL = "https://proyecto-entradas-excel-1.onrender.com"

# --- APLICACIONES ---
INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'cliente',
]

# --- MIDDLEWARE ---
MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'webcliente.urls'

# --- TEMPLATES ---
TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'webcliente.wsgi.application'

# --- BASE DE DATOS ---
DATABASES = {
    'default': dj_database_url.config(
        default=config('DATABASE_URL', default=f"sqlite:///{BASE_DIR / 'db.sqlite3'}"),
        conn_max_age=600,
    )
}

# --- CONTRASEÑAS ---
AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

# --- INTERNACIONALIZACIÓN ---
LANGUAGE_CODE = 'es'
TIME_ZONE = 'America/Lima'
USE_I18N = True
USE_TZ = True

# --- ARCHIVOS ESTÁTICOS ---
STATIC_URL = '/static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'
STATICFILES_STORAGE = 'whitenoise.storage.CompressedManifestStaticFilesStorage'

# --- MEDIA ---
MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'

 
# --- EMAIL ---
EMAIL_BACKEND = "django.core.mail.backends.smtp.EmailBackend"
EMAIL_HOST = "smtp.gmail.com"
EMAIL_PORT = 587
EMAIL_USE_TLS = True
EMAIL_HOST_USER = config('EMAIL_HOST_USER1')
EMAIL_HOST_PASSWORD = config('EMAIL_HOST_PASSWORD1')
DEFAULT_FROM_EMAIL = config("DEFAULT_FROM_EMAIL1")

# --- LOGIN ---
LOGIN_REDIRECT_URL = '/participantes/'

# --- CONFIG GENERAL ---
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'
