async function request(url, opts) {
  const r = await fetch(url, opts);
  const data = await r.json();
  if (!r.ok) throw new Error(data.detail);
  return data;
}

const withBody = (method, body) => ({
  method,
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify(body),
});

export const createPlan = (params) => request("/api/plan", withBody("POST", params));
export const createBookPlan = (params) => request("/api/plan/book", withBody("POST", params));
export const saveCourse = (course) => request("/api/courses", withBody("POST", course));
export const listCourses = () => request("/api/courses");
export const getCourse = (id) => request(`/api/courses/${id}`);
export const deleteCourse = (id) => request(`/api/courses/${id}`, { method: "DELETE" });
export const createModules = (params) => request("/api/topic", withBody("POST", params));
export const updateCourse = (id, course) => request(`/api/courses/${id}`, withBody("PUT", course));
export const createTheory = (params) => request("/api/theory", withBody("POST", params));
