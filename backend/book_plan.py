from backend.books import read_book

PICK_PROMPT = """Ты выбираешь из оглавления учебника разделы, нужные для цели обучения.
Верни только JSON: {"selected": [номера]}
Правила:
- Выбирай только то, что нужно для цели и подходит уровню читателя; остальное пропусти.
- Сохраняй порядок оглавления.
- Номера бери только из списка."""


def _batches(items, limit=6000):
    """Порции по ~6000 символов заголовков, чтобы уложиться в лимит токенов."""
    cur, size = [], 0
    for it in items:
        n = len(it[1]) + 8
        if cur and size + n > limit:
            yield cur
            cur, size = [], 0
        cur.append(it)
        size += n
    if cur:
        yield cur


def _pick(ask_json, goal, level, items, what):
    lines = "\n".join(f"{i}|{t}" for i, t in items)
    user = f"Цель: {goal}\nУровень: {level}\n{what}:\n{lines}"
    data = ask_json(PICK_PROMPT, user, "selected", 2000)
    valid = {i for i, _ in items}
    out = []
    for x in data["selected"]:
        try:
            x = int(x)
        except (TypeError, ValueError):
            continue
        if x in valid and x not in out:
            out.append(x)
    return sorted(out)


def _children(toc, i):
    """Ближайший уровень вложенности под записью i."""
    lvl = toc[i]["level"]
    sub = []
    for j in range(i + 1, len(toc)):
        if toc[j]["level"] <= lvl:
            break
        sub.append(j)
    if not sub:
        return []
    cl = min(toc[j]["level"] for j in sub)
    return [j for j in sub if toc[j]["level"] == cl]


def _module(toc, j):
    e = toc[j]
    return {
        "title": e["title"],
        "summary": f"PDF, с. {e['page_start']}–{e['page_end']}",
        "kind": "concept",
        "also": "",
        "book": {"section": j, "page_start": e["page_start"], "page_end": e["page_end"]},
    }


def build_book_plan(ask_json, goal, level, book_id):
    """Тема = раздел верхнего уровня, модуль = его вложенный раздел.
    Два прохода: сначала главы, затем разделы внутри выбранных глав."""
    book = read_book(book_id)
    toc = book["toc"]
    top = min(e["level"] for e in toc)
    chapters = [(i, toc[i]["title"]) for i, e in enumerate(toc) if e["level"] == top]

    chosen = []
    for b in _batches(chapters):
        chosen += _pick(ask_json, goal, level, b, "Главы учебника")

    kids = {i: _children(toc, i) for i in chosen}
    pool = [(j, toc[j]["title"]) for i in chosen for j in kids[i]]
    picked = set()
    for b in _batches(pool):
        picked.update(_pick(ask_json, goal, level, b, "Разделы выбранных глав"))

    topics = []
    for i in chosen:
        mods = [j for j in kids[i] if j in picked] if kids[i] else [i]
        if not mods:
            continue
        e = toc[i]
        topics.append({
            "title": e["title"],
            "summary": f"PDF, с. {e['page_start']}–{e['page_end']}",
            "modules": [_module(toc, j) for j in mods],
        })

    return {
        "size": "",
        "scope": f"Курс по учебнику «{book['title']}»: разделы отобраны под цель «{goal}».",
        "prerequisites": [],
        "topics": topics,
        "source": "book",
        "book_id": book_id,
    }
