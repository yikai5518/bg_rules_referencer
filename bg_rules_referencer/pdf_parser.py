import io
import re
from typing import Any

import fitz  # PyMuPDF


def extract_text_from_pdf(
    pdf_bytes: bytes, filename: str = ""
) -> tuple[str, dict[str, Any]]:
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

    metadata: dict[str, Any] = {
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
    highlight_texts: list[str] | None = None,
    highlight_rects: list[tuple[float, float, float, float]] | None = None,
    highlight_images: bool = True,
    dpi: int = 150,
    game_name: str | None = None,
) -> tuple[bytes, int, int]:
    """
    Renders a specific page of the PDF to high-resolution PNG bytes,
    with pinpoint translucent highlights over cited text and accent frames
    around referenced diagrams or illustrations.

    Args:
        pdf_bytes: PDF file bytes.
        page_num: 1-indexed page number to render.
        highlight_texts: List of text snippets/clauses to highlight on this page.
        highlight_rects: Optional list of exact (l, t, r, b) bounding boxes to highlight directly.
        highlight_images: Whether to highlight/frame diagrams on this page.
        dpi: Resolution density for rendering (150 DPI is crisp and fast).
        game_name: Optional game name to prevent highlighting standalone titles/headers.

    Returns:
        Tuple of (png_bytes, text_highlights_count, image_highlights_count)
    """
    doc = fitz.open(stream=io.BytesIO(pdf_bytes), filetype="pdf")
    page_idx = max(0, min(page_num - 1, doc.page_count - 1))
    page = doc.load_page(page_idx)

    text_highlight_count = 0
    image_highlight_count = 0

    # 1. Text Highlighting
    placed_rects: list[fitz.Rect] = []  # page-level dedupe to avoid stacked highlights

    # Priority 1: Exact coordinates from Docling provenance
    if highlight_rects:
        print(
            f"[highlight] Page {page_num}: using {len(highlight_rects)} exact coordinate rect(s)"
        )
        for box in highlight_rects:
            try:
                rect = fitz.Rect(*box)
                if (
                    not rect.is_valid
                    or rect.is_empty
                    or rect.width <= 0
                    or rect.height <= 0
                ):
                    continue
                if any(rect.intersects(p) for p in placed_rects):
                    continue
                placed_rects.append(rect)
                annot = page.add_highlight_annot(rect)
                if annot:
                    annot.set_colors(stroke=(1.0, 0.82, 0.15))
                    annot.update()
                    text_highlight_count += 1
            except Exception:
                pass

    # Priority 2: Fuzzy text snippet search fallback if no exact rects provided
    elif highlight_texts:
        print(f"[highlight] Page {page_num}: {len(highlight_texts)} snippet(s)")
        for snippet in highlight_texts:
            if not snippet or not snippet.strip():
                continue
            # Only apply snippets that belong to this page
            page_tag = re.match(r"\s*\[Page (\d+)\]", snippet)
            if page_tag and int(page_tag.group(1)) != page_num:
                continue
            # Remove any [Page X] or header prefixes from the snippet
            cleaned = re.sub(r"\[Page \d+\]\s*", "", snippet).strip()
            # Normalize whitespace within the sentence
            s_clean = re.sub(r"\s+", " ", cleaned).strip()
            if len(s_clean) < 15:
                continue

            # Skip heading-like lines: short, no terminal punctuation, all words capitalised
            words_hd = re.findall(r"[A-Za-z]+", s_clean)
            if (
                len(words_hd) <= 7
                and not s_clean.rstrip(")").endswith((".", "!", "?", ","))
                and all(
                    w[0].isupper()
                    or w.lower()
                    in {
                        "the",
                        "to",
                        "of",
                        "a",
                        "and",
                        "in",
                        "for",
                        "on",
                        "at",
                        "–",
                        "-",
                    }
                    for w in words_hd
                )
            ):
                print(f"[highlight]   SKIP heading: {s_clean!r}")
                continue

            # Skip narrative play examples
            if re.match(
                r"^(?:example\b|for example\b|[A-Z][a-z]+ plays\b|[A-Z][a-z]+ draws\b|[A-Z][a-z]+ sends\b)",
                s_clean,
                re.IGNORECASE,
            ):
                print(f"[highlight]   SKIP example: {s_clean!r}")
                continue

            # Skip common page header banners like 'Player Turn – Agent Turn'
            if re.match(r"^player turn\b", s_clean, re.IGNORECASE):
                print(f"[highlight]   SKIP page banner: {s_clean!r}")
                continue

            # Skip standalone game name or document title headers
            if game_name:
                gn = game_name.lower().strip()
                s_low = s_clean.lower()
                if s_low in {
                    gn,
                    f"{gn} rules",
                    f"{gn} rulebook",
                    f"the {gn} rules",
                    f"{gn} official guide",
                    f"{gn} official rules",
                }:
                    continue

            # Search directly for the sentence
            rects = page.search_for(s_clean)
            if not rects:
                # Normalize curly quotes and dashes if exact match missed
                s_alt = (
                    s_clean.replace("’", "'")
                    .replace("“", '"')
                    .replace("”", '"')
                    .replace("—", "-")
                    .replace("–", "-")
                )
                if s_alt != s_clean:
                    rects = page.search_for(s_alt)

            if rects:
                print(f"[highlight]   FULL  ({len(rects)} rects): {s_clean!r}")
            else:
                print(f"[highlight]   MISS full sentence: {s_clean!r}")
                # If line breaks caused direct search to miss, search in 4-word windows
                words = s_clean.split()
                if len(words) >= 4:
                    for k in range(0, len(words) - 3, 2):
                        phrase = " ".join(words[k : k + 4])
                        if (
                            game_name
                            and phrase.lower().strip() == game_name.lower().strip()
                        ):
                            continue
                        p_rects = page.search_for(phrase)
                        print(
                            f"[highlight]     WINDOW ({len(p_rects)} rects): {phrase!r}"
                        )
                        for r in p_rects:
                            if not any(r.intersects(existing) for existing in rects):
                                rects.append(r)

            for rect in rects:
                try:
                    if (
                        not rect.is_valid
                        or rect.is_empty
                        or rect.width <= 0
                        or rect.height <= 0
                    ):
                        continue
                    if any(rect.intersects(p) for p in placed_rects):
                        continue
                    placed_rects.append(rect)
                    print(
                        f"[highlight]       -> drew: {page.get_textbox(rect).strip()!r}"
                    )
                    annot = page.add_highlight_annot(rect)
                    if annot:
                        # Golden amber translucent highlight
                        annot.set_colors(stroke=(1.0, 0.82, 0.15))
                        annot.update()
                        text_highlight_count += 1
                except Exception:
                    pass

    # 2. Diagram / Image Highlighting
    if highlight_images:
        try:
            images = page.get_images()
            for img in images:
                xref = img[0]
                try:
                    rects = page.get_image_rects(xref)
                    for r in rects:
                        if not r.is_valid or r.is_empty:
                            continue
                        # Filter out tiny icon artifacts (e.g. smaller than 25x25)
                        if r.width >= 25 and r.height >= 25:
                            annot = page.add_rect_annot(r)
                            if annot:
                                # Warm orange accent frame
                                annot.set_colors(stroke=(0.95, 0.45, 0.1))
                                annot.set_border(width=2.5)
                                annot.update()
                                image_highlight_count += 1
                except Exception:
                    pass
        except Exception:
            pass

    try:
        pix = page.get_pixmap(dpi=dpi)
    except Exception:
        pix = page.get_pixmap(dpi=72)

    png_bytes = pix.tobytes("png")
    doc.close()

    return png_bytes, text_highlight_count, image_highlight_count


def get_page_diagram_rects(pdf_bytes: bytes, page_num: int) -> list[dict[str, Any]]:
    """
    Returns bounding box coordinates and dimensions of diagrams/images on a page.

    Args:
        pdf_bytes: PDF file bytes.
        page_num: 1-indexed page number.

    Returns:
        List of dicts containing image bounding coordinates and dimensions.
    """
    doc = fitz.open(stream=io.BytesIO(pdf_bytes), filetype="pdf")
    page_idx = max(0, min(page_num - 1, doc.page_count - 1))
    page = doc.load_page(page_idx)
    diagrams = []
    images = page.get_images()
    for img in images:
        xref = img[0]
        try:
            rects = page.get_image_rects(xref)
            for r in rects:
                if r.width >= 25 and r.height >= 25:
                    diagrams.append(
                        {
                            "xref": xref,
                            "x0": r.x0,
                            "y0": r.y0,
                            "x1": r.x1,
                            "y1": r.y1,
                            "width": r.width,
                            "height": r.height,
                        }
                    )
        except Exception:
            pass
    doc.close()
    return diagrams
