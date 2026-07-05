"""
Supervisor agent for routing to sub-agents
"""
import logging
from typing import Dict, List

from langchain_core.messages import SystemMessage, HumanMessage

from utils.agents.prompts import SUPERVISOR_PROMPT
from utils.agents.sub_agents import current_trace_agent, historical_search_agent
from services.llm_client import get_databricks_client
from config.settings import settings


logger = logging.getLogger("Supervisor")


def get_llm():
    """
    Return the shared Databricks LLM client.
    """
    return get_databricks_client()


def route_question(question: str, has_active_trace: bool) -> str:
    """
    Route the question to appropriate agent.

    Args:
        question: User's question
        has_active_trace: Whether there's an active trace loaded

    Returns:
        Agent name: "current_trace_agent" or "historical_search_agent"
    """
    try:
        llm = get_llm()

        routing_context = f"""
        Question: {question}
        Active Trace Available: {'YES' if has_active_trace else 'NO'}
        """

        response = llm.chat.completions.create(
            model=settings.DATABRICKS_LLM_MODEL or "databricks-claude-opus-4-5",
            messages=[
                {"role": "system", "content": SUPERVISOR_PROMPT},
                {"role": "user", "content": routing_context}
            ],
            max_tokens=50,
            temperature=0.1
        )
        decision = response.choices[0].message.content.strip().lower()

        if "historical_search_agent" in decision:
            logger.info("Routing to: historical_search_agent")
            return "historical_search_agent"
        else:
            logger.info("Routing to: current_trace_agent")
            return "current_trace_agent"

    except Exception as e:
        logger.error(f"Routing error: {e}")
        return "current_trace_agent" if has_active_trace else "historical_search_agent"


def execute_agent(
        agent_name: str,
        current_context: str,
        historical_context: str,
        question: str
) -> str:
    """
    Execute the selected agent with appropriate context.
    """
    logger.info(f"Executing Agent: {agent_name}")
    logger.info(f"Question: {question[:100]}...")

    if agent_name == "current_trace_agent":
        logger.info("Current Trace Agent: Processing active lineage data")
        response = current_trace_agent(current_context, question)
        logger.info(f"Current Trace Agent: Response generated ({len(response)} chars)")
        return response

    elif agent_name == "historical_search_agent":
        logger.info("Historical Search Agent: Searching past traces")

        # If comparison detected, merge current + historical context
        import re
        compare_match = re.search(r"compar", question.lower())

        if compare_match and current_context and "No active lineage trace" not in current_context:
            # MERGE both contexts for comparison
            combined_context = historical_context + "\n\n=== CURRENT TRACE DATA ===\n\n" + current_context
            logger.info(f"Comparison mode: Merged context ({len(combined_context)} chars)")
            response = historical_search_agent(combined_context, question)
        else:
            # Normal historical search only
            response = historical_search_agent(historical_context, question)

        logger.info(f"Historical Search Agent: Response generated ({len(response)} chars)")
        return response

    else:
        logger.error(f"Unknown agent selected: {agent_name}")
        return "Unknown agent selected"