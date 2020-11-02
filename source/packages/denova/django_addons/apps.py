try:
    from django.apps import AppConfig
except ModuleNotFoundError:
    import sys
    sys.exit('Django required')

class DjangoExtraConfig(AppConfig):
    name = 'django_addons'
