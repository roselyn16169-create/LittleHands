/** 统一 fetch 封装：自动 JSON 解析、统一中文错误信息、家长 token 支持。 */

async function request(method, path, body = null, token = null) {
  const opts = { method, headers: {} };
  if (token) opts.headers["Authorization"] = `Bearer ${token}`;
  if (body !== null) {
    opts.headers["Content-Type"] = "application/json";
    opts.body = JSON.stringify(body);
  }
  let resp;
  try {
    resp = await fetch(path, opts);
  } catch (e) {
    throw new Error("网络连接失败，请确认服务已启动");
  }
  let data = null;
  try { data = await resp.json(); } catch (e) { /* 无响应体时忽略 */ }
  if (!resp.ok) {
    // 携带 token 的请求收到 401：token 失效，通知家长端锁屏（不针对 PIN 校验本身）
    if (resp.status === 401 && token && onUnauthorized) onUnauthorized();
    let msg = `请求失败（${resp.status}）`;
    if (data) {
      if (typeof data.detail === "string") msg = data.detail;
      else if (Array.isArray(data.detail)) msg = data.detail.map((d) => d.msg || "").filter(Boolean).join("；");
    }
    throw new Error(msg);
  }
  return data;
}

/* 家长端 401 统一处理（回调由 admin.js 注入，避免模块循环依赖） */
let onUnauthorized = null;
export function setUnauthorizedHandler(fn) { onUnauthorized = fn; }

/* ---------- 儿童端（无需鉴权） ---------- */
export const api = {
  tasks: () => request("GET", "/api/tasks"),
  today: () => request("GET", "/api/records/today"),
  submit: (items) => request("POST", "/api/records/submit", { items }),
  summary: () => request("GET", "/api/records/summary"),
  history: (month) => request("GET", `/api/records/history${month ? `?month=${month}` : ""}`),
  day: (date) => request("GET", `/api/records?date=${date}`),
  settlements: () => request("GET", "/api/settlements"),
};

/* ---------- 家长端（Bearer token，仅存当前页面内存：离开页面即失效，下次进入需重新输 PIN） ---------- */

let _token = null;

export const admin = {
  getToken: () => _token,
  setToken: (t) => { _token = t; },
  clearToken: () => { _token = null; },

  verify: (pin) => request("POST", "/api/auth/verify", { pin }),
  logout: () => request("POST", "/api/auth/logout", null, admin.getToken()),
  changePin: (old_pin, new_pin) =>
    request("PUT", "/api/auth/pin", { old_pin, new_pin }, admin.getToken()),

  tasks: () => request("GET", "/api/admin/tasks", null, admin.getToken()),
  createTask: (data) => request("POST", "/api/admin/tasks", data, admin.getToken()),
  updateTask: (id, data) => request("PUT", `/api/admin/tasks/${id}`, data, admin.getToken()),
  deleteTask: (id) => request("DELETE", `/api/admin/tasks/${id}`, null, admin.getToken()),
  logs: (page = 1, pageSize = 20) =>
    request("GET", `/api/admin/logs?page=${page}&page_size=${pageSize}`, null, admin.getToken()),
  stats: () => request("GET", "/api/admin/stats", null, admin.getToken()),
  settlements: (page = 1, pageSize = 20) =>
    request("GET", `/api/admin/settlements?page=${page}&page_size=${pageSize}`, null, admin.getToken()),
  createSettlement: (data) => request("POST", "/api/admin/settlements", data, admin.getToken()),
  deleteSettlement: (id) => request("DELETE", `/api/admin/settlements/${id}`, null, admin.getToken()),
};
