import os
from django.apps import AppConfig


class DashboardConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'dashboard'

    def ready(self):
        # Only start scheduler in the main process (not in manage.py commands)
        if os.environ.get('RUN_MAIN') == 'true' or not os.environ.get('DJANGO_DEBUG'):
            from . import cleanup_scheduler
            cleanup_scheduler.start_scheduler()
