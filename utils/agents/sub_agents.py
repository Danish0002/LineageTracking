"""
Sub-agent definitions with LLM guardrails
File: utils/agents/sub_agents.py
"""
import logging
from typing import List, Dict, Any

from langchain_core.messages import SystemMessage, HumanMessage, BaseMessage

from config.settings import settings
from services.llm_client import get_databricks_client
from utils.agents.prompts import CURRENT_TRACE_PROMPT, HISTORICAL_SEARCH_PROMPT, REFUSAL_MESSAGE
from utils.agents.guardrails import LineageTopicGuardrail


logger = logging.getLogger("SubAgents")

# Initialize guardrail once (singleton pattern)
try:
    guardrail = LineageTopicGuardrail()
    logger.info("Guardrail initialized successfully")
except Exception as e:
    logger.error(f"Failed to initialize guardrail: {e}")
    guardrail = None


def get_llm():
    """
    Returns shared OpenAI client configured for Databricks Claude endpoint.
    """
    return get_databricks_client()


def _invoke_llm(client: Any, messages: List[BaseMessage]) -> str:
    """
    Helper function to invoke the LLM with LangChain messages

    Args:
        client: OpenAI client instance
        messages: List of LangChain messages

    Returns:
        Response content as string
    """
    # Convert LangChain messages to OpenAI format
    formatted_messages = []
    for msg in messages:
        if isinstance(msg, SystemMessage):
            formatted_messages.append({
                "role": "system",
                "content": msg.content
            })
        elif isinstance(msg, HumanMessage):
            formatted_messages.append({
                "role": "user",
                "content": msg.content
            })

    response = client.chat.completions.create(
        model=settings.DATABRICKS_LLM_MODEL or "databricks-claude-opus-4-5",
        messages=formatted_messages,
        max_tokens=5000,
        temperature=0.3
    )

    return response.choices[0].message.content


def validate_with_guardrail(question: str) -> tuple[bool, str]:
    """
    Validate question using LLM guardrail.

    Args:
        question: User's question

    Returns:
        (is_valid, refusal_message_if_invalid)
    """
    if not guardrail:
        logger.warning("Guardrail not initialized, allowing all questions")
        return True, None

    # Create minimal state for guardrail
    from langchain_core.messages import HumanMessage as LCHumanMessage

    mock_state = {
        "messages": [LCHumanMessage(content=question)]
    }

    try:
        # Call guardrail's before_agent method
        result = guardrail.before_agent(mock_state, None)

        # If guardrail returns block instruction
        if result and result.get("jump_to") == "end":
            return False, REFUSAL_MESSAGE

        return True, None

    except Exception as e:
        logger.error(f"Guardrail validation error: {e}")
        # Fail open - allow question if guardrail errors
        return True, None


def current_trace_agent(context: str, question: str) -> str:
    """
    Handles questions about the active/current lineage trace.

    Args:
        context: Formatted context with edges, samples, metadata
        question: User's question

    Returns:
        Answer string
    """
    # Validate with guardrail
    is_valid, refusal_msg = validate_with_guardrail(question)
    if not is_valid:
        logger.warning(f"Current trace agent: Question blocked by guardrail")
        return refusal_msg

    try:
        llm = get_llm()

        system_prompt = CURRENT_TRACE_PROMPT.format(context=context)

        messages = [
            SystemMessage(content=system_prompt),
            HumanMessage(content=question)
        ]

        return _invoke_llm(llm, messages)

    except Exception as e:
        logger.error(f"Current trace agent error: {e}")
        return f"Error analyzing current trace: {str(e)}"


def historical_search_agent(context: str, question: str) -> str:
    """
    Handles questions about past traces and historical searches.

    Args:
        context: Historical trace context from vector store
        question: User's question

    Returns:
        Answer string
    """
    # Validate with guardrail
    is_valid, refusal_msg = validate_with_guardrail(question)
    if not is_valid:
        logger.warning(f"Historical search agent: Question blocked by guardrail")
        return refusal_msg

    try:
        llm = get_llm()

        system_prompt = HISTORICAL_SEARCH_PROMPT.format(context=context)

        messages = [
            SystemMessage(content=system_prompt),
            HumanMessage(content=question)
        ]

        return _invoke_llm(llm, messages)

    except Exception as e:
        logger.error(f"Historical search agent error: {e}")
        return f"Error searching history: {str(e)}"