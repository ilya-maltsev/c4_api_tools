from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from django.conf import settings


class Command(BaseCommand):
    help = 'Create or update admin user from environment variables'

    def handle(self, *args, **options):
        username = settings.DASHBOARD_ADMIN_USER
        password = settings.DASHBOARD_ADMIN_PASSWORD

        user, created = User.objects.get_or_create(
            username=username,
            defaults={'is_staff': True, 'is_superuser': True},
        )

        user.set_password(password)
        user.is_staff = True
        user.is_superuser = True
        user.save()

        if created:
            self.stdout.write(f'Admin user "{username}" created.')
        else:
            self.stdout.write(f'Admin user "{username}" password updated.')
