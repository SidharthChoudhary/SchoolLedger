from django.db.models.signals import post_save
from django.dispatch import receiver
from django.contrib.auth.models import User
from .models import UserProfile


@receiver(post_save, sender=User)
def create_user_profile(sender, instance, created, **kwargs):
    """Create a UserProfile whenever a User is created"""
    if created:
        UserProfile.objects.create(
            user=instance,
            full_name=instance.get_full_name() or instance.username
        )


@receiver(post_save, sender=User)
def save_user_profile(sender, instance, **kwargs):
    """Save the UserProfile whenever the User is updated"""
    try:
        instance.profile.save()
    except UserProfile.DoesNotExist:
        # In case profile doesn't exist, create it
        UserProfile.objects.create(
            user=instance,
            full_name=instance.get_full_name() or instance.username
        )
