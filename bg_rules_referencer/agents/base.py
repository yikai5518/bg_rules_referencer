import operator
from abc import ABC, abstractmethod
from typing import Annotated, Any, Dict, List, Optional

from langchain_core.messages import BaseMessage
from pydantic import BaseModel, Field


class AgentState(BaseModel):
    """
    The state shared between agents in the LangGraph workflow.
    """

    messages: Annotated[List[BaseMessage], operator.add] = Field(default_factory=list)
    game_name: Optional[str] = None
    rulebook_text: Optional[str] = None
    relevant_chunks: List[str] = Field(default_factory=list)
    final_answer: Optional[str] = None


class BaseAgent(BaseModel, ABC):
    """
    Abstract base class for all board game referencer agents.
    Using Pydantic BaseModel allows for easy configuration of prompts, LLMs, etc.
    """

    name: str

    @abstractmethod
    def __call__(self, state: AgentState) -> Dict[str, Any]:
        """
        Executes the agent's logic.
        Must return a dictionary containing updates to the AgentState.
        """
        pass
