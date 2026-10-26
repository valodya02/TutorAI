import json
import os
import re
import time
import uuid
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from groq import Groq, RateLimitError
from pydantic import BaseModel
from backend.books import router as books_router
from backend.book_plan import build_book_plan

load_dotenv()
client = Groq(api_key=os.getenv("GROQ_API_KEY"))
MODEL = os.getenv("MODEL", "openai/gpt-oss-120b")
ROOT = Path(__file__).resolve().parent.parent
FRONTEND = ROOT / "frontend"
COURSES = ROOT / "data" / "courses"
COURSES.mkdir(parents=True, exist_ok=True)
KINDS = ("concept", "procedure", "facts", "narrative", "creative")
PLAN_PROMPT = """Ты составляешь структуру курса по цели пользователя.
Верни только JSON с полями строго в этом порядке:
{"size": "узкий|средний|широкий", "scope": "...", "prerequisites": ["..."], "topics": [{"title": "...", "summary": "..."}]}

Сначала определи size - размер запроса:
- узкий: одна теорема, понятие, приём или формула. Темы: 1-2.
- средний: один раздел дисциплины или навык. Темы: 3-8.
- широкий: целая дисциплина или профессия. Темы: 8-15.
Количество тем должно соответствовать size. Больше тем - не значит лучше: не раздувай план.

Примеры:
- "Теорема Штейнера" -> size узкий, 1 тема (формулировка, доказательство, применение и задачи уместятся в её модулях).
- "Термодинамика" -> size средний, около 6 тем.
- "Физика с нуля" -> size широкий, около 15 тем.

Правила:
- scope: одним-двумя предложениями: как ты понял цель, что входит в курс и что не входит.
- В topics только то, что нужно для самой цели. Фоновые знания (то, что читатель должен знать до начала) не делай темами, а перечисли в prerequisites. Если уровень читателя не покрывает prerequisites, добавь первой темой краткое повторение только недостающего.
- Не включай в план то, что читатель с указанным уровнем уже знает.
- summary: одно предложение.
Отвечай на языке цели."""

TOPIC_PROMPT = """Ты разбиваешь тему курса на учебные модули.
Верни только JSON:
{"modules": [{"title": "...", "summary": "...", "kind": "concept", "also": ""}]}
Правила:
- Один модуль - один связный подтопик, который изучается и проверяется отдельно.
- Количество модулей зависит от размера темы и курса:
  - курс узкий или тема простая: 2-4 модуля;
  - обычная тема: 4-7 модулей;
  - большая и сложная тема: 7-10 модулей.
  Не раздувай: если тему можно закрыть меньшим числом модулей, делай меньше.
- Порядок от простого к сложному, модули не пересекаются и не повторяют другие темы курса.
- summary: одно предложение.
- kind - основной тип материала модуля:
  concept - идеи, теории, модели (нужны объяснения и аналогии);
  procedure - навык, алгоритм, метод решения (нужны упражнения);
  facts - то, что запоминают: термины, словарь, классификации (нужны карточки и тесты);
  narrative - история, литература, право, общественные науки: рассказ о процессах, причинах и следствиях (нужны объяснения, источники, спорные вопросы);
  creative - создание продукта: дизайн, текст, проект (нужны проект и обратная связь).
  Исторические и гуманитарные темы это narrative, а не facts.
- also - второй тип, если модуль смешанный (например, предел: concept + procedure). Иначе пустая строка.
Отвечай на языке цели."""

THEORY_COMMON = """Ты пишешь учебный материал для одного модуля курса на уровне хорошего университетского учебника.
Стиль: связный текст, как глава хорошего учебника, а не конспект и не план.
- Начни с вступления в 1-2 абзаца: о чём модуль, зачем он нужен, как связан с предыдущим материалом.
- Излагай абзацами. Между частями делай переходы фразами вроде «Далее рассмотрим...», «Отсюда следует...», «Чтобы понять это, вернёмся к...».
- Заголовки используй редко: не больше 3-4 заголовков второго уровня (##) на весь модуль, без номеров, только когда меняется крупная часть материала. Не нумеруй разделы и не делай заголовок из каждого шага.
- Списки и таблицы только там, где они явно нужнее текста (шаги процедуры, короткое сравнение), и только после фразы, объясняющей, зачем они. Таблица никогда не открывает модуль.
Формат: Markdown. Формулы только в LaTeX: строчные в $...$, выносные в $$...$$ на отдельных строках. Другие разделители формул не используй. Не оборачивай ответ в блок кода и не используй JSON.
Правила:
- Глубина соответствует уровню читателя. Не залезай в материал соседних модулей, но ссылайся на уже изученное.
- Только достоверные факты. Если не уверен, так и скажи, не придумывай.
- Объём: не больше 1000 слов, плотно и без воды.
- В конце одной строкой: 2-3 известных учебника по теме (только авторы и названия, без страниц)."""

