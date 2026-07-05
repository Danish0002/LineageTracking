"""
Shared Databricks LLM and embedding client.

Centralizes configuration of the Databricks-serving OpenAI client so all LLM
and embedding calls go through a single, business-ready endpoint definition.
"""
from functools import lru_cache
from typing import Any, Dict, List, Optional

from openai import OpenAI

from config.settings import settings
from core.logger import get_logger


logger = get_logger("LLMClient")


class MockEmbeddingData:
    def __init__(self, embedding):
        self.embedding = embedding


class MockEmbeddings:
    def create(self, model, input, **kwargs):
        import random
        # Return a list of floats matching the embedding dimension
        embedding = [random.uniform(-1, 1) for _ in range(settings.DATABRICKS_EMBEDDING_DIMENSION)]
        return type('obj', (object,), {'data': [MockEmbeddingData(embedding)]})


class MockChatCompletionChoiceMessage:
    def __init__(self, content):
        self.content = content


class MockChatCompletionChoice:
    def __init__(self, message):
        self.message = message


class MockChatCompletions:
    def create(self, model, messages, **kwargs):
        # Extract user query
        user_message = ""
        for m in messages:
            if m.get("role") == "user":
                user_message = m.get("content", "")
        
        # Check system prompt contents (passed via system message or context)
        system_content = ""
        for m in messages:
            if m.get("role") == "system":
                system_content = m.get("content", "")
        
        content = ""
        # Classify the type of prompt
        if "supervisor" in system_content.lower() or "routing" in system_content.lower():
            user_msg_lower = user_message.lower()
            if any(kw in user_msg_lower for kw in ["history", "past", "previous", "list", "show all"]):
                content = "historical_search_agent"
            else:
                content = "current_trace_agent"
        elif "topic classifier" in user_message.lower() or "classification:" in user_message.lower():
            # Guardrails classifier
            content = "LINEAGE"
        else:
            # Chatbot responder
            content = f"Here is a mock response from the Record-Level Lineage POC chatbot assistant. You asked: '{user_message}'\n\nThe active lineage trace contains a path from gmpmsd_dev.dv_project_metadata.major_launch_strategy_id down to gmpmsd_dev.dv_strategy_mapping.strategy_guid, spanning 4 nodes across 3 levels. The data consistency is fully matched between ADLS and Snowflake."
        
        choice = MockChatCompletionChoice(MockChatCompletionChoiceMessage(content))
        return type('obj', (object,), {'choices': [choice]})


class MockOpenAI:
    def __init__(self, **kwargs):
        self.embeddings = MockEmbeddings()
        self.chat = type('obj', (object,), {'completions': MockChatCompletions()})()


@lru_cache(maxsize=1)
def get_databricks_client() -> OpenAI:
    """
    Return a singleton OpenAI client configured for the Databricks endpoint.
    """
    if settings.MOCK_MODE:
        logger.info("[MOCK MODE] Returning Mock OpenAI client")
        return MockOpenAI()

    if not settings.DATABRICKS_ACCESS_TOKEN:
        raise ValueError("DATABRICKS_ACCESS_TOKEN is not set in environment/.env")

    if not settings.DATABRICKS_BASE_URL:
        raise ValueError("DATABRICKS_BASE_URL is not set in environment/.env")

    logger.info(
        f"Initializing Databricks OpenAI client for base URL: {settings.DATABRICKS_BASE_URL}"
    )

    return OpenAI(
        api_key=settings.DATABRICKS_ACCESS_TOKEN,
        base_url=settings.DATABRICKS_BASE_URL,
    )


def create_chat_completion(
    messages: List[Dict[str, str]],
    model: Optional[str] = None,
    **kwargs: Any,
):
    """
    Convenience wrapper for chat completion calls against the Databricks LLM.

    Args:
        messages: OpenAI-style messages list.
        model: Optional override for the model name. If not provided, falls back
               to settings.DATABRICKS_LLM_MODEL if present, otherwise the
               default Databricks Claude model.
        **kwargs: Additional parameters forwarded to chat.completions.create.
    """
    client = get_databricks_client()
    # Prefer a configurable model name if present, otherwise sane default.
    default_model = settings.DATABRICKS_LLM_MODEL
    model_name = model or default_model

    return client.chat.completions.create(
        model=model_name,
        messages=messages,
        **kwargs,
    )


def create_embedding(
    text: str,
    model: Optional[str] = None,
):
    """
    Convenience wrapper for embedding calls against the Databricks embedding model.

    Args:
        text: Input text to embed.
        model: Optional override for the embedding model name. If not provided,
               uses settings.DATABRICKS_EMBEDDING_MODEL.
    """
    client = get_databricks_client()
    model_name = model or settings.DATABRICKS_EMBEDDING_MODEL

    return client.embeddings.create(
        model=model_name,
        input=text,
        encoding_format="float",
    )


__all__ = [
    "get_databricks_client",
    "create_chat_completion",
    "create_embedding",
]

