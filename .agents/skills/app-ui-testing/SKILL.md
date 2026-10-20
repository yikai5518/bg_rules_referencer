---
name: app-ui-testing
description: Runbook for launching and verifying the Streamlit side-by-side web interface.
---

# Streamlit App UI Testing

This skill provides verification procedures for the Streamlit side-by-side user interface in `app.py`.

## Launching the Application

Run Streamlit with `uv`:

```bash
uv run streamlit run app.py
```

## UI Verification Checklist

1. **Initial Empty State:**
   - Welcome hero card displays with guide cards.
   - Upload widget is available in the sidebar.

2. **Rulebook Upload:**
   - Upload a PDF rulebook.
   - Active Game metadata card populates in the sidebar (file name, page count, diagram count).
   - Layout transitions into the 50/50 side-by-side view.

3. **Left Column (Viewer):**
   - Page 1 renders crisply.
   - Navigation controls (`◀ Prev`, direct page input, `Next ▶`) switch pages smoothly.
   - Highlight toggles in sidebar enable/disable text highlights and diagram frames.

4. **Right Column (Chat & Auto-Snap):**
   - Asking a rules question triggers agent stream progress.
   - The response includes in-line page citations and clickable `[ 🔍 View Page X ]` buttons.
   - The left viewer automatically snaps to the primary cited page.
   - Multi-page citation pills appear above the viewer (`[ 📄 Page X ]`) to jump between referenced pages in one click.
