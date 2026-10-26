// Учебники: загрузка PDF и ручная настройка оглавления

import { request as apiRequest } from "./api.js";

const DEFAULT_PATTERN = String.raw`^(?P<title>.+?)[\s.·…]{2,}(?P<page>\d+)\s*$`;

async function request(url, opts) {
  return apiRequest(url, opts);
}

const post = (body, signal) => ({
  method: "POST",
  signal,
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify(body),
});

function el(tag, props = {}, ...children) {
  const e = Object.assign(document.createElement(tag), props);
  e.append(...children);
  return e;
}

function field(label, input) {
  return el("label", {}, label, input);
}

const root = el("div");
const status = el("div");
const list = el("div");
const panel = el("div");
const fileInput = el("input", { type: "file", accept: ".pdf,application/pdf" });
const uploadBtn = el("button", { type: "button", textContent: "Загрузить" });
root.append(
  field("PDF-файл", fileInput),
  uploadBtn,
  status,
  list,
  panel,
);

let onChange = async () => {};

// container: элемент, куда встроить блок; cb вызывается при каждом обновлении списка книг
export function mountBooks(container, cb) {
  onChange = cb;
  container.append(root);
  refresh();
}

function say(text, isError = false) {
  status.className = isError ? "err" : "muted";
  status.textContent = text;
}

async function refresh() {
  try {
    const books = await request("/api/books");
    await onChange(books);
    if (!books.length) {
      list.textContent = "Пока пусто";
      return;
    }
    const ul = el("ul");
    for (const b of books) {
      const btn = el("button", { type: "button", textContent: "Оглавление" });
      btn.onclick = () => showSettings(b.id);
      ul.append(
        el("li", {}, `${b.title} (${b.pages} стр., разделов: ${b.sections}) `, btn),
      );
    }
    list.replaceChildren(ul);
  } catch (err) {
    list.className = "err";
    list.textContent = err.message;
  }
}

async function showSettings(id, note = "") {
  const book = await request(`/api/books/${id}`);
  const s = book.settings || {};

  const pages = el("input", { value: s.toc_pages || "", placeholder: "например 6-8" });
  const offset = el("input", { type: "number", value: s.offset ?? 1 });
  const pattern = el("input", { value: s.pattern || DEFAULT_PATTERN });
  const result = el("pre", { className: "muted" });
  result.style.cssText = "white-space:pre-wrap;max-height:320px;overflow:auto;font:inherit;font-size:.85rem";

  const preview = el("button", { type: "button", textContent: "Показать страницу оглавления" });
  preview.onclick = async () => {
    const p = parseInt(pages.value, 10);
    if (!p) { result.textContent = "Укажите страницы оглавления"; return; }
    try {
      const { text } = await request(`/api/books/${id}/pages/${p}`);
      result.className = "muted";
      result.textContent = `Страница PDF ${p}:\n\n${text}`;
    } catch (err) {
      result.className = "err";
      result.textContent = err.message;
    }
  };

  const apply = el("button", { type: "button", textContent: "Применить" });
  apply.onclick = async () => {
    apply.disabled = true;
    try {
      await request(`/api/books/${id}/toc`, post({
        toc_pages: pages.value,
        offset: Number(offset.value) || 0,
        pattern: pattern.value,
      }));
      const b = await request(`/api/books/${id}`);
      result.className = "muted";
      result.textContent =
        `Найдено разделов: ${b.toc.length}\n\n` +
        b.toc.slice(0, 15)
          .map((t) => `${"  ".repeat(t.level - 1)}${t.title} → с. PDF ${t.page_start}–${t.page_end}`)
          .join("\n") +
        (b.toc.length > 15 ? "\n..." : "");
      await refresh();
    } catch (err) {
      result.className = "err";
      result.textContent = err.message;
    } finally {
      apply.disabled = false;
    }
  };

  panel.replaceChildren(
    el("h3", { textContent: `Оглавление: ${book.title}` }),
    note ? el("p", { className: "muted", textContent: note }) : "",
    field("Страницы оглавления в PDF (с 1)", pages),
    field("Сдвиг нумерации: страница PDF = напечатанная + сдвиг", offset),
    field("Шаблон строки (регулярное выражение с группами title и page)", pattern),
    preview, " ", apply,
    result,
  );
}

uploadBtn.onclick = async () => {
  const file = fileInput.files[0];
  if (!file) return say("Выберите PDF", true);
  uploadBtn.disabled = true;
  say("Загружаю...");
  try {
    const fd = new FormData();
    fd.append("file", file);
    const b = await request("/api/books", { method: "POST", body: fd });
    say(b.sections ? `Загружено, разделов: ${b.sections}` : "Загружено");
    await refresh();
    if (!b.sections) {
      await showSettings(b.id, "В PDF нет закладок: укажите, где находится оглавление.");
    }
  } catch (err) {
    say(err.message, true);
  } finally {
    uploadBtn.disabled = false;
  }
};
