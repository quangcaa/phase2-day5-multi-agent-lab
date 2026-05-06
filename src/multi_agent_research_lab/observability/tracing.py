"""Tracing hooks with LangSmith integration.

LangGraph automatically sends traces to LangSmith when the following
environment variables are set:
  - LANGCHAIN_TRACING_V2=true
  - LANGCHAIN_API_KEY=<your langsmith api key>
  - LANGCHAIN_PROJECT=<project name>

This module also provides a lightweight local span context manager
for additional manual instrumentation.
"""

import os
import logging
from collections.abc import Iterator
from contextlib import contextmanager
from time import perf_counter
from typing import Any

from multi_agent_research_lab.core.config import get_settings

logger = logging.getLogger(__name__)


def configure_langsmith_tracing() -> None:
    """Set LangSmith env vars so LangGraph auto-traces.

    Call this once at startup (e.g., in ``_init()``).
    """

    settings = get_settings()
    if settings.langsmith_api_key:
        os.environ["LANGCHAIN_TRACING_V2"] = "true"
        os.environ["LANGCHAIN_API_KEY"] = settings.langsmith_api_key
        os.environ["LANGCHAIN_PROJECT"] = settings.langsmith_project
        logger.info(
            "LangSmith tracing enabled  project=%s",
            settings.langsmith_project,
        )
    else:
        logger.info("LangSmith tracing disabled – no LANGSMITH_API_KEY set")


@contextmanager
def trace_span(name: str, attributes: dict[str, Any] | None = None) -> Iterator[dict[str, Any]]:
    """Minimal span context used for manual instrumentation.

    Works independently of LangSmith – useful for local profiling.
    """

    started = perf_counter()
    span: dict[str, Any] = {"name": name, "attributes": attributes or {}, "duration_seconds": None}
    try:
        yield span
    finally:
        span["duration_seconds"] = perf_counter() - started
        logger.debug("Span %s completed in %.3fs", name, span["duration_seconds"])
