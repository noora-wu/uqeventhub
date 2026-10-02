from django.dispatch import receiver
from allauth.account.signals import user_signed_up
from allauth.socialaccount.signals import social_account_added

from .models import AppUser


def _sync_app_user(user):
    if not user or not user.email:
        return
    username = user.username or user.email.split("@")[0]
    AppUser.objects.update_or_create(
        email=user.email.lower(),
        defaults={
            "username": username,
            "is_active": user.is_active,
            "is_superuser": user.is_superuser,
        },
    )


@receiver(user_signed_up)
def sync_after_signup(request, user, **kwargs):
    _sync_app_user(user)


@receiver(social_account_added)
def sync_after_social_add(request, sociallogin, **kwargs):
    _sync_app_user(sociallogin.user)

