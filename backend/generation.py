from fastapi import APIRouter, HTTPException

from backend.book_plan import build_book_plan
from backend.llm import ask_json, llm
from backend.prompts import KINDS, KIND_PROMPTS, PLAN_PROMPT, THEORY_COMMON, TOPIC_PROMPT
from backend.schemas import BookGoal, Goal, ModuleRequest, TopicRequest

router = APIRouter(tags=["generation"])


@router.post("/api/plan/book")
def plan_book(body: BookGoal):
    return build_book_plan(ask_json, body.goal, body.level, body.book_id)


@router.post("/api/plan")
def plan(body: Goal):
    return ask_json(PLAN_PROMPT, f"Цель: {body.goal}\nУровень: {body.level}", "topics", 4000)


@router.post("/api/topic")
def topic(body: TopicRequest):
    user = (f"Цель курса: {body.goal}\nУровень: {body.level}\n"
            f"Размер курса: {body.size or 'не указан'}\nВсе темы курса: {'; '.join(body.topics)}\n"
            f"Разбей на модули тему: {body.topic}\nКратко о теме: {body.summary}")
    data = ask_json(TOPIC_PROMPT, user, "modules", 3000)
    for module in data["modules"]:
        if module.get("kind") not in KINDS:
            module["kind"] = "concept"
        if module.get("also") not in KINDS or module["also"] == module["kind"]:
            module["also"] = ""
    return data


@router.post("/api/theory")
def theory(body: ModuleRequest):
    kind = body.kind if body.kind in KINDS else "concept"
    system = THEORY_COMMON + "\n\n" + KIND_PROMPTS[kind]
    if body.also in KINDS and body.also != kind:
        system += "\n\nУчти требования второго типа:\n" + KIND_PROMPTS[body.also]
    user = (f"Цель курса: {body.goal}\nУровень: {body.level}\nТема: {body.topic}\n"
            f"Модули темы по порядку: {'; '.join(body.modules)}\n"
            f"Напиши теорию для модуля: {body.module}\nКратко о модуле: {body.summary}")
    text, reason = llm(system, user, 5000, effort="medium")
    if not text:
        raise HTTPException(502, "Модель вернула пустой ответ")
    if reason == "length":
        text += "\n\n*Текст обрезан из-за лимита токенов. Нажмите «Сгенерировать заново» или разбейте модуль на части.*"
    return {"theory": text}
