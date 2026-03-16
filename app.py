import streamlit as st

from bg_rules_referencer.workflow import query_rules

st.set_page_config(page_title="Board Game Rules Helper", page_icon="🎲")

st.title("🎲 Board Game Rules Helper")
st.write("Ask me any question about the rules of a board game!")

# Initialize chat history
if "messages" not in st.session_state:
    st.session_state.messages = []

# Display chat messages from history on app rerun
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

# React to user input
if prompt := st.chat_input("How do I perform a trade in Catan?"):
    # Display user message in chat message container
    st.chat_message("user").markdown(prompt)
    # Add user message to chat history
    st.session_state.messages.append({"role": "user", "content": prompt})

    with st.spinner("Consulting the rulebooks..."):
        try:
            # Query the backend workflow
            response_text = query_rules(prompt)

            # Display assistant response in chat message container
            with st.chat_message("assistant"):
                st.markdown(response_text)

            # Add assistant response to chat history
            st.session_state.messages.append(
                {"role": "assistant", "content": response_text}
            )

        except Exception as e:
            st.error(f"An error occurred: {e}")
