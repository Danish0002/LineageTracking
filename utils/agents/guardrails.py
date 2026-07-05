"""
LLM-based Guardrails using OpenAI via Databricks endpoint
File: utils/agents/guardrails.py
"""
import logging
from typing import Any, Dict, Optional

from langchain.agents.middleware import AgentMiddleware, AgentState, hook_config
from langgraph.runtime import Runtime

from services.llm_client import get_databricks_client
from config.settings import settings
from utils.agents.prompts import TOPIC_VALIDATION_PROMPT, REFUSAL_MESSAGE


logger = logging.getLogger("Guardrails")

class LineageTopicGuardrail(AgentMiddleware):
    """LLM-based guardrail that validates if questions are about data lineage."""

    def __init__(self):
        super().__init__()

        # Use shared OpenAI client with Databricks endpoint
        self.classifier = get_databricks_client()

        logger.info("LineageTopicGuardrail initialized with Databricks Claude endpoint")

    @hook_config(can_jump_to=["end"])
    def before_agent(self, state: AgentState, runtime: Runtime) -> Dict[str, Any] | None:
        """Validate question topic before agent starts processing."""

        # Get the latest user message
        if not state.get("messages"):
            return None

        last_message = state["messages"][-1]

        # Only validate user messages
        if not hasattr(last_message, 'type') or last_message.type != "human":
            return None

        question = last_message.content

        # Very short questions might be follow-ups in conversation
        if len(question.split()) <= 3:
            logger.info(f"Guardrail: Allowing short follow-up question: {question[:50]}")
            return None

        logger.info(f"Guardrail: Validating question: {question[:100]}")

        try:
            # Call LLM classifier via Databricks endpoint
            prompt = TOPIC_VALIDATION_PROMPT.format(question=question)

            response = self.classifier.chat.completions.create(
                model=settings.DATABRICKS_LLM_MODEL or "databricks-claude-opus-4-5",
                messages=[
                    {"role": "user", "content": prompt}
                ],
                max_tokens=10,  # Only need one word response
                temperature=0.0  # Deterministic
            )

            classification = response.choices[0].message.content.strip().upper()

            logger.info(f"Guardrail: Classification result: {classification}")

            if "OFFTOPIC" in classification:
                logger.warning(f"Guardrail: BLOCKED off-topic question: {question[:100]}")

                # Block execution and return refusal message
                return {
                    "messages": [{
                        "role": "assistant",
                        "content": REFUSAL_MESSAGE
                    }],
                    "jump_to": "end"
                }

            # Allow lineage-related questions
            logger.info(f"Guardrail: ALLOWED lineage question")
            return None

        except Exception as e:
            logger.error(f"Guardrail: Error during classification: {e}")
            # On error, allow the question (fail open to avoid blocking legitimate queries)
            logger.warning("Guardrail: Allowing question due to classification error")
            return None


# Export for easy import
__all__ = ['LineageTopicGuardrail', 'REFUSAL_MESSAGE']