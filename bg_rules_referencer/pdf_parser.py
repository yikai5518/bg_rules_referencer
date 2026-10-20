import io
import re
from typing import Any, Dict, List, Optional, Tuple

import fitz  # PyMuPDF


def extract_text_from_pdf(
    pdf_bytes: bytes, filename: str = ""
) -> Tuple[str, Dict[str, Any]]:
    """
    Extracts text, metadata, and visual structure from PDF bytes using PyMuPDF.

    Args:
        pdf_bytes: The raw byte content of the PDF file.
        filename: Optional filename to help infer game name.

    Returns:
        Tuple containing:
            - full_text: Concatenated text of all pages with [Page X] tags.
            - metadata: Dictionary with page_count, char_count, image_count, and inferred_name.
    """
    doc = fitz.open(stream=io.BytesIO(pdf_bytes), filetype="pdf")
    pages_text = []
    total_images = 0

    for page_num in range(doc.page_count):
        page = doc.load_page(page_num)
        text = page.get_text()
        total_images += len(page.get_images())
        if text.strip():
            pages_text.append(f"[Page {page_num + 1}]\n{text.strip()}")

    full_text = "\n\n".join(pages_text)

    # Attempt to infer the board game name
    inferred_name = None
    meta_title = doc.metadata.get("title") if doc.metadata else None
    if (
        meta_title
        and len(meta_title.strip()) > 2
        and "untitled" not in meta_title.lower()
    ):
        inferred_name = meta_title.strip()
    elif filename:
        clean_name = re.sub(r"\.[^.]+$", "", filename)  # strip extension
        clean_name = re.sub(r"[-_]", " ", clean_name)
        # Filter out generic words
        ignored = {
            "rules",
            "rulebook",
            "rule",
            "manual",
            "instructions",
            "en",
            "eng",
            "english",
            "official",
            "board",
            "game",
        }
        words = [w for w in clean_name.split() if w.lower() not in ignored]
        if words:
            inferred_name = " ".join(words).title()
        else:
            inferred_name = clean_name.title()

    metadata: Dict[str, Any] = {
        "page_count": doc.page_count,
        "char_count": len(full_text),
        "image_count": total_images,
        "inferred_name": inferred_name or "Board Game",
    }
    doc.close()
    return full_text, metadata


def render_page_with_highlights(
    pdf_bytes: bytes,
    page_num: int,
    highlight_texts: Optional[List[str]] = None,
    highlight_images: bool = True,
    dpi: int = 150,
) -> Tuple[bytes, int, int]:
    """
    Renders a specific page of the PDF to high-resolution PNG bytes,
    with pinpoint translucent highlights over cited text and accent frames
    around referenced diagrams or illustrations.

    Args:
        pdf_bytes: PDF file bytes.
        page_num: 1-indexed page number to render.
        highlight_texts: List of text snippets/clauses to highlight on this page.
        highlight_images: Whether to highlight/frame diagrams on this page.
        dpi: Resolution density for rendering (150 DPI is crisp and fast).

    Returns:
        Tuple of (png_bytes, text_highlights_count, image_highlights_count)
    """
    doc = fitz.open(stream=io.BytesIO(pdf_bytes), filetype="pdf")
    page_idx = max(0, min(page_num - 1, doc.page_count - 1))
    page = doc.load_page(page_idx)

    text_highlight_count = 0
    image_highlight_count = 0

    # 1. Text Highlighting
    if highlight_texts:
        for snippet in highlight_texts:
            if not snippet or not snippet.strip():
                continue
            # Remove any [Page X] or header prefixes from the snippet
            cleaned = re.sub(r"\[Page \d+\]\s*", "", snippet).strip()
            # Split into individual sentences or clauses
            sentences = re.split(r"(?<=[.!?])\s+|\n+", cleaned)

            for sentence in sentences:
                s_clean = sentence.strip()
                if len(s_clean) < 4:
                    continue

                # Search directly for the sentence
                rects = page.search_for(s_clean)
                if not rects:
                    # If line breaks caused direct search to miss, search in 3-5 word windows
                    words = s_clean.split()
                    if len(words) >= 3:
                        for k in range(0, len(words) - 2, 2):
                            phrase = " ".join(words[k : k + 4])
                            p_rects = page.search_for(phrase)
                            for r in p_rects:
                                if not any(
                                    r.intersects(existing) for existing in rects
                                ):
                                    rects.append(r)

                for rect in rects:
                    annot = page.add_highlight_annot(rect)
                    # Golden amber translucent highlight
                    annot.set_colors(stroke=(1.0, 0.82, 0.15))
                    annot.update()
                    text_highlight_count += 1

    # 2. Diagram / Image Highlighting
    if highlight_images:
        images = page.get_images()
        for img in images:
            xref = img[0]
            try:
                rects = page.get_image_rects(xref)
                for r in rects:
                    # Filter out tiny icon artifacts (e.g. smaller than 25x25)
                    if r.width >= 25 and r.height >= 25:
                        annot = page.add_rect_annot(r)
                        # Warm orange accent frame
                        annot.set_colors(stroke=(0.95, 0.45, 0.1))
                        annot.set_border(width=2.5)
                        annot.update()
                        image_highlight_count += 1
            except Exception:
                pass

    pix = page.get_pixmap(dpi=dpi)
    png_bytes = pix.tobytes("png")
    doc.close()

    return png_bytes, text_highlight_count, image_highlight_count
