import {
  createPlan, createBookPlan, createModules, createTheory, saveCourse, updateCourse,
  listCourses, getCourse, deleteCourse,
} from "./api.js";
import {
  renderLoading, renderError, renderPlan, renderSaved, renderModule, renderMarkdown,
} from "./views.js";
import { mountBooks } from "./books.js";

const form = document.getElementById("form");
const btn = document.getElementById("btn");
const saveBtn = document.getElementById("save");
const out = document.getElementById("out");
const saved = document.getElementById("saved");
const mode = document.getElementById("mode");
const bookbox = document.getElementById("bookbox");
const bookSel = document.getElementById("book");

let current = null; // { goal, level, plan, id? }
let viewId = 0; // меняется при смене экрана: поздний ответ не затрёт другой экран

// ---------- режим и выбор учебника ----------

mode.addEventListener("change", () => {
  bookbox.hidden = mode.value !== "book";
  if (!bookbox.hidden && !bookSel.options.length) document.getElementById("books").open = true;
});

function fillBooks(books) {
  const prev = bookSel.value;
  bookSel.replaceChildren(
    ...books.map((b) => new Option(`${b.title} (разделов: ${b.sections})`, b.id)),
  );
  if (books.some((b) => b.id === prev)) bookSel.value = prev;
  if (!books.length) bookSel.append(new Option("— нет учебников —", ""));
}

mountBooks(document.getElementById("books"), fillBooks);

// ---------- план и модули ----------

function showPlan() {
  viewId++;
  renderPlan(out, current.plan, expandTopic, openModule);
}

async function refreshSaved() {
  try {
    renderSaved(saved, await listCourses(), openCourse, removeCourse);
  } catch (err) {
    renderError(saved, err.message);
  }
}

async function openCourse(id) {
  try {
    current = await getCourse(id);
    showPlan();
    saveBtn.hidden = true;
  } catch (err) {
    renderError(out, err.message);
  }
}

async function removeCourse(id) {
  if (!confirm("Удалить план?")) return;
  try {
    await deleteCourse(id);
    await refreshSaved();
  } catch (err) {
    alert(err.message);
  }
}

async function expandTopic(i, button) {
  const course = current; // current может смениться, пока идёт запрос
  const view = viewId;
  const topic = course.plan.topics[i];
  button.disabled = true;
  button.textContent = "Генерирую...";
  try {
    const { modules } = await createModules({
      goal: course.goal,
      level: course.level,
      size: course.plan.size || "",
      topics: course.plan.topics.map((t) => t.title),
      topic: topic.title,
      summary: topic.summary,
    });
    topic.modules = modules;
    if (course === current && view === viewId) showPlan();
    if (course.id) await updateCourse(course.id, course);
  } catch (err) {
    button.disabled = false;
    button.textContent = "Разбить на модули";
    alert(err.message);
  }
}

async function openModule(i, j) {
  const course = current;
  const topic = course.plan.topics[i];
  const mod = topic.modules[j];
  mod.kind ||= "concept"; // у старых модулей типа нет
  const view = ++viewId;
  const body = renderModule(out, topic, mod, {
    onBack: showPlan,
    onKind: async (kind, also) => {
      mod.kind = kind;
      mod.also = also;
      try {
        if (course.id) await updateCourse(course.id, course);
      } catch (err) {
        alert(err.message);
      }
    },
    onRegen: () => {
      delete mod.theory;
      openModule(i, j);
    },
  });

  if (mod.theory) {
    renderMarkdown(body, mod.theory);
    return;
  }
  renderLoading(body);
  try {
    const { theory } = await createTheory({
      goal: course.goal,
      level: course.level,
      topic: topic.title,
      modules: topic.modules.map((m) => m.title),
      module: mod.title,
      summary: mod.summary,
      kind: mod.kind,
      also: mod.also || "",
    });
    mod.theory = theory;
    if (view === viewId) renderMarkdown(body, theory);
    if (course.id) await updateCourse(course.id, course);
  } catch (err) {
    if (view === viewId) renderError(body, err.message);
  }
}

form.addEventListener("submit", async (e) => {
  e.preventDefault();
  const data = new FormData(form);
  const params = { goal: data.get("goal"), level: data.get("level") };
  const fromBook = mode.value === "book";
  if (fromBook && !bookSel.value) {
    renderError(out, "Выберите или загрузите учебник");
    return;
  }
  btn.disabled = true;
  saveBtn.hidden = true;
  viewId++;
  renderLoading(out);
  try {
    const plan = fromBook
      ? await createBookPlan({ ...params, book_id: bookSel.value })
      : await createPlan(params);
    current = { ...params, plan };
    showPlan();
    saveBtn.hidden = false;
    saveBtn.disabled = false;
    saveBtn.textContent = "Сохранить план";
  } catch (err) {
    renderError(out, err.message);
  } finally {
    btn.disabled = false;
  }
});

saveBtn.addEventListener("click", async () => {
  saveBtn.disabled = true;
  try {
    const { id } = await saveCourse(current);
    current.id = id; // дальше изменения сохраняются автоматически
    saveBtn.textContent = "Сохранено";
    await refreshSaved();
  } catch (err) {
    saveBtn.disabled = false;
    alert(err.message);
  }
});

refreshSaved();
