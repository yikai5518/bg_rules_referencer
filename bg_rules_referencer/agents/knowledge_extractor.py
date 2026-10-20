import re
from typing import Any, Dict, List, Tuple

from .base import AgentState, BaseAgent


def parse_pages(text: str) -> List[Tuple[int, str]]:
    """
    Parses rulebook text into (page_number, page_text) tuples.
    Detects [Page X] or --- Page X --- headers.
    """
    pattern = r"(?:\[Page (\d+)\]|---\s*Page\s*(\d+)\s*---)"
    splits = re.split(pattern, text)
    if len(splits) == 1:
        # No page markers found; treat as single page 1
        return [(1, text.strip())]

    pages = []
    # re.split with two capture groups returns: [pre_text, g1, g2, content, g1, g2, content, ...]
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
) -> List[Dict[str, Any]]:
    """
    Splits a single page into chunks, ensuring every chunk retains its page number.
    """
    paragraphs = [p.strip() for p in re.split(r"\n\s*\n", page_text) if p.strip()]
    if not paragraphs:
        # Fallback if no paragraph breaks
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


def score_chunk(chunk_text: str, search_terms: List[str], full_query: str) -> float:
    """
    Scores a chunk based on term frequency and query matching.
    """
    chunk_lower = chunk_text.lower()
    score = 0.0

    # Boost for exact match of user's query or intent phrase
    if full_query and full_query.lower() in chunk_lower:
        score += 12.0

    # Score each keyword
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
    preserving exact page numbers for authoritative referencing.
    """

    name: str = "knowledge_extractor"
    max_chunks: int = 4

    def __call__(self, state: AgentState) -> Dict[str, Any]:
        print(f"--- {self.name.replace('_', ' ').capitalize()} Agent ---")

        rulebook_text = state.rulebook_text
        if not rulebook_text or not rulebook_text.strip():
            print("Notice: No rulebook text found in state.")
            return {
                "relevant_chunks": [
                    "No rulebook text is currently loaded. Please upload a rulebook PDF first."
                ],
                "referenced_pages": [],
            }

        # Build search terms from query, keywords, and intent
        search_terms = list(state.keywords) if state.keywords else []
        last_query = ""

        if state.messages:
            last_query = str(state.messages[-1].content)
            query_words = re.findall(r"\b[A-Za-z0-9_-]+\b", last_query)
            search_terms.extend([w.lower() for w in query_words if len(w) > 3])

        if state.query_intent:
            intent_words = re.findall(r"\b[A-Za-z0-9_-]+\b", state.query_intent)
            search_terms.extend([w.lower() for w in intent_words if len(w) > 3])

        unique_terms = list(dict.fromkeys(search_terms))

        # Parse pages and chunk
        pages = parse_pages(rulebook_text)
        all_chunks = []
        for page_num, page_content in pages:
            page_chunks = chunk_page(
                page_num, page_content, max_chunk_size=1100, overlap=200
            )
            all_chunks.extend(page_chunks)

        print(f"Parsed {len(pages)} pages into {len(all_chunks)} chunks.")

        # Score chunks
        scored_chunks = []
        for chunk in all_chunks:
            s = score_chunk(chunk["text"], unique_terms, last_query)
            scored_chunks.append((s, chunk))

        # Sort descending by relevance score
        scored_chunks.sort(key=lambda x: x[0], reverse=True)

        # Select top chunks (positive score or fallback to top 2)
        top_items = [chunk for score, chunk in scored_chunks if score > 0][
            : self.max_chunks
        ]

        if not top_items and all_chunks:
            top_items = all_chunks[:2]

        top_chunks_formatted = [item["formatted"] for item in top_items]
        highlight_snippets = [item["text"] for item in top_items]
        referenced_pages = sorted(list({item["page"] for item in top_items}))

        print(
            f"Selected {len(top_chunks_formatted)} relevant chunks referencing pages: {referenced_pages}"
        )
        return {
            "relevant_chunks": top_chunks_formatted,
            "highlight_snippets": highlight_snippets,
            "referenced_pages": referenced_pages,
        }
