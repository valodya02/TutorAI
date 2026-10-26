import { marked } from "https://cdn.jsdelivr.net/npm/marked@12/lib/marked.esm.js";
import DOMPurify from "https://cdn.jsdelivr.net/npm/dompurify@3/+esm";
import katex from "https://cdn.jsdelivr.net/npm/katex@0.16.11/dist/katex.mjs";
export const KINDS = {
  concept: "концептуальный",
  procedure: "процедурный",
  facts: "декларативный",
  narrative: "повествовательный",
  creative: "творческий",
};

function kindSelect(value, withEmpty) {
  const s = document.createElement("select");
  if (withEmpty) s.append(new Option("нет", ""));
  for (const [k, label] of Object.entries(KINDS)) s.append(new Option(label, k));
  s.value = value || "";
  return s;
}

export function renderLoading(el) {
  el.textContent = "Генерирую...";
}

export function renderError(el, message) {
  const p = document.createElement("p");
  p.className = "err";
  p.textContent = message;
  el.replaceChildren(p);
}

export function renderPlan(el, plan, onExpand, onOpen) {
  const box = document.createElement("div");
  box.className = "plan";
    const scope = document.createElement("p");
  scope.textContent = plan.scope;
  box.append(scope);
  if (plan.size) {
    const size = document.createElement("p");
    size.className = "muted";
    size.textContent = `Объём: ${plan.size}`;
    box.append(size);
  }

  if (plan.prerequisites?.length) {
    const h = document.createElement("b");
    h.textContent = "Нужно знать заранее:";
    const ul = document.createElement("ul");
    for (const p of plan.prerequisites) {
      const li = document.createElement("li");
      li.textContent = p;
      ul.append(li);
    }
    box.append(h, ul);
  }

  const ol = document.createElement("ol");
  plan.topics.forEach((t, i) => {
    const li = document.createElement("li");
    const b = document.createElement("b");
    b.textContent = t.title;
    li.append(b, t.summary);

    if (t.modules?.length) {
      const ul = document.createElement("ul");
      t.modules.forEach((m, j) => {
        const mi = document.createElement("li");
        const a = document.createElement("a");
        a.href = "#";
        a.textContent = m.title;
        a.onclick = (e) => { e.preventDefault(); onOpen(i, j); };
        const done = m.theory ? " ✓" : "";
        mi.append(a, done, ": ", m.summary);
        ul.append(mi);
      });
      li.append(ul);
    } else {
      const btn = document.createElement("button");
      btn.type = "button";
      btn.textContent = "Разбить на модули";
      btn.onclick = () => onExpand(i, btn);
      li.append(btn);
    }
    ol.append(li);
  });
  box.append(ol);

  el.replaceChildren(box);
}

export function renderSaved(el, courses, onOpen, onDelete) {
  if (!courses.length) {
    el.textContent = "Пока пусто";
    return;
  }
  const ul = document.createElement("ul");
  for (const c of courses) {
    const li = document.createElement("li");
    const open = document.createElement("a");
    open.href = "#";
    open.textContent = `${c.goal} (${c.level}, ${c.created})`;
    open.onclick = (e) => { e.preventDefault(); onOpen(c.id); };
    const del = document.createElement("button");
    del.type = "button";
    del.textContent = "Удалить";
    del.onclick = () => onDelete(c.id);
    li.append(open, " ", del);
    ul.append(li);
  }
  el.replaceChildren(ul);
}

// Каркас экрана модуля; возвращает элемент для содержимого
export function renderModule(el, topic, mod, { onBack, onKind, onRegen }) {
  const back = document.createElement("button");
  back.type = "button";
  back.textContent = "← К плану";
  back.onclick = onBack;

  const h = document.createElement("h2");
  h.textContent = mod.title;
  const sub = document.createElement("p");
  sub.className = "muted";
  sub.textContent = `Тема: ${topic.title}`;

  const meta = document.createElement("div");
  meta.className = "meta";
  const kind = kindSelect(mod.kind, false);
  const also = kindSelect(mod.also, true);
  const changed = () => onKind(kind.value, also.value === kind.value ? "" : also.value);
  kind.onchange = also.onchange = changed;
  const regen = document.createElement("button");
  regen.type = "button";
  regen.textContent = "Сгенерировать заново";
  regen.onclick = onRegen;
  meta.append("Тип:", kind, "дополнительно:", also, regen);

  const body = document.createElement("div");
  body.className = "theory";
  el.replaceChildren(back, h, sub, meta, body);
  return body;
}

// Формулы вырезаются до Markdown и подставляются после,
// чтобы Markdown-парсер не трогал содержимое формул
const MATH_RE = new RegExp(
  [
    /(?<!\\)\$\$([\s\S]+?)(?<!\\)\$\$/.source, // $$...$$
    /(?<!\\)\\\[([\s\S]+?)(?<!\\)\\\]/.source, // \[...\]
    /(?<!\\)\\\(([\s\S]+?)(?<!\\)\\\)/.source, // \(...\)
    /(?<![\\$])\$([^$\n]+?)(?<!\\)\$(?!\d)/.source, // $...$
  ].join("|"),
  "g"
);

export function renderMarkdown(el, md) {
  const formulas = [];
  const stash = (tex, display) => {
    formulas.push({ tex: tex.trim(), display });
    return `ZZMATH${formulas.length - 1}ZZ`;
  };

  // 1. Вырезаем формулы (кроме блоков кода)
  const text = md
    .split(/(```[\s\S]*?```|`[^`\n]+`)/)
    .map((part, i) =>
      i % 2
        ? part
        : part.replace(MATH_RE, (_, a, b, c, d) =>
            a !== undefined ? stash(a, true)
            : b !== undefined ? stash(b, true)
            : c !== undefined ? stash(c, false)
            : stash(d, false))
    )
    .join("");

  // 2-3. Markdown и очистка HTML
  const html = DOMPurify.sanitize(marked.parse(text));

  // 4. Подставляем формулы; вывод KaTeX безопасен, поэтому после очистки
  el.innerHTML = html.replace(/ZZMATH(\d+)ZZ/g, (_, i) => {
    const { tex, display } = formulas[i];
    return katex.renderToString(tex, {
      displayMode: display,
      throwOnError: false,
      strict: "ignore",
      output: "html",
    });
  });
    // marked ставит disabled на чекбоксы задач; для самопроверки они должны нажиматься
  for (const box of el.querySelectorAll('input[type="checkbox"]')) {
    box.disabled = false;
  }
}