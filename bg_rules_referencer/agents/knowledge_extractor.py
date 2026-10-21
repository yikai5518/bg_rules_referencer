import os
import re
from typing import Any

from langchain_core.runnables import RunnableConfig

from llama_index.core import VectorStoreIndex
from llama_index.core.schema import TextNode
from llama_index.embeddings.gemini import GeminiEmbedding
from llama_index.retrievers.bm25 import BM25Retriever

from .base import AgentState, BaseAgent


def parse_pages(text: str) -> list[tuple[int, str]]:
    """
    Parses rulebook text into (page_number, page_text) tuples.
    Detects [Page X] or --- Page X --- headers.
    """
    pattern = r"(?:\[Page (\d+)\]|---\s*Page\s*(\d+)\s*---)"
    splits = re.split(pattern, text)
    if len(splits) == 1:
        return [(1, text.strip())]

    pages = []
    i = 1
    while i < len(splits):
        p1 = splits[i]
        p2 = splits[i + 1] if i + 1 < len(splits) else None
        page_num_str = p1 or p2
        page_num = (
            int(page_num_str)
            if page_num_str and page_num_str.isdigit()
            else len(pages) + 1
        )
        content = splits[i + 2].strip() if i + 2 < len(splits) else ""
        if content:
            pages.append((page_num, content))
        i += 3

    return pages if pages else [(1, text.strip())]


def chunk_page(
    page_num: int, page_text: str, max_chunk_size: int = 1000, overlap: int = 150
) -> list[dict[str, Any]]:
    """
    Splits a single page into chunks, ensuring every chunk retains its page number.
    """
    paragraphs = [p.strip() for p in re.split(r"\n\s*\n", page_text) if p.strip()]
    if not paragraphs:
        if len(page_text) <= max_chunk_size:
            return [
                {
                    "page": page_num,
                    "text": page_text,
                    "formatted": f"[Page {page_num}]\n{page_text}",
                }
            ]
        chunks = []
        for j in range(0, len(page_text), max_chunk_size - overlap):
            slice_text = page_text[j : j + max_chunk_size]
            chunks.append(
                {
                    "page": page_num,
                    "text": slice_text,
                    "formatted": f"[Page {page_num}]\n{slice_text}",
                }
            )
        return chunks

    chunks = []
    current_paras = []
    current_length = 0

    for para in paragraphs:
        p_len = len(para)
        if current_length + p_len > max_chunk_size and current_paras:
            content = "\n\n".join(current_paras)
            chunks.append(
                {
                    "page": page_num,
                    "text": content,
                    "formatted": f"[Page {page_num}]\n{content}",
                }
            )
            if len(current_paras[-1]) <= overlap:
                current_paras = [current_paras[-1], para]
                current_length = len(current_paras[0]) + p_len
            else:
                current_paras = [para]
                current_length = p_len
        else:
            current_paras.append(para)
            current_length += p_len

    if current_paras:
        content = "\n\n".join(current_paras)
        chunks.append(
            {
                "page": page_num,
                "text": content,
                "formatted": f"[Page {page_num}]\n{content}",
            }
        )

    return chunks


def score_chunk(chunk_text: str, search_terms: list[str], full_query: str) -> float:
    """
    Scores a chunk based on term frequency and query matching.
    """
    chunk_lower = chunk_text.lower()
    score = 0.0

    if full_query and full_query.lower() in chunk_lower:
        score += 12.0

    for term in search_terms:
        term_clean = term.lower().strip()
        if not term_clean:
            continue
        matches = len(re.findall(r"\b" + re.escape(term_clean) + r"\b", chunk_lower))
        score += matches * 2.5

    return score


