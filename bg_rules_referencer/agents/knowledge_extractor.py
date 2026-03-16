from typing import Any, Dict

from .base import AgentState, BaseAgent


class KnowledgeExtractorAgent(BaseAgent):
    """
    Simulates parsing the rulebook into chunks and doing an in-memory
    vector search to find the chunks relevant to the user's question.
    """

    name: str = "knowledge_extractor"

    def __call__(self, state: AgentState) -> Dict[str, Any]:
        print(f"--- {self.name.replace('_', ' ').capitalize()} Agent ---")
        # Stub: Pretend we found relevant chunks
        return {"relevant_chunks": ["Stub chunk 1", "Stub chunk 2"]}
