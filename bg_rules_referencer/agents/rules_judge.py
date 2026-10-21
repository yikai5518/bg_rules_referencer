import re
from typing import Any

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_google_genai import ChatGoogleGenerativeAI

from .base import AgentState, BaseAgent


class RulesJudgeAgent(BaseAgent):
    """
    Formulates an accurate and authoritative ruling based strictly on the
    relevant rulebook chunks extracted for the active game, with mandatory page citations.
    """

    name: str = "rules_judge"
    model_name: str = "gemini-2.5-flash"

    def __call__(self, state: AgentState) -> dict[str, Any]:
        print(f"--- {self.name.replace('_', ' ').capitalize()} Agent ---")

        if not state.messages:
            return {"final_answer": "No question was provided."}

        last_question = str(state.messages[-1].content)
        game_name = state.game_name or "the board game"
        chunks = state.relevant_chunks or []
        referenced_pages = state.referenced_pages or []

        if not chunks or (len(chunks) == 1 and "No rulebook text" in chunks[0]):
            return {
                "final_answer": (
                    "⚠️ No rulebook is currently loaded. Please upload a rulebook PDF "
                    "to ask questions about this game's rules."
                )
            }

        chunks_context = "\n\n---\n\n".join(chunks)

        from bg_rules_referencer.settings import settings

        pages_str = (
            ", ".join(f"Page {p}" for p in referenced_pages)
            if referenced_pages
            else "Rulebook"
        )

        if not settings.google_api_key:
            print(
                "Warning: GOOGLE_API_KEY not found. Returning extracted excerpts directly."
            )
            # Group by page for clean reference
            formatted_chunks = []
            for chunk in chunks:
                match = re.search(r"\[Page (\d+)\]", chunk)
                p_label = f"Page {match.group(1)}" if match else "Rulebook"
                clean_text = re.sub(r"\[Page \d+\]\s*", "", chunk).strip()
                formatted_chunks.append(f"**📄 {p_label}:**\n{clean_text}")

            formatted_answer = (
                f"### Rulebook Reference ({game_name})\n\n"
                f"Relevant sections found for your question:\n\n"
                + "\n\n---\n\n".join(formatted_chunks)
                + f"\n\n**📖 Referenced Pages:** {pages_str}\n\n"
                f"*(Note: Configure GOOGLE_API_KEY to enable full AI synthesized rulings.)*"
            )
            return {"final_answer": formatted_answer}

        try:
            model_name = settings.rules_judge_model or "gemini-3.8-flash"
            llm = ChatGoogleGenerativeAI(
                model=model_name,
                api_key=settings.google_api_key,
                temperature=0.2,
            )

            system_prompt = (
                f"You are an authoritative and precise Board Game Rules Judge.\n"
                f"Game: {game_name}\n\n"
                f"Your task is to answer the user's question accurately and strictly based ONLY on the "
                f"official rulebook excerpts provided below.\n\n"
                f"Rules:\n"
                f"1. Ground every statement in the excerpts.\n"
                f"2. MANDATORY PAGE CITATIONS: Always cite the exact page number(s) (e.g. 'According to Page 3...', '(Page 5)') "
                f"where each rule or condition is found.\n"
                f"3. Cite specific terminology, steps, or conditions from the text.\n"
                f"4. If the excerpts do not contain sufficient information to answer definitively, "
                f"state that clearly and summarize what the text does say.\n"
                f"5. Conclude your answer with a line listing all referenced pages in bold:\n"
                f"   **📖 Referenced Pages:** Page X"
            )

            user_prompt = (
                f"Official Rulebook Excerpts:\n{chunks_context}\n\n"
                f"Player Question: {last_question}"
            )

            print("Formulating final ruling via LLM...")
            response = llm.invoke(
                [
                    SystemMessage(content=system_prompt),
                    HumanMessage(content=user_prompt),
                ]
            )

            # Safely extract text string from response.content (handles strings, lists of content blocks, dicts)
            raw_content = response.content
            if isinstance(raw_content, str):
                final_text = raw_content
            elif isinstance(raw_content, list):
                parts = []
                for item in raw_content:
                    if isinstance(item, dict) and "text" in item:
                        parts.append(str(item["text"]))
                    elif isinstance(item, str):
                        parts.append(item)
                    elif hasattr(item, "text"):
                        parts.append(str(getattr(item, "text")))
                    else:
                        parts.append(str(item))
                final_text = "".join(parts).strip()
            elif isinstance(raw_content, dict) and "text" in raw_content:
                final_text = str(raw_content["text"]).strip()
            else:
                final_text = str(raw_content).strip()

            # Parse any pages cited directly in the LLM answer
            cited_pages = []
            for p in re.findall(r"(?:Page|P\.)\s*(\d+)", final_text, re.IGNORECASE):
                val = int(p)
                if val not in cited_pages:
                    cited_pages.append(val)

            merged_pages = cited_pages if cited_pages else referenced_pages
            return {"final_answer": final_text, "referenced_pages": merged_pages}

        except Exception as e:
            err_str = str(e)
            print(
                f"Notice: Rules Judge LLM invocation failed ({err_str}). Returning extracted excerpts."
            )
            formatted_chunks = []
            for chunk in chunks:
                match = re.search(r"\[Page (\d+)\]", chunk)
                p_label = f"Page {match.group(1)}" if match else "Rulebook"
                clean_text = re.sub(r"\[Page \d+\]\s*", "", chunk).strip()
                formatted_chunks.append(f"**📄 {p_label}:**\n{clean_text}")

            if "402" in err_str or "RESOURCE_EXHAUSTED" in err_str:
                notice = "*(Note: AI synthesis is paused because your Google API prepayment credits are depleted. Displaying raw verified rulebook excerpts above.)*"
            elif "404" in err_str or "NOT_FOUND" in err_str:
                notice = f"*(Note: Model `{model_name}` was not found. Please check model settings.)*"
            else:
                notice = f"*(Notice: AI synthesis fallback active: {err_str})*"

            fallback_answer = (
                f"### Rulebook Reference ({game_name})\n\n"
                f"Here are the relevant excerpts extracted from your uploaded rulebook regarding your question:\n\n"
                + "\n\n---\n\n".join(formatted_chunks)
                + f"\n\n**📖 Referenced Pages:** {pages_str}\n\n"
                + notice
            )
            return {"final_answer": fallback_answer}
