import re
from typing import Any, Dict, List

from langchain_google_genai import ChatGoogleGenerativeAI
from pydantic import BaseModel, Field

from .base import AgentState, BaseAgent


class QuestionIntent(BaseModel):
    intent: str = Field(
        description="A concise summary of what specific rules, actions, or mechanics the user is asking about."
    )
    keywords: List[str] = Field(
        default_factory=list,
        description="Key terms, concepts, actions, or components to look up in the rulebook.",
    )
    game_name: str = Field(
        default="",
        description="The board game name if identified from the question, or empty string.",
    )


class OrchestratorAgent(BaseAgent):
    """
    Analyzes the user's question, identifies the rules intent and relevant
    gameplay keywords for the uploaded rulebook, without external web searches.
    """

    name: str = "orchestrator"
    model_name: str = "gemini-2.5-flash"

    def __call__(self, state: AgentState) -> Dict[str, Any]:
        print(f"--- {self.name.capitalize()} Agent ---")

        # Get the latest message (user query)
        if not state.messages:
            return {"query_intent": None, "keywords": []}

        last_message = str(state.messages[-1].content)
        current_game = state.game_name or "the board game"

        # Heuristic fallback keywords in case LLM is unavailable or credits are depleted
        words = re.findall(r"\b[A-Za-z0-9_-]+\b", last_message)
        stop_words = {
            "what",
            "when",
            "where",
            "which",
            "does",
            "have",
            "with",
            "this",
            "that",
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
        }
        fallback_keywords = [
            w.lower() for w in words if len(w) > 2 and w.lower() not in stop_words
        ]
        fallback_intent = f"Question regarding: {last_message}"

        # Check for API Key
        from bg_rules_referencer.settings import settings

        if not settings.google_api_key:
            print("Warning: GOOGLE_API_KEY not found. Using heuristic extraction.")
            return {
                "query_intent": fallback_intent,
                "keywords": fallback_keywords,
                "game_name": state.game_name,
            }

        try:
            # Initialize the LLM
            llm = ChatGoogleGenerativeAI(
                model=self.model_name, api_key=settings.google_api_key
            )
            structured_llm = llm.with_structured_output(QuestionIntent)

            print("Analyzing rules intent via LLM...")
            prompt = (
                f"You are an expert board game rules analyst.\n"
                f"Active Game: {current_game}\n"
                f"User Question: {last_message}\n\n"
                f"Extract the specific rules intent, gameplay concepts, and search keywords."
            )
            response: QuestionIntent = structured_llm.invoke(prompt)

            extracted_intent = response.intent or fallback_intent
            extracted_keywords = (
                response.keywords if response.keywords else fallback_keywords
            )
            game_name = state.game_name or (
                response.game_name if response.game_name else None
            )

            print(f"Rules Intent: {extracted_intent}")
            print(f"Keywords: {extracted_keywords}")

            return {
                "query_intent": extracted_intent,
                "keywords": extracted_keywords,
                "game_name": game_name,
            }
        except Exception as e:
            print(
                f"Notice: Orchestrator LLM invocation failed ({e}). Using heuristic extraction."
            )
            return {
                "query_intent": fallback_intent,
                "keywords": fallback_keywords,
                "game_name": state.game_name,
            }