class KnowledgeExtractorAgent(BaseAgent):
    """
    Extracts the most relevant chunks from the uploaded rulebook text,
    leveraging LlamaIndex hybrid retrieval and Docling structural layout coordinates.
    """

    name: str = "knowledge_extractor"
    max_chunks: int = 4

    def _build_nodes_from_text(self, rulebook_text: str) -> list[TextNode]:
        """
        Fallback node builder when a pre-parsed Docling RulebookDocument is not in state.
        """
        pages = parse_pages(rulebook_text)
        nodes: list[TextNode] = []
        counter = 0

        for page_num, page_content in pages:
            lines = [ln.strip() for ln in page_content.split("\n") if ln.strip()]
            for line in lines:
                counter += 1
                words = re.findall(r"[A-Za-z]+", line)
                is_heading = (
                    len(words) <= 7
                    and not line.rstrip(")").endswith((".", "!", "?", ","))
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
                        for w in words
                    )
                ) or bool(re.match(r"^player turn\b", line, re.IGNORECASE))

                nodes.append(
                    TextNode(
                        text=line,
                        id_=f"node_fb_{page_num}_{counter}",
                        metadata={
                            "page_no": page_num,
                            "label": "section_header" if is_heading else "text",
                            "is_heading": is_heading,
                            "is_visual": False,
                            "bboxes": [],
                        },
                    )
                )
        return nodes

    def __call__(
        self, state: AgentState, config: RunnableConfig | None = None
    ) -> dict[str, Any]:
        print(f"--- {self.name.replace('_', ' ').capitalize()} Agent ---")

        rulebook_doc = None
        if config and "configurable" in config:
            rulebook_doc = config["configurable"].get("rulebook_doc")
        if rulebook_doc is None:
            rulebook_doc = getattr(state, "rulebook_doc", None)
        rulebook_text = state.rulebook_text or ""

        # Retrieve or construct LlamaIndex nodes
        nodes: list[TextNode] = []
        if (
            rulebook_doc is not None
            and hasattr(rulebook_doc, "nodes")
            and rulebook_doc.nodes
        ):
            nodes = rulebook_doc.nodes
            print(f"Using {len(nodes)} pre-parsed Docling nodes.")
        elif rulebook_text.strip():
            nodes = self._build_nodes_from_text(rulebook_text)
            print(f"Constructed {len(nodes)} fallback nodes from rulebook text.")
        else:
            print("Notice: No rulebook text or document found in state.")
            return {
                "relevant_chunks": [
                    "No rulebook text is currently loaded. Please upload a rulebook PDF first."
                ],
                "referenced_pages": [],
                "highlight_snippets": [],
                "highlight_bboxes": {},
            }

        # Build clean search terms and query
        stop_words = {
            "what",
            "when",
            "where",
            "which",
            "who",
            "whom",
            "whose",
            "why",
            "how",
            "does",
            "have",
            "with",
            "this",
            "that",
            "these",
            "those",
            "from",
            "they",
            "will",
            "about",
            "there",
            "their",
            "rules",
            "rule",
            "board",
            "game",
            "play",
            "player",
            "players",
            "turn",
            "turns",
            "round",
            "rounds",
            "phase",
            "phases",
            "step",
            "steps",
            "during",
            "many",
            "much",
            "each",
            "every",
            "other",
            "your",
            "then",
            "also",
            "into",
            "onto",
            "only",
            "such",
            "some",
            "more",
            "most",
            "less",
            "least",
            "than",
            "been",
            "were",
            "being",
            "could",
            "would",
            "should",
            "shall",
            "must",
            "might",
            "need",
            "used",
            "using",
            "take",
            "takes",
            "taking",
            "make",
            "makes",
            "making",
        }

        search_terms = [
            k.lower() for k in (state.keywords or []) if k.lower() not in stop_words
        ]
        last_query = ""
        if state.messages:
            last_query = str(state.messages[-1].content)
            query_words = re.findall(r"\b[A-Za-z0-9_-]+\b", last_query)
            search_terms.extend(
                [
                    w.lower()
                    for w in query_words
                    if len(w) > 3 and w.lower() not in stop_words
                ]
            )

        if state.query_intent:
            intent_words = re.findall(r"\b[A-Za-z0-9_-]+\b", state.query_intent)
            search_terms.extend(
                [
                    w.lower()
                    for w in intent_words
                    if len(w) > 3 and w.lower() not in stop_words
                ]
            )

        unique_terms = list(dict.fromkeys(search_terms))
        search_query_str = (
            f"{last_query} {state.query_intent or ''} {' '.join(unique_terms)}".strip()
        )

        # Hybrid retrieval with LlamaIndex BM25 + Gemini Vector Index
        matched_nodes: list[tuple[float, TextNode]] = []
        try:
            bm25_retriever = BM25Retriever.from_defaults(
                nodes=nodes, similarity_top_k=min(12, len(nodes))
            )
            bm25_results = bm25_retriever.retrieve(search_query_str)
            for idx, res in enumerate(bm25_results):
                # Rank score based on BM25 retrieval rank
                score = 10.0 / (idx + 1)
                matched_nodes.append((score, res.node))
        except Exception as e:
            print(f"Notice: BM25 retriever warning: {e}")

        # Vector Index with Gemini Embedding if API key is present
        api_key = os.environ.get("GOOGLE_API_KEY")
        if api_key:
            try:
                embed_model = GeminiEmbedding(model_name="models/text-embedding-004")
                vector_index = VectorStoreIndex(nodes=nodes, embed_model=embed_model)
                vec_retriever = vector_index.as_retriever(
                    similarity_top_k=min(8, len(nodes))
                )
                vec_results = vec_retriever.retrieve(search_query_str)
                for idx, res in enumerate(vec_results):
                    score = 15.0 / (idx + 1)
                    matched_nodes.append((score, res.node))
            except Exception as e:
                print(f"Notice: Vector embedding retrieval fallback (using BM25): {e}")

        # If no retrieval results yet, use keyword term frequency scoring
        if not matched_nodes:
            for node in nodes:
                sc = score_chunk(node.text, unique_terms, last_query)
                if sc > 0:
                    matched_nodes.append((sc, node))

        # Deduplicate and aggregate scores by node id
        aggregated_scores: dict[str, tuple[float, TextNode]] = {}
        for sc, node in matched_nodes:
            if node.id_ in aggregated_scores:
                existing_sc, n = aggregated_scores[node.id_]
                aggregated_scores[node.id_] = (existing_sc + sc, n)
            else:
                aggregated_scores[node.id_] = (sc, node)

        ranked_nodes = sorted(
            aggregated_scores.values(), key=lambda x: x[0], reverse=True
        )

        if not ranked_nodes:
            ranked_nodes = [(1.0, n) for n in nodes[: self.max_chunks]]

        top_candidates = [n for _, n in ranked_nodes[: self.max_chunks]]

        # Format relevant chunks for Rules Judge with [Page X] tags
        top_chunks_formatted = [
            f"[Page {n.metadata.get('page_no', 1)}]\n{n.text}" for n in top_candidates
        ]
        referenced_pages = sorted(
            list({int(n.metadata.get("page_no", 1)) for n in top_candidates})
        )

        # Extract precise highlight snippets and bounding boxes
        highlight_snippets: list[str] = []
        highlight_bboxes: dict[int, list[tuple[float, float, float, float]]] = {}

        for score, node in ranked_nodes:
            if score <= 0:
                continue

            page_no = int(node.metadata.get("page_no", 1))
            if page_no not in referenced_pages:
                continue

            # Skip headings, titles, page banners
            if node.metadata.get("is_heading", False):
                print(f"[highlight-select] Skip heading node: {node.text!r}")
                continue

            # Skip narrative play examples
            text_clean = node.text.strip()
            if re.match(
                r"^(?:example\b|for example\b|[A-Z][a-z]+ plays\b|[A-Z][a-z]+ draws\b|[A-Z][a-z]+ sends\b)",
                text_clean,
                re.IGNORECASE,
            ):
                print(f"[highlight-select] Skip example node: {text_clean!r}")
                continue

            if len(text_clean) < 15:
                continue

            # Add to highlight snippets
            snippet_entry = f"[Page {page_no}] {text_clean}"
            if snippet_entry not in highlight_snippets and len(highlight_snippets) < 6:
                highlight_snippets.append(snippet_entry)

            # Add exact coordinates if available
            bboxes = node.metadata.get("bboxes", [])
            if bboxes:
                if page_no not in highlight_bboxes:
                    highlight_bboxes[page_no] = []
                for b in bboxes:
                    if b not in highlight_bboxes[page_no]:
                        highlight_bboxes[page_no].append(tuple(b))

        # Diagram/Image visual highlights if visual query is flagged
        if (
            state.is_visual_query
            and rulebook_doc is not None
            and hasattr(rulebook_doc, "page_elements")
        ):
            for p in referenced_pages:
                for elem in rulebook_doc.page_elements.get(p, []):
                    if elem.get("is_visual") and elem.get("bboxes"):
                        if p not in highlight_bboxes:
                            highlight_bboxes[p] = []
                        highlight_bboxes[p].extend(elem["bboxes"])

        print(
            f"[highlight-select] Generated {len(highlight_snippets)} snippet(s) across pages: {referenced_pages}"
        )
        print(
            f"[highlight-select] Coordinate bboxes for pages: {list(highlight_bboxes.keys())}"
        )

        return {
            "relevant_chunks": top_chunks_formatted,
            "highlight_snippets": highlight_snippets,
            "highlight_bboxes": highlight_bboxes,
            "referenced_pages": referenced_pages,
        }
