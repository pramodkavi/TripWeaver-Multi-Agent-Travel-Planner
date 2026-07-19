"""LLM setup, kept in one place so the model is easy to swap via env vars."""

import os
from functools import lru_cache

from dotenv import load_dotenv
from langchain_openai import ChatOpenAI

load_dotenv(override=True)

OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")


@lru_cache(maxsize=1)
def get_llm() -> ChatOpenAI:
    # Built on first use so importing this module never requires a key.
    return ChatOpenAI(
        model=OPENAI_MODEL,
        api_key=os.getenv("OPENAI_API_KEY"),
        temperature=0,
    )
