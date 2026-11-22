import re


def chunk_text(text, max_chars=1200, overlap=150):
    """Paragraph-aware chunking with character overlap."""
    text = re.sub(r"\r\n?", "\n", text or "").strip()
    if not text:
        return []
    paras = [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]
    chunks, cur = [], ""
    for p in paras:
        while len(p) > max_chars:  # hard-split giant paragraphs
            cut = p.rfind(" ", 0, max_chars)
            cut = cut if cut > max_chars // 2 else max_chars
            piece, p = p[:cut], p[cut:].strip()
            if cur:
                chunks.append(cur)
                cur = ""
            chunks.append(piece)
        if len(cur) + len(p) + 2 <= max_chars:
            cur = f"{cur}\n\n{p}".strip()
        else:
            if cur:
                chunks.append(cur)
            cur = p
    if cur:
        chunks.append(cur)
    if overlap and len(chunks) > 1:
        chunks = [chunks[0]] + [chunks[i - 1][-overlap:].split(" ", 1)[-1] + " " + chunks[i]
                                for i in range(1, len(chunks))]
    return chunks
