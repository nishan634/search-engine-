import io

MAX_PAGES = 500


class ExtractionError(Exception):
    pass


def extract_text(data: bytes, ext: str) -> str:
    try:
        if ext in (".txt", ".md"):
            return data.decode("utf-8", errors="replace")
        if ext == ".pdf":
            from pypdf import PdfReader
            reader = PdfReader(io.BytesIO(data))
            if reader.is_encrypted:
                raise ExtractionError("Encrypted PDFs are not supported.")
            return "\n\n".join((p.extract_text() or "") for p in reader.pages[:MAX_PAGES])
        if ext == ".docx":
            from docx import Document
            doc = Document(io.BytesIO(data))
            parts = [p.text for p in doc.paragraphs if p.text.strip()]
            for table in doc.tables:
                for row in table.rows:
                    parts.append(" | ".join(c.text.strip() for c in row.cells))
            return "\n\n".join(parts)
    except ExtractionError:
        raise
    except Exception as e:
        raise ExtractionError(f"Could not read document ({e.__class__.__name__}).") from e
    raise ExtractionError("Unsupported file type.")
