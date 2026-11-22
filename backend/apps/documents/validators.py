import hashlib
import os
import re
import zipfile

from django.conf import settings
from rest_framework.exceptions import ValidationError

CONTENT_TYPES = {
    ".pdf": "application/pdf",
    ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    ".txt": "text/plain",
    ".md": "text/markdown",
}


def sanitize_name(name):
    name = os.path.basename(name or "upload")
    return re.sub(r"[^\w.\- ]", "_", name)[:200] or "upload"


def validate_upload(f):
    """Extension allowlist + size cap + magic-byte check. Returns (clean_name, ext, content_type, sha256)."""
    name = sanitize_name(f.name)
    ext = os.path.splitext(name)[1].lower()
    if ext not in settings.ALLOWED_UPLOAD_EXTENSIONS:
        raise ValidationError({"file": f"Unsupported file type. Allowed: {', '.join(sorted(settings.ALLOWED_UPLOAD_EXTENSIONS))}"})
    if f.size > settings.MAX_UPLOAD_MB * 1024 * 1024:
        raise ValidationError({"file": f"File too large (max {settings.MAX_UPLOAD_MB} MB)."})
    if f.size == 0:
        raise ValidationError({"file": "File is empty."})

    f.seek(0)
    head = f.read(8)
    f.seek(0)
    if ext == ".pdf" and not head.startswith(b"%PDF"):
        raise ValidationError({"file": "File content does not match a PDF."})
    if ext == ".docx":
        if not head.startswith(b"PK"):
            raise ValidationError({"file": "File content does not match a DOCX."})
        try:
            with zipfile.ZipFile(f) as z:
                if "word/document.xml" not in z.namelist():
                    raise ValidationError({"file": "File content does not match a DOCX."})
        except zipfile.BadZipFile:
            raise ValidationError({"file": "Corrupt DOCX file."})
        f.seek(0)
    if ext in (".txt", ".md"):
        sample = f.read(4096)
        f.seek(0)
        if b"\x00" in sample:
            raise ValidationError({"file": "File does not look like text."})

    h = hashlib.sha256()
    for chunk in f.chunks():
        h.update(chunk)
    f.seek(0)
    return name, ext, CONTENT_TYPES[ext], h.hexdigest()
