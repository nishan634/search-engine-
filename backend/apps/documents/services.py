from django.db import transaction

from apps.knowledge.models import KnowledgeItem
from apps.knowledge.services import attach_organization

from .models import Document
from .tasks import process_document_task
from .validators import validate_upload


def upload_document(owner, f, title="", collection_ids=None, tag_names=None):
    name, ext, ctype, digest = validate_upload(f)
    with transaction.atomic():
        item = KnowledgeItem.objects.create(owner=owner, kind="document", title=title or name, status="pending")
        doc = Document.objects.create(owner=owner, item=item, file=f, original_name=name,
                                      content_type=ctype, size=f.size, sha256=digest)
        attach_organization(item, collection_ids, tag_names)
    process_document_task.delay(doc.id)
    item.refresh_from_db()
    return item
