# Vulture whitelist for Django project
# This file contains patterns that vulture incorrectly identifies as unused code
# but are actually used by Django's framework conventions

# Django settings.py - All settings are read by Django
SECRET_KEY = ""
DEBUG = True
ALLOWED_HOSTS = []
INSTALLED_APPS = []
MIDDLEWARE = []
ROOT_URLCONF = ""
TEMPLATES = []
WSGI_APPLICATION = ""
DATABASES = {}
AUTH_PASSWORD_VALIDATORS = []
LANGUAGE_CODE = ""
TIME_ZONE = ""
USE_I18N = True
USE_TZ = True
STATIC_URL = ""
STATIC_ROOT = ""
STATICFILES_DIRS = []
STORAGES = {}
DEFAULT_AUTO_FIELD = ""
LOGGING = {}
EMAIL_BACKEND = ""
EMAIL_HOST = ""
EMAIL_PORT = 587
EMAIL_USE_TLS = True
EMAIL_USE_SSL = False
EMAIL_HOST_PASSWORD = ""
DEFAULT_FROM_EMAIL = ""

# Django WSGI/ASGI
application = None


# Django Admin - ModelAdmin attributes
class ModelAdmin:
    list_display = []
    list_filter = []
    search_fields = []
    readonly_fields = []
    fieldsets = []
    ordering = []
    date_hierarchy = ""
    inlines = []

    # Method attributes
    def method(self):
        pass

    method.short_description = ""


# Django Models - Meta class
class Meta:
    verbose_name = ""
    verbose_name_plural = ""
    ordering = []
    unique_together = []
    indexes = []


# Django Model fields (these are accessed via ORM, not directly)
class Model:
    created_at = None
    updated_at = None


# Django Forms - Meta class
class FormMeta:
    model = None
    fields = []
    widgets = {}
    labels = {}


# Django Views - Class-based view attributes
class View:
    model = None
    form_class = None
    context_object_name = ""
    paginate_by = 10
    ordering = []


# Django Management Commands
class Command:
    help = ""

    def add_arguments(self, parser):
        pass

    def handle(self, *args, **options):
        pass


# Django URLs
urlpatterns = []

# Django Migrations
dependencies = []
operations = []


# Django Apps
class AppConfig:
    default_auto_field = ""
    verbose_name = ""


# Django Middleware
class Middleware:
    def process_response(self, request, response):
        return response


# Django Template Tags - registered functions
def template_tag():
    pass


# Django Admin - model registration
class Admin:
    site_header = ""
    site_title = ""
    index_title = ""
