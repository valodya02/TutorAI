import json
import logging
import os
from time import perf_counter

from fastapi import HTTPException
from groq import Groq, RateLimitError

logger = logging.getLogger(__name__)
MODEL = os.getenv("MODEL", "openai/gpt-oss-120b")


def llm(system, user, max_tokens, effort="low", json_mode=False):
    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        raise HTTPException(503, "Не задан GROQ_API_KEY")
    client = Groq(api_key=api_key)
    extra = {"response_format": {"type": "json_object"}} if json_mode else {}
    started = perf_counter()
    try:
        resp = client.chat.completions.create(
            model=MODEL,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            max_completion_tokens=max_tokens,
            reasoning_effort=effort,
            **extra,
        )
    except RateLimitError as e:
        wait = e.response.headers.get("retry-after")
        hint = f"Повторите через {wait} с." if wait else "Повторите через минуту."
        raise HTTPException(429, f"Лимит токенов Groq. {hint}")
    except Exception:
        logger.exception("LLM generation failed")
        raise HTTPException(502, "Ошибка генерации. Повторите запрос позже.")
    choice = resp.choices[0]
    logger.info("LLM request completed model=%s duration_seconds=%.3f finish_reason=%s", MODEL, perf_counter() - started, choice.finish_reason)
    return (choice.message.content or "").strip(), choice.finish_reason


def ask_json(system, user, key, max_tokens=3000):
    text, _ = llm(system, user, max_tokens, json_mode=True)
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        raise HTTPException(502, "Неполный ответ модели (не хватило токенов). Повторите запрос.")
    if not isinstance(data, dict) or not data.get(key):
        raise HTTPException(502, "Модель вернула пустой результат")
    return data
