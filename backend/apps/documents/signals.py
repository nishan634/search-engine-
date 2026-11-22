from django.db.models.signals import post_delete
from django.dispatch import receiver

from .models import Document


@receiver(post_delete, sender=Document)
def delete_file_with_document(sender, instance, **kwargs):
    instance.file.delete(save=False)
