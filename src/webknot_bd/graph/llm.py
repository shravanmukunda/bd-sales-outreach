"""Optional Ollama structured-output calls. Callers fall back to the baseline on any failure."""

from __future__ import annotations

from collections.abc import Callable

from pydantic import BaseModel

from webknot_bd.config import logger, settings


def structured_invoke(schema: type[BaseModel], prompt: str) -> BaseModel:
    from langchain_ollama import ChatOllama

    model = ChatOllama(
        model=settings.ollama_model,
        temperature=0,
        base_url=settings.ollama_base_url,
    )
    return model.with_structured_output(schema).invoke(prompt)


def _coerce(schema: type[BaseModel], raw: object) -> BaseModel:
    if isinstance(raw, schema):
        return raw
    return schema.model_validate(raw)


def invoke_or_baseline(
    schema: type[BaseModel],
    prompt: str,
    baseline: Callable[[], BaseModel],
    *,
    enabled: bool | None = None,
    check: Callable[[BaseModel], None] | None = None,
) -> tuple[BaseModel, bool]:
    """Call the chat model twice at most, then use `baseline`.

    The second value is true when the baseline was used after both attempts failed.
    `enabled` defaults to `settings.use_llm`. When it is false the model is not called.
    `check` runs after a schema-valid reply and may raise to reject that reply.
    """
    use_model = settings.use_llm if enabled is None else enabled
    if not use_model:
        return baseline(), False
    for attempt in (1, 2):
        try:
            value = _coerce(schema, structured_invoke(schema, prompt))
            if check is not None:
                check(value)
            return value, False
        except Exception:
            logger.warning(
                "Structured output failed on attempt %s",
                attempt,
                exc_info=True,
            )
    logger.warning("Structured output failed twice; using the baseline")
    return baseline(), True
