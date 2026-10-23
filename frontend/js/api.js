/** 统一 fetch 封装：自动 JSON 解析、统一中文错误信息。 */

async function request(method, path, body = null) {
  const opts = { method, headers: {} };
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
    let msg = `请求失败（${resp.status}）`;
    if (data) {
      if (typeof data.detail === "string") msg = data.detail;
      else if (Array.isArray(data.detail)) msg = data.detail.map((d) => d.msg || "").filter(Boolean).join("；");
    }
    throw new Error(msg);
  }
  return data;
}

export const api = {
  tasks: () => request("GET", "/api/tasks"),
  today: () => request("GET", "/api/records/today"),
  submit: (items) => request("POST", "/api/records/submit", { items }),
  summary: () => request("GET", "/api/records/summary"),
  history: (month) => request("GET", `/api/records/history${month ? `?month=${month}` : ""}`),
  day: (date) => request("GET", `/api/records?date=${date}`),
};
