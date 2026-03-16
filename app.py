import uuid

import streamlit as st
from langchain_core.messages import HumanMessage
from langgraph.checkpoint.memory import MemorySaver

from bg_rules_referencer.workflow import build_workflow

st.set_page_config(
    page_title="Board Game Rules Helper",
    page_icon="🎲",
    layout="centered",
    initial_sidebar_state="expanded",
)

# Initialize app and memory in session state
if "app" not in st.session_state:
    st.session_state.memory = MemorySaver()
    st.session_state.app = build_workflow(checkpointer=st.session_state.memory)
    st.session_state.thread_id = str(uuid.uuid4())
    st.session_state.config = {
        "configurable": {"thread_id": st.session_state.thread_id}
    }

# --- Sidebar ---
with st.sidebar:
    st.title("🎲 Board Game Rules")
    st.markdown(
        """
    Welcome! I'm an AI assistant designed to help you quickly find official rules for your favorite board games.

    **How it works:**
    1. Ask a question about a game (e.g., "How do I win in Catan?").
    2. I'll identify the game and double-check with you.
    3. I'll search the web for its official PDF rulebook.
    4. I'll read the rules and provide a precise answer based *only* on the text I found.
    """
    )
    st.markdown("---")
    st.markdown("Built with LangGraph & Gemini")

# --- Main App ---
st.title("Ask a Rules Question ♟️")

# Initialize chat history
if "messages" not in st.session_state:
    st.session_state.messages = []

# Display chat messages from history on app rerun
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

# Check if graph is interrupted / pending confirmation
graph_state = st.session_state.app.get_state(st.session_state.config)
is_interrupted = len(graph_state.next) > 0 and graph_state.next[0] == "librarian"

if is_interrupted:
    game_name = graph_state.values.get("game_name", "Unknown Game")

    with st.chat_message("assistant"):
        st.markdown(
            f"It looks like you are asking about **{game_name}**. Is that correct?"
        )

        col1, col2 = st.columns(2)
        with col1:
            if st.button("Yes, proceed", use_container_width=True, type="primary"):
                # Add confirmation message
                st.session_state.messages.append(
                    {
                        "role": "assistant",
                        "content": f"Confirmed. Looking up rules for {game_name}...",
                    }
                )

                with st.spinner("Consulting the rulebooks..."):
                    # Resume graph by invoking with None (it uses the state stored in the checkpointer)
                    result = st.session_state.app.invoke(
                        None, config=st.session_state.config
                    )

                    response_text = result.get(
                        "final_answer", "Sorry, I could not determine an answer."
                    )
                    st.session_state.messages.append(
                        {"role": "assistant", "content": response_text}
                    )

                # We need to start a fresh thread for the next question to prevent state bleeding
                st.session_state.thread_id = str(uuid.uuid4())
                st.session_state.config = {
                    "configurable": {"thread_id": st.session_state.thread_id}
                }
                st.rerun()

        with col2:
            if st.button("No, let me rephrase", use_container_width=True):
                st.session_state.messages.append(
                    {
                        "role": "assistant",
                        "content": "Okay, please rephrase your question to be clearer.",
                    }
                )
                # Reset thread to cancel the interrupt and start fresh
                st.session_state.thread_id = str(uuid.uuid4())
                st.session_state.config = {
                    "configurable": {"thread_id": st.session_state.thread_id}
                }
                st.rerun()

else:
    # React to user input
    if prompt := st.chat_input("E.g: Can I build a settlement on a harbor in Catan?"):
        # Display user message in chat message container
        with st.chat_message("user"):
            st.markdown(prompt)

        # Add user message to chat history
        st.session_state.messages.append({"role": "user", "content": prompt})

        with st.chat_message("assistant"):
            with st.spinner("Identifying game intent..."):
                try:
                    # Invoke graph (will pause after orchestrator)
                    st.session_state.app.invoke(
                        {"messages": [HumanMessage(content=prompt)]},
                        config=st.session_state.config,
                    )
                    st.rerun()
                except Exception as e:
                    error_msg = f"An error occurred: {e}"
                    st.error(error_msg)
                    st.session_state.messages.append(
                        {"role": "assistant", "content": error_msg}
                    )
