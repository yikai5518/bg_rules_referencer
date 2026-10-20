from typing import Optional

from langchain_core.messages import HumanMessage
from langgraph.graph import END, START, StateGraph

from bg_rules_referencer.agents.base import AgentState
from bg_rules_referencer.agents.knowledge_extractor import KnowledgeExtractorAgent
from bg_rules_referencer.agents.orchestrator import OrchestratorAgent
from bg_rules_referencer.agents.rules_judge import RulesJudgeAgent


def build_workflow(checkpointer=None):
    """
    Builds the streamlined LangGraph workflow for uploaded rulebooks.
    Graph Flow: START -> orchestrator -> knowledge_extractor -> rules_judge -> END
    """
    workflow = StateGraph(AgentState)

    # Instantiate agents
    orchestrator = OrchestratorAgent()
    knowledge_extractor = KnowledgeExtractorAgent()
    rules_judge = RulesJudgeAgent()

    # Add nodes using the callable agents
    workflow.add_node("orchestrator", orchestrator)
    workflow.add_node("knowledge_extractor", knowledge_extractor)
    workflow.add_node("rules_judge", rules_judge)

    # Define linear execution flow
    workflow.add_edge(START, "orchestrator")
    workflow.add_edge("orchestrator", "knowledge_extractor")
    workflow.add_edge("knowledge_extractor", "rules_judge")
    workflow.add_edge("rules_judge", END)

    if checkpointer:
        return workflow.compile(checkpointer=checkpointer)
    return workflow.compile()


def query_rules(
    query: str,
    rulebook_text: Optional[str] = None,
    game_name: Optional[str] = None,
    rulebook_filename: Optional[str] = None,
) -> str:
    """
    Main entry point for querying the board game rules helper with an uploaded rulebook.
    """
    app = build_workflow()

    # Initialize state with user's query and loaded rulebook
    initial_state = AgentState(
        messages=[HumanMessage(content=query)],
        game_name=game_name or "Board Game",
        rulebook_filename=rulebook_filename,
        rulebook_text=rulebook_text,
    )

    # Run the graph
    result = app.invoke(initial_state)

    # Return the final formulated answer
    return result.get("final_answer", "Sorry, I could not determine an answer.")


if __name__ == "__main__":
    print("Testing the streamlined query workflow...")
    sample_rules = """
    --- Page 1 ---
    Catan Rules:
    To win Catan, a player must be the first to reach 10 victory points on their turn.
    Points are earned by building settlements (1 point each), cities (2 points each),
    holding the Longest Road card (2 points), or holding the Largest Army card (2 points).
    Victory Point development cards also award 1 victory point each.
    """
    query = "How do I win in Catan?"
    print(f"User Query: {query}")
    print("\nExecuting Workflow...")
    response = query_rules(
        query,
        rulebook_text=sample_rules,
        game_name="Catan",
        rulebook_filename="catan_base_rules.pdf",
    )
    print(f"\nResponse: {response}")
