import logging
from urllib.parse import urlparse

from celery import shared_task

from .fetch import FetchError, fetch_page
from .models import KnowledgeItem
from .services import index_item

log = logging.getLogger(__name__)


@shared_task
def index_item_task(item_id):
    item = KnowledgeItem.objects.filter(id=item_id).first()
    if item:
        index_item(item)


@shared_task
def fetch_url_task(item_id):
    item = KnowledgeItem.objects.filter(id=item_id).first()
    if not item:
        return
    try:
        title, text = fetch_page(item.url)
    except FetchError as e:
        item.status, item.error = "failed", str(e)[:300]
        item.save(update_fields=["status", "error", "updated_at"])
        return
    if title and item.title == (urlparse(item.url).hostname or item.url):
        item.title = title[:300]
    item.content, item.status, item.error = text, "ready", ""
    item.save(update_fields=["title", "content", "status", "error", "updated_at"])
    index_item(item)
