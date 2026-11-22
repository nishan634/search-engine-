import logging
import os

from celery import shared_task

from apps.knowledge.services import index_item

from .extraction import ExtractionError, extract_text
from .models import Document

log = logging.getLogger(__name__)
MAX_TEXT_CHARS = 3_000_000  # keeps indexing time and storage bounded


@shared_task
def process_document_task(document_id):
    doc = Document.objects.select_related("item").filter(id=document_id).first()
    if not doc:
        return
    item = doc.item
    try:
        with doc.file.open("rb") as fh:
            data = fh.read()
        text = extract_text(data, os.path.splitext(doc.original_name)[1].lower())[:MAX_TEXT_CHARS]
        if not text.strip():
            raise ExtractionError("No extractable text (scanned PDFs need OCR).")
    except ExtractionError as e:
        item.status, item.error = "failed", str(e)[:300]
        item.save(update_fields=["status", "error", "updated_at"])
        return
    item.content, item.status, item.error = text, "ready", ""
    item.save(update_fields=["content", "status", "error", "updated_at"])
    index_item(item)
