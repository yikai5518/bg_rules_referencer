import re
from typing import Any, Dict

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

    def __call__(self, state: AgentState) -> Dict[str, Any]:
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
            llm = ChatGoogleGenerativeAI(
                model=self.model_name,
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

            final_text = response.content
            return {"final_answer": final_text}

        except Exception as e:
            print(
                f"Notice: Rules Judge LLM invocation failed ({e}). Returning extracted excerpts."
            )
            formatted_chunks = []
            for chunk in chunks:
                match = re.search(r"\[Page (\d+)\]", chunk)
                p_label = f"Page {match.group(1)}" if match else "Rulebook"
                clean_text = re.sub(r"\[Page \d+\]\s*", "", chunk).strip()
                formatted_chunks.append(f"**📄 {p_label}:**\n{clean_text}")

            fallback_answer = (
                f"### Rulebook Reference ({game_name})\n\n"
                f"Here are the relevant excerpts extracted from your uploaded rulebook regarding your question:\n\n"
                + "\n\n---\n\n".join(formatted_chunks)
                + f"\n\n**📖 Referenced Pages:** {pages_str}\n\n"
                f"*(Notice: AI synthesis unavailable due to API limit: {e})*"
            )
            return {"final_answer": fallback_answer}
