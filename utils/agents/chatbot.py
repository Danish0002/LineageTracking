"""
Streamlit UI logic for the AI Lineage Assistant chatbot.

This module encapsulates all chatbot-related UI and interaction code so that
`main.py` stays focused on app wiring and layout.
"""
import streamlit as st

from core.logger import get_logger
from utils.agents.agent import ask_lineage_agent


logger = get_logger("ChatbotUI")


def render_chatbot() -> None:
    """
    Render the AI Lineage Assistant chat interface and handle interactions.
    Relies on `st.session_state` values that are managed by the main app:
      - session_id
      - current_edges
      - samples_with_source
      - filter_value_input
    """
    # -------------------------------------------------------------------------
    # UNIFIED AI ASSISTANT – stable chat with loading state
    # -------------------------------------------------------------------------
    st.markdown("---")
    st.subheader("AI Lineage Assistant")
    st.markdown(
        "Ask me anything about lineage flows, data quality, or search historical traces."
    )

    # Initialize chat state
    if "chat_messages" not in st.session_state:
        st.session_state.chat_messages = []

    if "pending_agent_call" not in st.session_state:
        st.session_state.pending_agent_call = False

    # -------------------------------------------------------------------------
    # Render chat history (single source of truth)
    # -------------------------------------------------------------------------
    for message in st.session_state.chat_messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])

    # -------------------------------------------------------------------------
    # Chat input
    # -------------------------------------------------------------------------
    prompt = st.chat_input(
        "Ask about lineage, data quality, or search history..."
    )

    # -------------------------------------------------------------------------
    # Handle new user prompt
    # -------------------------------------------------------------------------
    if prompt and prompt.strip() and not st.session_state.pending_agent_call:
        # Add user message
        st.session_state.chat_messages.append(
            {
                "role": "user",
                "content": prompt,
            }
        )

        # Add placeholder assistant message
        st.session_state.chat_messages.append(
            {
                "role": "assistant",
                "content": "Thinking...",
            }
        )

        # Mark that agent work is pending
        st.session_state.pending_agent_call = True

        # Rerun so user immediately sees "Thinking..."
        st.rerun()

    # -------------------------------------------------------------------------
    # Execute agent call if pending
    # -------------------------------------------------------------------------
    if st.session_state.pending_agent_call:
        try:
            # Last user question is second-last message
            question = st.session_state.chat_messages[-2]["content"]

            historical_keywords = [
                "history",
                "past",
                "previous",
                "before",
                "earlier",
                "similar",
                "compare",
                "other traces",
                "all traces",
                "find traces",
                "search traces",
                "saved traces",
                "did trace",
                "traced earlier",
            ]

            specific_objects = ["dv_", "tbl_", "vw_", "dim_", "fact_"]
            mentions_specific_object = any(
                obj in question.lower() for obj in specific_objects
            )

            include_historical = (
                any(k in question.lower() for k in historical_keywords)
                or (
                    not st.session_state.get("current_edges")
                    and mentions_specific_object
                )
            )

            response = ask_lineage_agent(
                session_id=st.session_state.session_id,
                question=question,
                edges=st.session_state.get("current_edges", []),
                samples=st.session_state.get("samples_with_source", {}),
                filter_value=st.session_state.get("filter_value_input"),
                include_historical=include_historical,
            )

            # Replace placeholder with real response
            st.session_state.chat_messages[-1]["content"] = response

        except Exception as e:
            logger.error(f"Chatbot error: {e}", exc_info=True)
            st.session_state.chat_messages[-1]["content"] = f"Error: {str(e)}"

        finally:
            st.session_state.pending_agent_call = False
            st.rerun()

    # -------------------------------------------------------------------------
    # Clear chat button
    # -------------------------------------------------------------------------
    if st.session_state.chat_messages:
        col1, col2, col3 = st.columns([3, 1, 3])
        with col2:
            if st.button("Clear Chat"):
                st.session_state.chat_messages = []
                st.session_state.pending_agent_call = False
                st.rerun()


__all__ = ["render_chatbot"]

