# AGENTS.md — Board Game Rules Helper

This document defines core instructions, architectural context, development standards, and available workflows for AI agents operating within the `Board Game Rules Helper` repository.

---

## 1. Project Overview & Architecture

**Board Game Rules Helper** is a multi-agent application that provides verified, strictly grounded answers to board game rules questions directly referenced against official rulebook PDFs, featuring an interactive 50/50 side-by-side document viewer and visual highlighting engine.

### Key Architecture Components
- **`bg_rules_referencer/pdf_parser.py`**:
  - Uses **PyMuPDF (`fitz`)** for high-fidelity text extraction, structured with `[Page X]` page markers.
  - Extracts document metadata (inferred game title, page count, character count, diagram/image count).
  - Implements `render_page_with_highlights()`: generates high-DPI rendered page images with dynamic visual highlights (golden amber for cited rules text, warm orange frames for referenced diagrams/illustrations).
- **`bg_rules_referencer/agents/`**:
  - `orchestrator.py`: Analyzes the user's question, extracting rule intent, gameplay mechanics, and search keywords for the active game, with heuristic fallbacks if LLM APIs are unavailable.
  - `knowledge_extractor.py`: Chunks the uploaded rulebook page-by-page, ranks passages against query intent and keywords, and isolates `relevant_chunks`, `highlight_snippets`, and `referenced_pages`.
  - `rules_judge.py`: Synthesizes final ruling grounded strictly in extracted excerpts, enforcing in-line page citations (e.g. `(Page 4)`) and summary reference lines (`**📖 Referenced Pages:** Page X`).
  - `base.py`: Defines shared Pydantic `AgentState` and `BaseAgent`.
- **`bg_rules_referencer/workflow.py`**:
  - Orchestrates streamlined multi-agent execution using **LangGraph** (`StateGraph`):
    `START -> orchestrator -> knowledge_extractor -> rules_judge -> END`.
- **`app.py`**:
  - **Streamlit** user interface featuring a balanced 50/50 side-by-side layout:
    - **Left Column (Viewer):** Sticky navigation controls (`◀ Prev`, direct page input, `Next ▶`, `🎯 Cited Page`), multi-page quick-jump pills (`[ 📄 Page 3 ]`), high-res page image with highlights, and highlight toggles.
    - **Right Column (Chat):** Scrollable chat assistant, instant `[ 🔍 View Page X ]` jump buttons, expandable source excerpts, and auto-snapping to the primary referenced page upon ruling completion.

---

## 2. Environment & Tooling Standards

- **Python Version**: `>=3.13`
- **Package & Dependency Manager**: **`uv`** (strictly use `uv` instead of raw `pip` or standard `python -m venv` where possible).
- **Formatting & Linting**: **`ruff`**
- **Testing**: **`pytest`** (configured with `pythonpath = ["."]` in `pyproject.toml`)

### Essential CLI Commands
```bash
# Install dependencies in editable mode
uv pip install -e .

# Run the Streamlit application
uv run streamlit run app.py

# Run all test suites
uv run pytest tests/test_workflow.py -v

# Run lint checks
uv run ruff check .

# Apply safe formatting fixes
uv run ruff format .
uv run ruff check --fix .
```

---

## 3. Engineering Guidelines for Agents

### Rulebook Grounding & No Hallucination
- **Zero Hallucination Tolerance**: Rulings must strictly reflect the uploaded rulebook. If an answer cannot be determined from the provided text, the agent must explicitly state that the rules text does not cover the situation.
- **Always Include Page Citations**: Whenever extracting or judging rules, preserve and cite `[Page X]` references so players can verify the original source.
- **Keep AgentState Pure**: Update state exclusively through returning dict updates from LangGraph nodes.

### PDF Parsing & Visual Rendering
- Do not remove `[Page X]` headers during extraction in `pdf_parser.py`; downstream agents rely on them to determine page numbers for rendering citations.
- When highlighting in `render_page_with_highlights`, decompose snippet sentences into 3–5 word sliding windows to withstand line wraps and whitespace variations in PDFs.
- For diagram detection, use `page.get_images()` and `page.get_image_rects(xref)` to frame illustrations with warm orange accent borders.

### Side-by-Side User Experience
- Maintain 50/50 side-by-side visual balance between the document viewer and the chat assistant.
- Ensure the viewer automatically snaps to the primary referenced page when a new ruling is produced.
- Provide interactive jump pills (`[ 📄 Page X ]`) in both the chat responses and the viewer toolbar.

### API Keys & Secrets
- `GOOGLE_API_KEY` must be configured in `.env` for Gemini models via `langchain-google-genai`.
- Graceful fallbacks must always be provided so quota exhaustion (HTTP 402) or missing keys display extracted excerpts without crashing the app.
- Never commit `.env` or raw API keys into version control.

---

## 4. Workspace Customizations & Skills

Specialized agent workflows and runbooks are organized under `.agents/skills/`. Each skill contains a `SKILL.md` specification following the Antigravity customization guidelines.

```text
.agents/
└── skills/
    ├── eval-rules-workflow/    # Evaluate LangGraph graph execution & grounding fidelity
    ├── pdf-rulebook-testing/   # Validate PyMuPDF text extraction & highlight rendering
    └── app-ui-testing/         # Runbook for launching and verifying the Streamlit UI
```

### Available Skills Summary
| Skill | Directory | Description |
| :--- | :--- | :--- |
| **`eval-rules-workflow`** | [.agents/skills/eval-rules-workflow/](file:///.agents/skills/eval-rules-workflow/SKILL.md) | Run and evaluate multi-agent reasoning, grounding checks, and LangGraph workflow correctness. |
| **`pdf-rulebook-testing`** | [.agents/skills/pdf-rulebook-testing/](file:///.agents/skills/pdf-rulebook-testing/SKILL.md) | Test PyMuPDF text extraction, page parsing, metadata inference, and highlight rendering on rulebook PDFs. |
| **`app-ui-testing`** | [.agents/skills/app-ui-testing/](file:///.agents/skills/app-ui-testing/SKILL.md) | Step-by-step verification and diagnostic procedure for the Streamlit web interface. |
