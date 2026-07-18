"""LLM initialization.

Isolated here so the provider/model stays swappable via environment variables
(SRS: provider is the implementer's choice, kept configurable). Defaults to
OpenAI ``gpt-4o-mini``.

The client is built lazily (on first use) so the app can import cleanly even
when credentials are absent; a missing/invalid key then surfaces at call time
where the nodes handle it gracefully rather than crashing at startup.
"""

import os
from functools import lru_cache

from dotenv import load_dotenv
from langchain_openai import ChatOpenAI

load_dotenv(override=True)

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")


@lru_cache(maxsize=1)
def get_llm() -> ChatOpenAI:
    """Return the shared chat LLM, constructing it on first use."""
    return ChatOpenAI(
        model=OPENAI_MODEL,
        api_key=os.getenv("OPENAI_API_KEY"),
        temperature=0,
    )