KIND_PROMPTS = {
    "concept": """Тип модуля: концептуальный (идеи, теории, модели).
Порядок мысли: интуиция и аналогии, затем точные определения и формулировки, обоснование (вывод или доказательство, если оно принято в дисциплине и посильно для уровня, иначе идея), разобранные примеры, границы применимости и частые заблуждения. Это порядок изложения, а не список разделов: вплетай всё в связный текст. Закончи 3-4 вопросами на понимание (здесь допустим список).""",
    "procedure": """Тип модуля: процедурный (навык, алгоритм, метод решения).
Кратко объясни идею, затем изложи процедуру (здесь допустим нумерованный список шагов). Примеры по нарастанию самостоятельности: полностью разобранный, затем с пропущенными шагами для читателя. Код и команды давай рабочими, в блоках кода с указанием языка. Расскажи о типичных сбоях и как их диагностировать, закончи чек-листом самопроверки. Теории не больше необходимого.""",
    "facts": """Тип модуля: декларативный (то, что запоминают: термины, словарь, классификации).
Сначала в 1-2 абзацах объясни, как устроен материал и по какому принципу он группируется. Затем излагай группы связным текстом, показывая связи между фактами. Ключевые термины выделяй жирным и давай определение с примером прямо в тексте. Короткое сравнение допустимо таблицей, но только после пояснения. Добавь мнемоники. Закончи блоком «Запомнить»: 8-12 пар «вопрос - ответ», пригодных для карточек.""",
    "narrative": """Тип модуля: повествовательный (история, литература, право, общественные науки).
Это рассказ, а не справочник. Покажи контекст и предпосылки, затем ход событий или развитие идеи с главными действующими лицами, причины и следствия, значение и связь с последующим. Опирайся на источники и называй их, если знаешь точно. Если у учёных есть спор, изложи позиции. Даты и имена вплетай в текст, не выноси в таблицы. В конце коротко: хронология (до 8 пунктов) и ключевые понятия.""",
    "creative": """Тип модуля: творческий (дизайн, письмо, создание продукта).
Объясни принципы и приёмы, сопровождая их примерами удачного и неудачного. Разбери 1-2 образца: что сделано хорошо и почему. Назови критерии качества, по ним потом оценивается работа. Закончи заданием-проектом: цель, ограничения, что сдать, критерии оценки.""",
}

app = FastAPI()
app.include_router(books_router)

class Goal(BaseModel):
    goal: str
    level: str = "начинающий"

class BookGoal(BaseModel):
    goal: str
    level: str = "начинающий"
    book_id: str

class TopicRequest(BaseModel):
    goal: str
    level: str = "начинающий"
    size: str = ""  # размер курса: узкий/средний/широкий
    topics: list[str]  # все темы курса, для контекста
    topic: str  # раскрываемая тема
    summary: str = ""
    
class ModuleRequest(BaseModel):
    goal: str
    level: str = "начинающий"
    topic: str
    modules: list[str]  # все модули темы по порядку
    module: str
    summary: str = ""
    kind: str = "concept"
    also: str = ""

class Course(BaseModel):
    goal: str
    level: str
    plan: dict


def llm(system, user, max_tokens, effort="low", json_mode=False):
    extra = {"response_format": {"type": "json_object"}} if json_mode else {}
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
    except Exception as e:
        raise HTTPException(502, f"Ошибка генерации: {e}")
    choice = resp.choices[0]
    return (choice.message.content or "").strip(), choice.finish_reason


