import operator
from abc import ABC, abstractmethod
from typing import Annotated, Any

from langchain_core.messages import BaseMessage
from langchain_core.runnables import RunnableConfig
from pydantic import BaseModel, Field


class AgentState(BaseModel):
    """
    The state shared between agents in the LangGraph workflow.
    """

    messages: Annotated[list[BaseMessage], operator.add] = Field(default_factory=list)
    game_name: str | None = None
    rulebook_filename: str | None = None
    rulebook_text: str | None = None
    query_intent: str | None = None
    keywords: list[str] = Field(default_factory=list)
    relevant_chunks: list[str] = Field(default_factory=list)
    highlight_snippets: list[str] = Field(default_factory=list)
    highlight_bboxes: dict[int, list[tuple[float, float, float, float]]] = Field(
        default_factory=dict
    )
    referenced_pages: list[int] = Field(default_factory=list)
    is_visual_query: bool = False
    final_answer: str | None = None


class BaseAgent(BaseModel, ABC):
    """
    Abstract base class for all board game referencer agents.
    Using Pydantic BaseModel allows for easy configuration of prompts, LLMs, etc.
    """

    name: str

    @abstractmethod
    def __call__(
        self, state: AgentState, config: RunnableConfig | None = None
    ) -> dict[str, Any]:
        """
        Executes the agent's logic.
        Must return a dictionary containing updates to the AgentState.
        """
        pass
