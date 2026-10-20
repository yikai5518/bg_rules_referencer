---
name: pdf-rulebook-testing
description: Test PyMuPDF text extraction, page parsing, metadata inference, and highlight rendering on rulebook PDFs.
---

# PDF Rulebook Testing

This skill provides testing procedures for PyMuPDF text extraction and high-DPI rendering in `bg_rules_referencer/pdf_parser.py`.

## Quick Validation

Run the dedicated PDF parser unit tests:

```bash
uv run pytest tests/test_workflow.py -k "test_pdf_parser or test_render_page_with_highlights" -v
```

## Manual Python Check

You can verify page rendering and highlights interactively:

```python
import fitz
from bg_rules_referencer.pdf_parser import extract_text_from_pdf, render_page_with_highlights

with open("path/to/rulebook.pdf", "rb") as f:
    pdf_bytes = f.read()

text, metadata = extract_text_from_pdf(pdf_bytes, filename="test.pdf")
print("Pages:", metadata["page_count"])
print("Images:", metadata["image_count"])

png_bytes, text_hl, img_hl = render_page_with_highlights(
    pdf_bytes,
    page_num=1,
    highlight_texts=["sample rule clause"],
    highlight_images=True,
)
print(f"Rendered {len(png_bytes)} bytes with {text_hl} text highlights and {img_hl} diagram frames.")
```

## Key Invariants
- Each page in extracted text must begin with `[Page X]`.
- Text highlights should use golden amber (`(1.0, 0.82, 0.15)`).
- Diagram frames should use warm orange (`(0.95, 0.45, 0.1)`).
- Word window searching (3–5 words) must be preserved to handle line wrapping.
