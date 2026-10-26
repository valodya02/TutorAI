const REQUEST_TIMEOUT = 180_000;

function errorMessage(data, status) {
  const detail = data?.detail;
  if (typeof detail === "string" && detail) return detail;
  if (Array.isArray(detail)) {
    const messages = detail.map((item) => item?.msg).filter(Boolean);
    if (messages.length) return messages.join("; ");
  }
  if (detail && typeof detail === "object" && typeof detail.message === "string") {
    return detail.message;
  }
  return `Ошибка сервера (${status})`;
}

export async function request(url, opts = {}) {
  const controller = new AbortController();
  let timedOut = false;
  const timeout = setTimeout(() => {
    timedOut = true;
    controller.abort();
  }, REQUEST_TIMEOUT);
  const signal = opts.signal;
  const onAbort = () => controller.abort();
  signal?.addEventListener("abort", onAbort, { once: true });
  if (signal?.aborted) controller.abort();

  try {
    const r = await fetch(url, { ...opts, signal: controller.signal });
    const type = r.headers.get("content-type") || "";
    let data = null;
    if (type.toLowerCase().includes("application/json")) {
      try {
        data = await r.json();
      } catch {
        if (r.ok) throw new Error("Сервер вернул некорректный JSON");
      }
    }
    if (!r.ok) throw new Error(errorMessage(data, r.status));
    if (data === null) throw new Error("Сервер вернул неожиданный ответ");
    return data;
  } catch (err) {
    if (err.name === "AbortError") {
      if (signal?.aborted) throw err;
      if (timedOut) throw new Error("Запрос занял слишком много времени");
    }
    if (err instanceof TypeError) {
      throw new Error("Не удалось связаться с сервером. Проверьте подключение и повторите попытку.");
    }
    throw err;
  } finally {
    clearTimeout(timeout);
    signal?.removeEventListener("abort", onAbort);
  }
}

const withBody = (method, body, signal) => ({
  method,
  signal,
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify(body),
});

export const createPlan = (params, signal) => request("/api/plan", withBody("POST", params, signal));
export const createBookPlan = (params, signal) => request("/api/plan/book", withBody("POST", params, signal));
export const saveCourse = (course, signal) => request("/api/courses", withBody("POST", course, signal));
export const listCourses = (signal) => request("/api/courses", { signal });
export const getCourse = (id, signal) => request(`/api/courses/${id}`, { signal });
export const deleteCourse = (id, signal) => request(`/api/courses/${id}`, { method: "DELETE", signal });
export const createModules = (params, signal) => request("/api/topic", withBody("POST", params, signal));
export const updateCourse = (id, course, signal) => request(`/api/courses/${id}`, withBody("PUT", course, signal));
export const createTheory = (params, signal) => request("/api/theory", withBody("POST", params, signal));
