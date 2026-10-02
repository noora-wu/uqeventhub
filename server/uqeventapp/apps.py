from django.apps import AppConfig


class UqeventappConfig(AppConfig):
    name = 'uqeventapp'

    def ready(self):
        from . import signals  # noqa: F401