def ask_json(system, user, key, max_tokens=3000):
    text, _ = llm(system, user, max_tokens, json_mode=True)
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        raise HTTPException(502, "Неполный ответ модели (не хватило токенов). Повторите запрос.")
    if not data.get(key):
        raise HTTPException(502, "Модель вернула пустой результат")
    return data

@app.post("/api/plan/book")
def plan_book(body: BookGoal):
    goal = body.goal.strip()
    if not goal:
        raise HTTPException(400, "Введите цель обучения")
    return build_book_plan(ask_json, goal, body.level, body.book_id)

@app.post("/api/plan")
def plan(body: Goal):
    goal = body.goal.strip()
    if not goal:
        raise HTTPException(400, "Введите цель обучения")
    return ask_json(PLAN_PROMPT, f"Цель: {goal}\nУровень: {body.level}", "topics", 4000)


@app.post("/api/topic")
def topic(body: TopicRequest):
    user = (
        f"Цель курса: {body.goal}\nУровень: {body.level}\n"
        f"Размер курса: {body.size or 'не указан'}\n"
        f"Все темы курса: {'; '.join(body.topics)}\n"
        f"Разбей на модули тему: {body.topic}\nКратко о теме: {body.summary}"
    )
    data = ask_json(TOPIC_PROMPT, user, "modules", 3000)
    for m in data["modules"]:
        if m.get("kind") not in KINDS:
            m["kind"] = "concept"
        if m.get("also") not in KINDS or m["also"] == m["kind"]:
            m["also"] = ""
    return data


@app.post("/api/theory")
def theory(body: ModuleRequest):
    kind = body.kind if body.kind in KINDS else "concept"
    system = THEORY_COMMON + "\n\n" + KIND_PROMPTS[kind]
    if body.also in KINDS and body.also != kind:
        system += (
            "\n\nМодуль смешанный. Основа - первый тип, но учти и требования второго:\n\n"
            + KIND_PROMPTS[body.also]
        )
    user = (
        f"Цель курса: {body.goal}\nУровень: {body.level}\n"
        f"Тема: {body.topic}\nМодули темы по порядку: {'; '.join(body.modules)}\n"
        f"Напиши теорию для модуля: {body.module}\nКратко о модуле: {body.summary}"
    )
    text, reason = llm(system, user, 5000, effort="medium")
    if not text:
        raise HTTPException(502, "Модель вернула пустой ответ")
    if reason == "length":
        text += "\n\n*Текст обрезан из-за лимита токенов. Нажмите «Сгенерировать заново» или разбейте модуль на части.*"
    return {"theory": text}

def course_path(course_id: str) -> Path:
    if not re.fullmatch(r"[0-9a-f]{8}", course_id):
        raise HTTPException(404, "План не найден")
    return COURSES / f"{course_id}.json"


def read_course(course_id: str) -> dict:
    path = course_path(course_id)
    if not path.exists():
        raise HTTPException(404, "План не найден")
    return json.loads(path.read_text(encoding="utf-8"))


def write_course(data: dict) -> None:
    course_path(data["id"]).write_text(
        json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8"
    )


@app.post("/api/courses")
def save_course(body: Course):
    data = {
        "id": uuid.uuid4().hex[:8],
        "created": time.strftime("%Y-%m-%d %H:%M"),
        **body.model_dump(),
    }
    write_course(data)
    return {"id": data["id"]}


@app.put("/api/courses/{course_id}")
def update_course(course_id: str, body: Course):
    data = read_course(course_id)
    data.update(body.model_dump())
    write_course(data)
    return {"ok": True}


@app.get("/api/courses")
def list_courses():
    files = sorted(COURSES.glob("*.json"), key=lambda f: f.stat().st_mtime, reverse=True)
    result = []
    for f in files:
        d = json.loads(f.read_text(encoding="utf-8"))
        result.append({k: d[k] for k in ("id", "goal", "level", "created")})
    return result


@app.get("/api/courses/{course_id}")
def get_course(course_id: str):
    return read_course(course_id)


@app.delete("/api/courses/{course_id}")
def delete_course(course_id: str):
    read_course(course_id)  # 404, если нет
    course_path(course_id).unlink()
    return {"ok": True}


# после всех /api-маршрутов
app.mount("/", StaticFiles(directory=FRONTEND, html=True))