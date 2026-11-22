import logging
from urllib.parse import urlparse

from django.db import transaction

from apps.ai_engine import providers
from apps.collections.models import Collection, Tag

from .chunking import chunk_text
from .models import Chunk, KnowledgeItem

log = logging.getLogger(__name__)
EMBED_BATCH = 64


def attach_organization(item, collection_ids=None, tag_names=None):
    """Attach collections/tags, restricted to the item's owner (prevents cross-user linking)."""
    if collection_ids is not None:
        item.collections.set(Collection.objects.filter(owner=item.owner, id__in=collection_ids))
    if tag_names is not None:
        tags = [Tag.objects.get_or_create(owner=item.owner, name=n.strip().lower())[0]
                for n in tag_names if n.strip()]
        item.tags.set(tags)


def create_note(owner, title, content, collection_ids=None, tag_names=None):
    item = KnowledgeItem.objects.create(owner=owner, kind="note", title=title, content=content, status="ready")
    attach_organization(item, collection_ids, tag_names)
    from .tasks import index_item_task
    index_item_task.delay(item.id)
    return item


def create_bookmark(owner, url, title="", collection_ids=None, tag_names=None):
    host = urlparse(url).hostname or url
    item = KnowledgeItem.objects.create(owner=owner, kind="bookmark", title=title or host, url=url,
                                        status="pending")
    attach_organization(item, collection_ids, tag_names)
    from .tasks import fetch_url_task
    fetch_url_task.delay(item.id)
    return item


def index_item(item):
    """(Re)build chunks and embeddings. Keyword search works even if embedding fails."""
    texts = chunk_text(item.content)
    if not texts and item.title:
        texts = [item.title]
    with transaction.atomic():
        item.chunks.all().delete()
        chunks = Chunk.objects.bulk_create(
            [Chunk(item=item, owner_id=item.owner_id, position=i, text=t) for i, t in enumerate(texts)])
    try:
        embedder = providers.get_embedding_provider()
        for start in range(0, len(chunks), EMBED_BATCH):
            batch = chunks[start:start + EMBED_BATCH]
            vectors = embedder.embed([c.text for c in batch])
            for c, v in zip(batch, vectors):
                c.embedding = v
            Chunk.objects.bulk_update(batch, ["embedding"])
    except providers.ProviderError as e:
        log.warning("Embedding skipped for item %s: %s", item.id, e)
    return len(chunks)
