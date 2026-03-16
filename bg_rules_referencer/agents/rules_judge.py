from typing import Any, Dict

from .base import AgentState, BaseAgent


class RulesJudgeAgent(BaseAgent):
    """
    Formulates the final answer based strictly on the relevant chunks provided.
    """

    name: str = "rules_judge"

    def __call__(self, state: AgentState) -> Dict[str, Any]:
        print(f"--- {self.name.replace('_', ' ').capitalize()} Agent ---")
        # Stub: Pretend we formulated an answer
        return {"final_answer": "According to the stubbed rules, this is the answer."}
