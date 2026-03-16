from typing import Any, Dict

from .base import AgentState, BaseAgent


class LibrarianAgent(BaseAgent):
    """
    Simulates searching the web and downloading the official rulebook PDF.
    """

    name: str = "librarian"

    def __call__(self, state: AgentState) -> Dict[str, Any]:
        print(f"--- {self.name.capitalize()} Agent ---")
        # Stub: Pretend we downloaded and extracted text
        return {"rulebook_text": "Stubbed rulebook content..."}
