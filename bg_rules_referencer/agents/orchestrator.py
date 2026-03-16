from typing import Any, Dict

from .base import AgentState, BaseAgent


class OrchestratorAgent(BaseAgent):
    """
    Analyzes the user's question, identifies the board game,
    and determines the intent.
    """

    name: str = "orchestrator"

    def __call__(self, state: AgentState) -> Dict[str, Any]:
        print(f"--- {self.name.capitalize()} Agent ---")
        # Stub: Pretend we identified a game
        return {"game_name": "Stubbed Game"}
