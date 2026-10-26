from fastapi import APIRouter, HTTPException

from backend.book_plan import build_book_plan
from backend.books import get_section_text
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

    # Обработка module: может быть строкой или dict с полем book
    module_title = body.module
    book_info = None
    if isinstance(body.module, dict):
        module_title = body.module.get("title", "")
        book = body.module.get("book")
        if book and isinstance(book, dict):
            book_info = {
                "section": book.get("section"),
                "page_start": book.get("page_start"),
                "page_end": book.get("page_end"),
                "book_id": body.module.get("book_id"),
            }

    # Извлекаем заголовки модулей (могут быть объекты с book)
    module_titles = []
    for m in body.modules:
        if isinstance(m, dict):
            module_titles.append(m.get("title", ""))
        else:
            module_titles.append(str(m))
    user = (f"Цель курса: {body.goal}\nУровень: {body.level}\nТема: {body.topic}\n"
            f"Модули темы по порядку: {'; '.join(module_titles)}\n"
            f"Напиши теорию для модуля: {module_title}\nКратко о модуле: {body.summary}")

    # Добавляем информацию и текст учебника, если есть
    if book_info:
        book_id = book_info["book_id"]
        if book_id:
            try:
                section = book_info["section"]
                text = get_section_text(book_id, section)
                toc_entry = book_info.get("title", f"Раздел (с. {book_info['page_start']}–{book_info['page_end']})")
                user += (f"\n\nИсточник: учебник, раздел «{toc_entry}» (с. {book_info['page_start']}–{book_info['page_end']}):\n"
                        f"{text}\n\nИспользуй этот текст как основу для теории.")
            except HTTPException:
                pass  # Если учебник не прочитать, просто продолжаем без него
            except Exception:
                pass  # Любые другие ошибки игнорируем

    text, reason = llm(system, user, 5000, effort="medium")
    if not text:
        raise HTTPException(502, "Модель вернула пустой ответ")
    if reason == "length":
        text += "\n\n*Текст обрезан из-за лимита токенов. Нажмите «Сгенерировать заново» или разбейте модуль на части.*"
    return {"theory": text}
