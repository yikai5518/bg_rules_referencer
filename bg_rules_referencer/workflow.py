from langgraph.graph import END, START, StateGraph

from bg_rules_referencer.agents.base import AgentState
from bg_rules_referencer.agents.knowledge_extractor import KnowledgeExtractorAgent
from bg_rules_referencer.agents.librarian import LibrarianAgent
from bg_rules_referencer.agents.orchestrator import OrchestratorAgent
from bg_rules_referencer.agents.rules_judge import RulesJudgeAgent


def build_workflow():
    # Initialize the graph with the Pydantic state schema
    workflow = StateGraph(AgentState)

    # Instantiate agents
    orchestrator = OrchestratorAgent()
    librarian = LibrarianAgent()
    knowledge_extractor = KnowledgeExtractorAgent()
    rules_judge = RulesJudgeAgent()

    # Add nodes using the callable agents
    workflow.add_node("orchestrator", orchestrator)
    workflow.add_node("librarian", librarian)
    workflow.add_node("knowledge_extractor", knowledge_extractor)
    workflow.add_node("rules_judge", rules_judge)

    # Define the edges (the flow)
    workflow.add_edge(START, "orchestrator")
    workflow.add_edge("orchestrator", "librarian")
    workflow.add_edge("librarian", "knowledge_extractor")
    workflow.add_edge("knowledge_extractor", "rules_judge")
    workflow.add_edge("rules_judge", END)

    # Compile the graph
    return workflow.compile()


def query_rules(query: str) -> str:
    """
    Main entry point for querying the board game rules helper.
    """
    app = build_workflow()

    from langchain_core.messages import HumanMessage

    # Initialize the state with the user's query
    initial_state = AgentState(messages=[HumanMessage(content=query)])

    # Run the graph
    result = app.invoke(initial_state)

    # Return the final formulated answer
    return result.get("final_answer", "Sorry, I could not determine an answer.")


if __name__ == "__main__":
    # Test the query function
    print("Testing the query function...")
    query = "How do I win in Catan?"
    print(f"User Query: {query}")
    print("\nExecuting Workflow...")
    response = query_rules(query)

    print(f"\nResponse: {response}")
