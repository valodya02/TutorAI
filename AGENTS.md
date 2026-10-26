# TutorAI

AI-репетитор: генерирует план курса и учебную теорию по цели, умеет строить курс по оглавлению загруженного PDF.

## Стек
- Backend: Python 3.14, FastAPI, Uvicorn, Groq SDK, PyMuPDF (`fitz`), Pydantic.
- Frontend: vanilla JS (ES modules), HTML/CSS, marked + DOMPurify + KaTeX с CDN.
- Хранение: JSON-файлы и PDF на диске (`data/`), без БД.
- Тестов, линтеров, Docker и CI нет.

## Команды
```bash
python3 -m venv .venv && . .venv/bin/activate
pip install -r requirements.txt        # сейчас неполный, см. PLAN P0-1
uvicorn backend.app:app --reload --port 8000
# открыть http://127.0.0.1:8000
```
- build: не требуется (статика отдаётся FastAPI).
- test: не настроено (`pytest` отсутствует).
- lint: не настроено.

## Карта репо
- `backend/app.py` — FastAPI-приложение, LLM-промпты, курсы, статика.
- `backend/books.py` — загрузка PDF, оглавление, текст разделов.
- `backend/book_plan.py` — выбор разделов учебника под цель.
- `backend/__pycache__/` — сгенерированное, в git попало ошибочно.
- `frontend/index.html` — единственная страница.
- `frontend/js/app.js` — состояние экрана и сценарии.
- `frontend/js/api.js` — HTTP-клиент курсов.
- `frontend/js/books.js` — UI загрузки и настройки оглавления.
- `frontend/js/views.js` — рендер плана/модуля и Markdown+LaTeX.
- `frontend/css/style.css` — стили, светлая/тёмная тема.
- `data/courses/*.json` — сохранённые курсы (runtime, но закоммичены).
- `data/books/<id>/` — PDF и `book.json` (runtime, но закоммичены).
- `requirements.txt` — Python-зависимости.
- `.env` — секреты (закоммичен, см. PLAN P0-2).

## Конвенции
- Русский UI, сообщения об ошибках и промпты; код и имена — английские.
- Backend: плоские функции-роуты, Pydantic-модели рядом с роутами.
- Frontend: DOM собирается вручную, без фреймворка; `textContent` вместо HTML.
- id курсов/книг — 8 hex-символов, валидируются регуляркой.

## Хочешь X — смотри Y
- Поменять промпт плана/теории → `backend/app.py` (`PLAN_PROMPT`, `TOPIC_PROMPT`, `THEORY_COMMON`, `KIND_PROMPTS`).
- Логику выбора глав PDF → `backend/book_plan.py`.
- Парсинг оглавления → `backend/books.py` (`toc_*`, `parse_page_range`).
- HTTP-вызовы фронтенда → `frontend/js/api.js`, `frontend/js/books.js`.
- Рендер формул/Markdown → `frontend/js/views.js`.
- Архитектура и долг → `docs/ARCHITECTURE.md`; задачи → `docs/PLAN.md`.

## Правила для агентов
- Не коммитить `.env`, `data/`, `__pycache__`, `*.pdf`; не логировать ключи.
- Не менять сгенерированные `data/**` и `backend/__pycache__/**`.
- Не хардкодить модель/ключ: только через env (`GROQ_API_KEY`, `MODEL`).
- Перед PR: приложение стартует, `/api/plan` отвечает, `ruff check`/`pytest` — после их добавления (PLAN P1-4/P2-1).
- Любой новый эндпоинт — с валидацией входа и без утечки текста исключений.
- Секреты и персональные данные в ответах LLM не отправлять наружу.
