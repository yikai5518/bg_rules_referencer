import ast
import re
from typing import Any
import uuid

import streamlit as st
from langchain_core.messages import HumanMessage
from langgraph.checkpoint.memory import MemorySaver

from bg_rules_referencer.ingestion import parse_rulebook_with_docling
from bg_rules_referencer.pdf_parser import render_page_with_highlights
from bg_rules_referencer.workflow import build_workflow


def format_message_text(content: Any) -> str:
    """Safely extracts human-readable markdown text from string, list of dicts, or serialized dicts."""
    if isinstance(content, list):
        parts = []
        for item in content:
            if isinstance(item, dict) and "text" in item:
                parts.append(str(item["text"]))
            elif isinstance(item, str):
                parts.append(item)
            elif hasattr(item, "text"):
                parts.append(str(getattr(item, "text")))
            else:
                parts.append(str(item))
        return "".join(parts).strip()
    if isinstance(content, dict) and "text" in content:
        return str(content["text"]).strip()
    if isinstance(content, str):
        s = content.strip()
        # Handle serialized python list/dict repr
        if s.startswith("[{'type':") or s.startswith('[{"type":'):
            try:
                parsed = ast.literal_eval(s)
                if isinstance(parsed, list):
                    return format_message_text(parsed)
            except Exception:
                m = re.search(
                    r"['\"]text['\"]\s*:\s*['\"](.*?)['\"]\s*,\s*['\"]extras['\"]",
                    s,
                    re.DOTALL,
                )
                if m:
                    try:
                        return m.group(1).encode().decode("unicode-escape")
                    except Exception:
                        return m.group(1)
        return s
    return str(content).strip()


def set_viewer_page(target_page: int):
    """Synchronously updates current_page and increments page_version to reset the input widget."""
    max_p = st.session_state.get("page_count", 1) or 1
    clamped = max(1, min(int(target_page), max_p))
    if clamped != st.session_state.get("current_page", 1):
        st.session_state.current_page = clamped
        st.session_state.page_version = st.session_state.get("page_version", 0) + 1


