import io
import os
import re
from dataclasses import dataclass, field
from typing import Any

import fitz  # PyMuPDF for fast metadata & fallback
from docling.datamodel.base_models import DocumentStream, InputFormat
from docling.datamodel.pipeline_options import PdfPipelineOptions
from docling.document_converter import DocumentConverter, PdfFormatOption
from llama_index.core.schema import TextNode


@dataclass
class RulebookDocument:
    """
    Structured rulebook document produced by Docling layout parsing and LlamaIndex node creation.
    """

    full_text: str
    metadata: dict[str, Any]
    nodes: list[TextNode] = field(default_factory=list)
    page_elements: dict[int, list[dict[str, Any]]] = field(default_factory=dict)
    docling_doc: Any | None = None


_converter_instance: DocumentConverter | None = None


def get_docling_converter() -> DocumentConverter:
    """
    Returns a cached instance of DocumentConverter configured for fast digital PDF conversion
    with OCR disabled, table structure prediction disabled for speed, and tuned thread allocation.
    """
    global _converter_instance
    if _converter_instance is None:
        pipeline_options = PdfPipelineOptions()
        pipeline_options.do_ocr = False
        pipeline_options.do_table_structure = False
        # Set accelerator thread count (default 2 to match cloud vCPU allocation without thrashing)
        num_threads = int(os.getenv("DOCLING_NUM_THREADS", "2"))
        pipeline_options.accelerator_options.num_threads = num_threads

        _converter_instance = DocumentConverter(
            format_options={
                InputFormat.PDF: PdfFormatOption(pipeline_options=pipeline_options)
            }
        )
    return _converter_instance


def parse_rulebook_with_docling(
    pdf_bytes: bytes, filename: str = ""
) -> RulebookDocument:
    """
    Parses a board game rulebook PDF using Docling with OCR disabled, extracting:
    1. Structured text with [Page X] markers.
    2. Document metadata and inferred game name.
    3. Structural element bounding boxes (converted to top-left origin for PyMuPDF).
    4. Pre-built LlamaIndex TextNodes for hybrid semantic & keyword retrieval.
    """
    converter = get_docling_converter()
    doc_stream = DocumentStream(
        name=filename or "rulebook.pdf", stream=io.BytesIO(pdf_bytes)
    )

    conv_res = converter.convert(doc_stream)
    docling_doc = conv_res.document

    # Extract basic metadata using PyMuPDF for speed & title detection
    doc_fitz = fitz.open(stream=io.BytesIO(pdf_bytes), filetype="pdf")
    page_count = doc_fitz.page_count
    total_images = sum(len(doc_fitz[p].get_images()) for p in range(page_count))

    inferred_name = None
    meta_title = doc_fitz.metadata.get("title") if doc_fitz.metadata else None
    if (
        meta_title
        and len(meta_title.strip()) > 2
        and "untitled" not in meta_title.lower()
    ):
        inferred_name = meta_title.strip()
    elif filename:
        clean_name = re.sub(r"\.[^.]+$", "", filename)
        clean_name = re.sub(r"[-_]", " ", clean_name)
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
        inferred_name = " ".join(words).title() if words else clean_name.title()

    doc_fitz.close()

    # Iterate through docling items to collect elements, bounding boxes, and nodes
    page_elements: dict[int, list[dict[str, Any]]] = {
        p: [] for p in range(1, page_count + 1)
    }
    nodes: list[TextNode] = []
    pages_text: dict[int, list[str]] = {p: [] for p in range(1, page_count + 1)}

    node_counter = 0

    for item, level in docling_doc.iterate_items():
        label_raw = getattr(item, "label", "text")
        label = label_raw.value if hasattr(label_raw, "value") else str(label_raw)
        provs = getattr(item, "prov", [])
        if not provs:
            continue

        primary_page = provs[0].page_no
        if primary_page not in page_elements:
            page_elements[primary_page] = []

        # Convert bounding boxes to fitz top-left origin
        bboxes: list[tuple[float, float, float, float]] = []
        if primary_page in docling_doc.pages:
            page_h = docling_doc.pages[primary_page].size.height
            for p in provs:
                tl = p.bbox.to_top_left_origin(page_h)
                bboxes.append((tl.l, tl.t, tl.r, tl.b))

        text = getattr(item, "text", "")
        if text:
            text = text.strip()

        is_heading = label in {
            "section_header",
            "title",
            "page_header",
            "page_footer",
        }
        is_visual = label in {"picture", "figure", "chart", "caption"}

        elem_dict = {
            "text": text,
            "label": label,
            "bboxes": bboxes,
            "page_no": primary_page,
            "is_heading": is_heading,
            "is_visual": is_visual,
        }
        page_elements[primary_page].append(elem_dict)

        if text:
            pages_text[primary_page].append(text)

            # Check if text looks like a heading even if mislabeled as generic text
            words_hd = re.findall(r"[A-Za-z]+", text)
            if (
                len(words_hd) <= 7
                and not text.rstrip(")").endswith((".", "!", "?", ","))
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
                is_heading = True

            # Create LlamaIndex TextNode
            node_counter += 1
            node = TextNode(
                text=text,
                id_=f"node_{primary_page}_{node_counter}",
                metadata={
                    "page_no": primary_page,
                    "label": label,
                    "is_heading": is_heading,
                    "is_visual": is_visual,
                    "bboxes": bboxes,
                },
            )
            nodes.append(node)

    # Build full structured text with [Page X] tags
    formatted_pages = []
    for p in range(1, page_count + 1):
        lines = pages_text.get(p, [])
        if lines:
            formatted_pages.append(f"[Page {p}]\n" + "\n\n".join(lines))
        else:
            formatted_pages.append(f"[Page {p}]")

    full_text = "\n\n".join(formatted_pages)

    metadata: dict[str, Any] = {
        "page_count": page_count,
        "char_count": len(full_text),
        "image_count": total_images,
        "inferred_name": inferred_name or "Board Game",
    }

    return RulebookDocument(
        full_text=full_text,
        metadata=metadata,
        nodes=nodes,
        page_elements=page_elements,
        docling_doc=docling_doc,
    )
