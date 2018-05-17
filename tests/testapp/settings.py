import logging
import os


DEBUG = True

DATABASES = {"default": {"ENGINE": "django.db.backends.sqlite3", "NAME": "imagefield"}}

INSTALLED_APPS = [
    "django.contrib.auth",
    "django.contrib.admin",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.staticfiles",
    "django.contrib.messages",
    "testapp",
    # Libraries
    "imagefield",
]

STATIC_URL = "/static/"
BASEDIR = os.path.dirname(__file__)
MEDIA_ROOT = os.path.join(BASEDIR, "media/")
STATIC_ROOT = os.path.join(BASEDIR, "static/")
MEDIA_URL = "/media/"
STATIC_URL = "/static/"
SECRET_KEY = "supersikret"
LOGIN_REDIRECT_URL = "/?login=1"

ROOT_URLCONF = "testapp.urls"
LANGUAGES = (("en", "English"), ("de", "German"))

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ]
        },
    }
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.locale.LocaleMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]


if os.environ.get("LOG"):
    logger = logging.getLogger("imagefield")
    logger.addHandler(logging.StreamHandler())
    logger.setLevel(logging.DEBUG)