# Configure Streamlit page for wide side-by-side layout
st.set_page_config(
    page_title="Board Game Rules Helper",
    page_icon="🎲",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Custom Styling for modern aesthetic & glassmorphism
st.markdown(
    """
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Outfit:wght@400;500;600;700&display=swap');

    html, body, [class*="css"] {
        font-family: 'Outfit', sans-serif;
    }

    .main-title {
        font-size: 1.8rem;
        font-weight: 700;
        background: linear-gradient(135deg, #6366f1 0%, #a855f7 50%, #ec4899 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        margin-bottom: 0.1rem;
    }

    .subtitle {
        color: #94a3b8;
        font-size: 0.9rem;
        margin-bottom: 1rem;
    }

    .viewer-header {
        display: flex;
        align-items: center;
        justify-content: space-between;
        padding: 0.5rem 0.75rem;
        background: rgba(255, 255, 255, 0.03);
        border: 1px solid rgba(255, 255, 255, 0.08);
        border-radius: 10px;
        margin-bottom: 0.5rem;
    }

    .page-chip {
        display: inline-flex;
        align-items: center;
        gap: 0.35rem;
        padding: 0.2rem 0.6rem;
        border-radius: 9999px;
        background: rgba(245, 158, 11, 0.15);
        border: 1px solid rgba(245, 158, 11, 0.4);
        color: #fde68a;
        font-size: 0.8rem;
        font-weight: 500;
        margin-right: 0.4rem;
    }

    .stat-card {
        padding: 0.9rem;
        border-radius: 12px;
        background: rgba(255, 255, 255, 0.04);
        border: 1px solid rgba(255, 255, 255, 0.08);
        margin-bottom: 0.75rem;
        font-size: 0.85rem;
    }

    .hero-card {
        padding: 2.5rem;
        border-radius: 16px;
        background: linear-gradient(145deg, rgba(30, 27, 75, 0.5) 0%, rgba(15, 23, 42, 0.7) 100%);
        border: 1px solid rgba(139, 92, 246, 0.25);
        text-align: center;
        margin: 2rem 0;
    }

    .feature-grid {
        display: grid;
        grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
        gap: 1rem;
        margin-top: 1.5rem;
        text-align: left;
    }

    .feature-item {
        padding: 1rem;
        border-radius: 10px;
        background: rgba(255, 255, 255, 0.03);
        border: 1px solid rgba(255, 255, 255, 0.06);
    }
    </style>
    """,
    unsafe_allow_html=True,
)

# Initialize Session State
if "memory" not in st.session_state:
    st.session_state.memory = MemorySaver()
    st.session_state.app = build_workflow(checkpointer=st.session_state.memory)
    st.session_state.thread_id = str(uuid.uuid4())
    st.session_state.config = {
        "configurable": {"thread_id": st.session_state.thread_id}
    }

if "messages" not in st.session_state:
    st.session_state.messages = []

if "rulebook_text" not in st.session_state:
    st.session_state.rulebook_text = None
    st.session_state.rulebook_doc = None
    st.session_state.rulebook_filename = None
    st.session_state.pdf_bytes = None
    st.session_state.game_name = None
    st.session_state.page_count = 0
    st.session_state.char_count = 0
    st.session_state.image_count = 0
    st.session_state.current_page = 1
    st.session_state.page_version = 0
    st.session_state.active_highlights = []
    st.session_state.active_highlight_bboxes = {}
    st.session_state.active_referenced_pages = []

if "show_highlights" not in st.session_state:
    st.session_state.show_highlights = True
if "show_diagram_frames" not in st.session_state:
    st.session_state.show_diagram_frames = True
if "is_visual_query" not in st.session_state:
    st.session_state.is_visual_query = False

# --- Sidebar: PDF Ingestion & Viewer Controls ---
with st.sidebar:
    st.markdown("### 🎲 Rulebook Setup")

    uploaded_file = st.file_uploader(
        "📄 Upload Rulebook (PDF)",
        type=["pdf"],
        help="Upload the official rulebook PDF. It will be indexed and viewed side-by-side with chat.",
    )

    if uploaded_file is not None:
        if st.session_state.rulebook_filename != uploaded_file.name:
            with st.spinner("Analyzing document structure & indexing with Docling..."):
                raw_bytes = uploaded_file.getvalue()
                rulebook_doc = parse_rulebook_with_docling(
                    raw_bytes, filename=uploaded_file.name
                )
                st.session_state.pdf_bytes = raw_bytes
                st.session_state.rulebook_doc = rulebook_doc
                st.session_state.rulebook_text = rulebook_doc.full_text
                st.session_state.rulebook_filename = uploaded_file.name
                st.session_state.game_name = rulebook_doc.metadata.get(
                    "inferred_name", "Board Game"
                )
                st.session_state.page_count = rulebook_doc.metadata.get("page_count", 1)
                st.session_state.char_count = rulebook_doc.metadata.get("char_count", 0)
                st.session_state.image_count = rulebook_doc.metadata.get(
                    "image_count", 0
                )
                st.session_state.current_page = 1
                st.session_state.page_version = 0
                st.session_state.active_highlights = []
                st.session_state.active_highlight_bboxes = {}
                st.session_state.active_referenced_pages = []
                st.session_state.is_visual_query = False

                # Reset thread and chat history
                st.session_state.thread_id = str(uuid.uuid4())
                st.session_state.config = {
                    "configurable": {"thread_id": st.session_state.thread_id}
                }
                st.session_state.messages = [
                    {
                        "role": "assistant",
                        "content": (
                            f"🎉 Successfully loaded **{st.session_state.game_name}** "
                            f"({st.session_state.page_count} pages, {st.session_state.image_count} visual elements).\n\n"
                            "Ask any question! The matching text and diagrams will be highlighted on the left."
                        ),
                        "referenced_pages": [1],
                        "excerpts": [],
                    }
                ]
                st.rerun()

    # Active Rulebook Metadata Card
    if st.session_state.rulebook_text:
        st.markdown("#### 📖 Active Game")
        custom_name = st.text_input(
            "Game Name",
            value=st.session_state.game_name or "Board Game",
            key="game_name_editor",
        )
        if custom_name != st.session_state.game_name:
            st.session_state.game_name = custom_name

        st.markdown(
            f"""
            <div class="stat-card">
                <div>📁 <b>File:</b> {st.session_state.rulebook_filename}</div>
                <div>📑 <b>Pages:</b> {st.session_state.page_count}</div>
                <div>🖼️ <b>Diagrams:</b> {st.session_state.image_count} detected</div>
                <div>🔤 <b>Text Size:</b> {st.session_state.char_count:,} chars</div>
                <div style="margin-top: 0.4rem; color: #4ade80;">🟢 <b>Ready for Side-by-Side Reference</b></div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        st.markdown("#### 🎨 Highlighting Options")
        st.session_state.show_highlights = st.checkbox(
            "✨ Text Highlights",
            value=st.session_state.show_highlights,
            help="Toggle translucent yellow highlights on referenced text passages.",
        )
        st.session_state.show_diagram_frames = st.checkbox(
            "🖼️ Diagram Frames (Visual Queries)",
            value=st.session_state.show_diagram_frames,
            help="Frame diagrams and components when questions ask about visual elements, setup, or icons.",
        )

        if st.button("🗑️ Clear / Reset Rulebook", use_container_width=True):
            st.session_state.rulebook_text = None
            st.session_state.rulebook_filename = None
            st.session_state.pdf_bytes = None
            st.session_state.game_name = None
            st.session_state.page_count = 0
            st.session_state.char_count = 0
            st.session_state.image_count = 0
            st.session_state.current_page = 1
            st.session_state.page_version = 0
            st.session_state.active_highlights = []
            st.session_state.active_referenced_pages = []
            st.session_state.is_visual_query = False
            st.session_state.messages = []
            st.session_state.thread_id = str(uuid.uuid4())
            st.session_state.config = {
                "configurable": {"thread_id": st.session_state.thread_id}
            }
            st.rerun()

        from bg_rules_referencer.settings import settings

        st.markdown("#### 🤖 Active Models")
        st.markdown(
            f"""
            <div class="stat-card" style="font-size: 0.8rem;">
                <div>⚡ <b>Router:</b> <code>{settings.orchestrator_model}</code></div>
                <div>⚖️ <b>Judge:</b> <code>{settings.rules_judge_model}</code></div>
                <div>🖼️ <b>Vision:</b> <code>{settings.vision_model}</code></div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    st.markdown("---")
    st.markdown(
        """
        **Interactive Workflow:**
        * 📖 **PDF on Left:** Crisp page views with yellow highlights & orange diagram frames.
        * 💬 **Chat on Right:** Clear rulings with page citations & instant jump buttons.
        """
    )
    st.caption("Powered by PyMuPDF, LangGraph & Gemini")

# --- Header ---
st.markdown(
    '<div class="main-title">Board Game Rules Helper ♟️</div>', unsafe_allow_html=True
)

# Empty State: Prompt user to upload a rulebook
if not st.session_state.rulebook_text or not st.session_state.pdf_bytes:
    st.markdown(
        """
        <div class="hero-card">
            <h2 style="margin-top: 0;">📖 Upload a Rulebook to Start Side-by-Side Adjudication</h2>
            <p style="color: #cbd5e1; max-width: 650px; margin: 0 auto 1.5rem auto;">
                Upload your board game's official rulebook (PDF) in the sidebar.
                The assistant will display the rulebook side-by-side with the chat,
                automatically navigating and highlighting exact text and diagrams when you ask rules questions.
            </p>
            <div class="feature-grid">
                <div class="feature-item">
                    <b>⚡ Visual Highlights</b><br/>
                    <span style="font-size: 0.85rem; color: #94a3b8;">Referenced passages are marked directly on the page image.</span>
                </div>
                <div class="feature-item">
                    <b>🖼️ Diagram Framing</b><br/>
                    <span style="font-size: 0.85rem; color: #94a3b8;">Setup illustrations and component images are framed for visual reference.</span>
                </div>
                <div class="feature-item">
                    <b>📍 Auto-Navigation</b><br/>
                    <span style="font-size: 0.85rem; color: #94a3b8;">Viewer snaps to the cited page automatically when a question is answered.</span>
                </div>
                <div class="feature-item">
                    <b>🔍 Verifiable Rulings</b><br/>
                    <span style="font-size: 0.85rem; color: #94a3b8;">Grounded 100% in the uploaded rulebook with exact page numbers.</span>
                </div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

else:
    # Side-by-Side 50/50 Layout
    col_viewer, col_chat = st.columns([1, 1], gap="large")

    # ==========================================
    # LEFT COLUMN: INTERACTIVE RULEBOOK VIEWER
    # ==========================================
    with col_viewer:
        st.markdown(f"#### 📖 Rulebook Viewer: **{st.session_state.game_name}**")

        # Viewer Navigation Bar
        nav_c1, nav_c2, nav_c3, nav_c4 = st.columns([1, 1.8, 1, 1.4])
        with nav_c1:
            if st.button(
                "◀ Prev",
                use_container_width=True,
                disabled=st.session_state.current_page <= 1,
            ):
                set_viewer_page(st.session_state.current_page - 1)
                st.rerun()

        with nav_c2:
            new_page = st.number_input(
                "Page",
                min_value=1,
                max_value=max(1, st.session_state.page_count),
                value=st.session_state.current_page,
                key=f"page_selector_{st.session_state.get('page_version', 0)}",
                label_visibility="collapsed",
            )
            if new_page != st.session_state.current_page:
                set_viewer_page(new_page)
                st.rerun()

        with nav_c3:
            if st.button(
                "Next ▶",
                use_container_width=True,
                disabled=st.session_state.current_page >= st.session_state.page_count,
            ):
                set_viewer_page(st.session_state.current_page + 1)
                st.rerun()

        with nav_c4:
            if st.session_state.active_referenced_pages:
                primary_p = st.session_state.active_referenced_pages[0]
                if st.button(
                    f"🎯 Cited (P.{primary_p})",
                    use_container_width=True,
                    help="Jump to primary cited page",
                ):
                    set_viewer_page(primary_p)
                    st.rerun()

        # Multi-page Citation Quick-Jump Pills
        if st.session_state.active_referenced_pages:
            st.write("**📍 Cited in Latest Ruling:**")
            pill_cols = st.columns(len(st.session_state.active_referenced_pages) + 1)
            for idx, p in enumerate(st.session_state.active_referenced_pages):
                with pill_cols[idx]:
                    btn_type = (
                        "primary" if p == st.session_state.current_page else "secondary"
                    )
                    if st.button(
                        f"📄 Page {p}",
                        key=f"pill_p_{p}_{idx}",
                        type=btn_type,
                        use_container_width=True,
                    ):
                        set_viewer_page(p)
                        st.rerun()

        # Only apply highlights and diagram framing if a ruling has actively cited this page
        is_page_cited = (
            bool(st.session_state.active_highlights)
            or bool(st.session_state.active_highlight_bboxes)
        ) and (
            not st.session_state.active_referenced_pages
            or st.session_state.current_page in st.session_state.active_referenced_pages
        )
        active_hl_texts = (
            st.session_state.active_highlights
            if (st.session_state.show_highlights and is_page_cited)
            else None
        )
        active_hl_rects = (
            st.session_state.active_highlight_bboxes.get(
                st.session_state.current_page, []
            )
            if (st.session_state.show_highlights and is_page_cited)
            else None
        )
        # Only frame diagrams when the question specifically asks about visual elements/setup
        should_highlight_images = (
            st.session_state.show_diagram_frames
            and is_page_cited
            and st.session_state.get("is_visual_query", False)
        )

        # Render PDF Page with Highlights
        hl_count = 0
        img_count = 0
        try:
            with st.spinner("Rendering page..."):
                page_png, hl_count, img_count = render_page_with_highlights(
                    st.session_state.pdf_bytes,
                    page_num=st.session_state.current_page,
                    highlight_texts=active_hl_texts,
                    highlight_rects=active_hl_rects,
                    highlight_images=should_highlight_images,
                    dpi=150,
                    game_name=st.session_state.game_name,
                )
            try:
                st.image(page_png, width="stretch")
            except TypeError:
                st.image(page_png, use_container_width=True)
        except Exception as e:
            st.error(f"⚠️ Error rendering page {st.session_state.current_page}: {e}")

        # Page summary footer caption
        hl_info = []
        if st.session_state.show_highlights and hl_count > 0:
            hl_info.append(f"🟡 {hl_count} text highlights")
        if st.session_state.show_diagram_frames and img_count > 0:
            hl_info.append(f"🟠 {img_count} diagram frames")
        caption_str = (
            f"Page {st.session_state.current_page} of {st.session_state.page_count}"
        )
        if hl_info:
            caption_str += f" • {' • '.join(hl_info)}"
        st.caption(caption_str)

    # ==========================================
    # RIGHT COLUMN: RULES JUDGE CHAT
    # ==========================================
    with col_chat:
        st.markdown("#### 💬 Rules Assistant")

        # Scrollable Chat Container
        chat_container = st.container(height=540)
        with chat_container:
            for m_idx, msg in enumerate(st.session_state.messages):
                with st.chat_message(msg["role"]):
                    msg_text = format_message_text(msg.get("content", ""))
                    st.markdown(msg_text)

                    # If assistant message contains referenced pages, provide jump buttons
                    ref_pages = msg.get("referenced_pages", [])
                    if not ref_pages and msg["role"] == "assistant":
                        extracted = [
                            int(p)
                            for p in re.findall(
                                r"(?:Page|P\.)\s*(\d+)", msg_text, re.IGNORECASE
                            )
                        ]
                        ref_pages = list(dict.fromkeys(extracted))

                    if msg["role"] == "assistant" and ref_pages:
                        p_cols = st.columns(len(ref_pages) + 1)
                        for p_idx, p in enumerate(ref_pages):
                            with p_cols[p_idx]:
                                if st.button(
                                    f"🔍 View Page {p}",
                                    key=f"msg_btn_{m_idx}_{p}_{p_idx}",
                                    help=f"Jump PDF viewer to Page {p}",
                                ):
                                    set_viewer_page(p)
                                    if msg.get("highlight_bboxes"):
                                        st.session_state.active_highlight_bboxes = msg[
                                            "highlight_bboxes"
                                        ]
                                    if msg.get("highlight_snippets"):
                                        st.session_state.active_highlights = msg[
                                            "highlight_snippets"
                                        ]
                                    st.rerun()

                    # Expandable excerpts
                    if msg.get("excerpts"):
                        with st.expander("📚 View Referenced Excerpts"):
                            for e_idx, chunk in enumerate(msg["excerpts"], 1):
                                st.markdown(f"**Excerpt {e_idx}:**")
                                st.text(chunk)

        # Chat Input at Bottom of Column
        if prompt := st.chat_input(
            f"Ask a rules question about {st.session_state.game_name}..."
        ):
            # Display user message
            with chat_container:
                with st.chat_message("user"):
                    st.markdown(prompt)
            st.session_state.messages.append({"role": "user", "content": prompt})

            # Process with assistant
            with chat_container:
                with st.chat_message("assistant"):
                    status_container = st.status(
                        "Consulting the rulebook...", expanded=True
                    )
                    try:
                        initial_input = {
                            "messages": [HumanMessage(content=prompt)],
                            "game_name": st.session_state.game_name,
                            "rulebook_filename": st.session_state.rulebook_filename,
                            "rulebook_text": st.session_state.rulebook_text,
                        }
                        run_config = {
                            "configurable": {
                                **st.session_state.config.get("configurable", {}),
                                "rulebook_doc": st.session_state.get("rulebook_doc"),
                            }
                        }

                        for event in st.session_state.app.stream(
                            initial_input, config=run_config
                        ):
                            for node_name, state_update in event.items():
                                if node_name == "orchestrator":
                                    intent = state_update.get("query_intent", "")
                                    status_container.write(
                                        f"🧠 **Orchestrator:** Analyzing query intent: *{intent}*"
                                    )
                                elif node_name == "knowledge_extractor":
                                    chunks = state_update.get("relevant_chunks", [])
                                    status_container.write(
                                        f"📖 **Knowledge Extractor:** Retrieved {len(chunks)} relevant rulebook sections."
                                    )
                                elif node_name == "rules_judge":
                                    status_container.write(
                                        "⚖️ **Rules Judge:** Formulated definitive ruling with citations."
                                    )

                        final_state = st.session_state.app.get_state(run_config).values

                        response_text = format_message_text(
                            final_state.get(
                                "final_answer",
                                "Sorry, I could not determine an answer.",
                            )
                        )
                        excerpts = final_state.get("relevant_chunks", [])
                        ref_pages = final_state.get("referenced_pages", [])
                        if not ref_pages:
                            extracted = [
                                int(p)
                                for p in re.findall(
                                    r"(?:Page|P\.)\s*(\d+)",
                                    response_text,
                                    re.IGNORECASE,
                                )
                            ]
                            ref_pages = list(dict.fromkeys(extracted))

                        hl_snippets = final_state.get("highlight_snippets", [])
                        hl_bboxes = final_state.get("highlight_bboxes", {})

                        status_container.update(
                            label="Ruling complete!", state="complete", expanded=False
                        )

                        # Update session active highlights and referenced pages
                        st.session_state.active_highlights = hl_snippets
                        st.session_state.active_highlight_bboxes = hl_bboxes
                        st.session_state.active_referenced_pages = ref_pages
                        st.session_state.is_visual_query = final_state.get(
                            "is_visual_query", False
                        )

                        # Auto-snap left viewer to primary referenced page
                        if ref_pages:
                            set_viewer_page(ref_pages[0])

                        # Append to chat messages
                        st.session_state.messages.append(
                            {
                                "role": "assistant",
                                "content": response_text,
                                "referenced_pages": ref_pages,
                                "highlight_snippets": hl_snippets,
                                "highlight_bboxes": hl_bboxes,
                                "excerpts": excerpts,
                            }
                        )

                        st.rerun()

                    except Exception as e:
                        status_container.update(
                            label="An error occurred", state="error", expanded=True
                        )
                        error_msg = f"An error occurred while evaluating rules: {e}"
                        st.error(error_msg)
                        st.session_state.messages.append(
                            {"role": "assistant", "content": error_msg}
                        )
