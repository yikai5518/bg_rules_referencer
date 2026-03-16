from typing import Any, Dict

from langchain_google_genai import ChatGoogleGenerativeAI
from pydantic import BaseModel, Field

from .base import AgentState, BaseAgent


class GameIntent(BaseModel):
    game_name: str = Field(
        description="The name of the board game the user is asking about. If none is found, return an empty string."
    )


class OrchestratorAgent(BaseAgent):
    """
    Analyzes the user's question, identifies the board game,
    and determines the intent.
    """

    name: str = "orchestrator"
    model_name: str = "gemini-2.5-flash"

    def __call__(self, state: AgentState) -> Dict[str, Any]:
        print(f"--- {self.name.capitalize()} Agent ---")

        # Get the latest message (user query)
        if not state.messages:
            return {"game_name": None}

        last_message = state.messages[-1].content

        # Check for API Key
        from bg_rules_referencer.settings import settings

        if not settings.google_api_key:
            print("Warning: GOOGLE_API_KEY not found in settings.")
            # Fallback to stub for testing if no key is present yet
            return {"game_name": "Catan"}

        # Initialize the LLM
        llm = ChatGoogleGenerativeAI(
            model=self.model_name, api_key=settings.google_api_key
        )

        # Create structured output chain
        structured_llm = llm.with_structured_output(GameIntent)

        # Invoke the LLM
        response = structured_llm.invoke(
            f"Extract the board game name from this question: {last_message}"
        )

        print(f"Game Name: {response.game_name}")

        # Update state
        return {"game_name": response.game_name if response.game_name else None}
