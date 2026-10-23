/** 家长后台：PIN 锁屏、收益概览（近 7 天趋势）、任务增删改查、变更日志、修改 PIN。 */
import { admin, setUnauthorizedHandler } from "./api.js";
import { fmtMoney, toast } from "./common.js";

const $ = (id) => document.getElementById(id);

/* ==================== 视图切换 ==================== */

function showLock() {
  $("view-admin").classList.add("hidden");
  $("view-lock").classList.remove("hidden");
  resetPin();
}

function showAdmin() {
  $("view-lock").classList.add("hidden");
  $("view-admin").classList.remove("hidden");
  switchATab("stats");
}

/* ==================== PIN 锁屏 ==================== */

let pinBuf = "";

function resetPin() {
  pinBuf = "";
  renderDots();
}

function renderDots() {
  $("pin-dots").querySelectorAll(".pin-dot").forEach((d, i) => d.classList.toggle("on", i < pinBuf.length));
}

async function pressKey(k) {
  if (k === "C") { pinBuf = ""; renderDots(); return; }
  if (k === "back") { pinBuf = pinBuf.slice(0, -1); renderDots(); return; }
  if (pinBuf.length >= 4) return;
  pinBuf += k;
  renderDots();
  if (pinBuf.length < 4) return;

  // 输满 4 位自动校验
  const pin = pinBuf;
  try {
    const res = await admin.verify(pin);
    admin.setToken(res.token);
    toast("解锁成功 👋", "success");
    showAdmin();
  } catch (err) {
    const card = $("pin-card");
    card.classList.add("shake");
    setTimeout(() => { card.classList.remove("shake"); resetPin(); }, 400);
    toast(err.message, "error");
  }
}

document.querySelectorAll("[data-key]").forEach((b) =>
  b.addEventListener("click", () => pressKey(b.dataset.key)));

/* token 失效（过期/重启）→ 自动锁屏 */
setUnauthorizedHandler(() => {
  admin.clearToken();
  showLock();
  toast("登录已过期，请重新解锁", "info");
});

/* ==================== Tab 切换 ==================== */

function switchATab(name) {
  document.querySelectorAll(".admin-tab").forEach((b) =>
    b.classList.toggle("active", b.dataset.atab === name));
  for (const t of ["stats", "tasks", "logs"]) {
    $("atab-" + t).classList.toggle("hidden", t !== name);
  }
  if (name === "stats") loadStats();
  if (name === "tasks") loadTasks();
  if (name === "logs") loadLogs(logPage);
}

document.querySelectorAll(".admin-tab").forEach((b) =>
  b.addEventListener("click", () => switchATab(b.dataset.atab)));

/* ==================== 概览 ==================== */

async function loadStats() {
  try {
    const s = await admin.stats();
    $("stat-today").textContent = "¥" + fmtMoney(s.today_total);
    $("stat-month").textContent = "¥" + fmtMoney(s.month_total);
    $("stat-grand").textContent = "¥" + fmtMoney(s.grand_total);
    $("stat-days").textContent = s.checked_days + " 天";
    $("stat-active").textContent = s.active_tasks + " 项";

    /* 近 7 天柱状图（纯 CSS，今日高亮，零额日极矮底座） */
    const max = Math.max(...s.last7.map((d) => d.total), 1);
    $("chart7").innerHTML = s.last7.map((d, i) => {
      const pct = Math.max(Math.round((d.total / max) * 100), d.total > 0 ? 8 : 3);
      const [, m, day] = d.date.split("-");
      const isToday = i === s.last7.length - 1;
      return `
        <div class="flex-1 flex flex-col items-center justify-end gap-1 h-full">
          <span class="text-xs font-bold ${d.total > 0 ? "text-slate-500" : "text-slate-300"}">${d.total > 0 ? fmtMoney(d.total) : "0"}</span>
          <div class="w-full max-w-12 rounded-t-xl ${isToday ? "bg-indigo-500" : "bg-indigo-200"}" style="height:${pct}%"></div>
          <span class="text-xs ${isToday ? "text-indigo-600 font-bold" : "text-slate-400"}">${Number(m)}/${Number(day)}</span>
        </div>`;
    }).join("");
  } catch (err) {
    if (err.message.indexOf("过期") === -1) toast(err.message, "error");
  }
}

/* ==================== 任务管理 ==================== */

let tasksCache = [];

async function loadTasks() {
  const box = $("task-list");
  box.innerHTML = `<div class="text-center text-slate-400 py-8">jiā zǎi zhōng · 加载中…</div>`;
  try {
    const res = await admin.tasks();
    tasksCache = res.tasks;
    box.innerHTML = tasksCache.length
      ? tasksCache.map(taskRow).join("")
      : `<div class="text-center text-slate-400 py-10">还没有家务，点右上角新增 ➕</div>`;
  } catch (err) {
    box.innerHTML = "";
  }
}

function taskRow(t) {
  const limit = t.daily_limit ? `${t.daily_limit} 次/天` : "不限";
  return `
  <div class="bg-white rounded-2xl shadow px-4 py-3 flex items-center gap-3 ${t.is_active ? "" : "opacity-60"}">
    <span class="text-4xl">${t.icon}</span>
    <div class="flex-1 min-w-0">
      <div class="font-extrabold text-slate-700 text-lg truncate">
        ${t.name}
        ${t.is_active ? "" : '<span class="ml-1 text-xs bg-gray-200 text-gray-500 px-2 py-0.5 rounded-full align-middle">已下架</span>'}
      </div>
      <div class="text-sm text-slate-400 truncate">
        ${t.pinyin} · ${fmtMoney(t.price)} 元/次 · 上限 ${limit}
        · 今日 ${t.done_today} 次 · 累计 ${t.total_times} 次 / ¥${fmtMoney(t.total_earned)}
      </div>
    </div>
    <div class="flex gap-2 shrink-0">
      <button data-edit="${t.id}" class="px-3 py-2 rounded-xl bg-slate-100 text-slate-600 font-bold active:scale-95 transition">编辑</button>
      ${t.is_active
        ? `<button data-off="${t.id}" class="px-3 py-2 rounded-xl bg-rose-100 text-rose-600 font-bold active:scale-95 transition">下架</button>`
        : `<button data-on="${t.id}" class="px-3 py-2 rounded-xl bg-emerald-100 text-emerald-600 font-bold active:scale-95 transition">上架</button>`}
    </div>
  </div>`;
}

$("task-list").addEventListener("click", async (e) => {
  const edit = e.target.closest("[data-edit]");
  const off = e.target.closest("[data-off]");
  const on = e.target.closest("[data-on]");
  try {
    if (edit) openTaskModal(Number(edit.dataset.edit));
    else if (off) {
      await admin.deleteTask(Number(off.dataset.off));
      toast("已下架，历史打卡记录完整保留", "success");
      loadTasks();
    } else if (on) {
      await admin.updateTask(Number(on.dataset.on), { is_active: true });
      toast("已重新上架", "success");
      loadTasks();
    }
  } catch (err) {
    toast(err.message, "error");
  }
});

/* ==================== 任务编辑弹窗 ==================== */

const ICONS = ["🧹","🪣","🧽","🗑️","🛏️","🍽️","🧺","👕","🚿","🪟","🧸","🪴",
               "🌱","💧","🐕","🐱","📚","✏️","🎒","🍎","🥕","🧻","⭐","🌟"];

let editingId = null;
let pinyinTouched = false;

function buildIconGrid() {
  $("icon-grid").innerHTML = ICONS.map((i) =>
    `<button type="button" data-icon="${i}" class="text-2xl p-1.5 rounded-xl bg-slate-100 active:scale-90 transition">${i}</button>`).join("");
}

function selectedIcon() {
  const b = $("icon-grid").querySelector(".icon-on");
  return b ? b.dataset.icon : null;
}

function openTaskModal(id = null) {
  editingId = id;
  pinyinTouched = false;
  const t = id ? tasksCache.find((x) => x.id === id) : null;
  $("modal-title").textContent = t ? `biān jí · 编辑：${t.name}` : "xīn zēng jiā wù · 新增家务";
  $("f-name").value = t ? t.name : "";
  $("f-pinyin").value = t ? t.pinyin : "";
  $("f-price").value = t ? t.price : "";
  $("f-limit").value = t && t.daily_limit ? t.daily_limit : "";
  $("f-sort").value = t ? t.sort_order : "";

  const want = t ? t.icon : "🧹";
  $("icon-grid").querySelectorAll("[data-icon]").forEach((b) =>
    b.classList.toggle("icon-on", b.dataset.icon === want));

  const m = $("task-modal");
  m.classList.remove("hidden");
  m.classList.add("flex");
  $("f-name").focus();
}

function closeTaskModal() {
  const m = $("task-modal");
  m.classList.add("hidden");
  m.classList.remove("flex");
}

$("btn-new-task").addEventListener("click", () => openTaskModal());
$("modal-cancel").addEventListener("click", closeTaskModal);
$("f-pinyin").addEventListener("input", () => { pinyinTouched = true; });

$("icon-grid").addEventListener("click", (e) => {
  const b = e.target.closest("[data-icon]");
  if (!b) return;
  $("icon-grid").querySelectorAll(".icon-on").forEach((x) => x.classList.remove("icon-on"));
  b.classList.add("icon-on");
});

$("modal-save").addEventListener("click", async () => {
  const name = $("f-name").value.trim();
  const price = parseFloat($("f-price").value);
  if (!name) { toast("请填写家务名称", "error"); return; }
  if (!(price >= 0.01)) { toast("单价至少 0.01 元", "error"); return; }

  const limitStr = $("f-limit").value.trim();
  const sortStr = $("f-sort").value.trim();
  const payload = { name, icon: selectedIcon() || "🧹", price };
  const py = $("f-pinyin").value.trim();
  if (py) payload.pinyin = py;                    // 留空 = 后端自动生成
  if (limitStr) payload.daily_limit = Number(limitStr);
  else if (editingId) payload.daily_limit = null; // 编辑时清空 = 改为不限
  if (sortStr) payload.sort_order = Number(sortStr);

  try {
    if (editingId) await admin.updateTask(editingId, payload);
    else await admin.createTask(payload);
    toast("保存成功 ✅", "success");
    closeTaskModal();
    loadTasks();
  } catch (err) {
    toast(err.message, "error");
  }
});

/* ==================== 变更日志 ==================== */

let logPage = 1;

const ACTION_MAP = {
  create: ["新增", "bg-emerald-100 text-emerald-600"],
  update: ["修改", "bg-amber-100 text-amber-600"],
  delete: ["下架", "bg-rose-100 text-rose-600"],
};
const FIELD_MAP = {
  name: "名称", pinyin: "拼音", icon: "图标", price: "单价",
  daily_limit: "每日上限", sort_order: "排序", is_active: "上架状态",
};

function fmtVal(field, v) {
  if (v === null || v === undefined) return "空";
  if (field === "price") return `¥${v}`;
  if (field === "is_active") return v ? "上架" : "下架";
  if (field === "daily_limit" && v === null) return "不限";
  return String(v);
}

async function loadLogs(page = 1) {
  try {
    const res = await admin.logs(page);
    logPage = res.page;
    $("log-page-info").textContent = `第 ${res.page} / ${Math.max(res.pages, 1)} 页 · 共 ${res.total} 条`;
    $("log-prev").disabled = page <= 1;
    $("log-next").disabled = page >= res.pages;

    $("log-list").innerHTML = res.items.length ? res.items.map((it) => {
      const [label, cls] = ACTION_MAP[it.action] || [it.action, "bg-slate-100 text-slate-500"];
      const changes = it.changes.map((c) => `
        <div class="text-sm text-slate-500">
          ${FIELD_MAP[c.field] || c.field}：
          ${c.old === null ? "" : `${fmtVal(c.field, c.old)} → `}
          <b class="text-slate-700">${fmtVal(c.field, c.new)}</b>
        </div>`).join("");
      return `
      <div class="bg-white rounded-2xl shadow px-4 py-3">
        <div class="flex items-center gap-2 flex-wrap">
          <span class="text-xs font-bold px-2 py-0.5 rounded-full ${cls}">${label}</span>
          <span class="font-extrabold text-slate-700">${it.task_name}</span>
          <span class="ml-auto text-sm text-slate-400">${it.created_at}</span>
        </div>
        <div class="mt-1 space-y-0.5">${changes}</div>
      </div>`;
    }).join("") : `<div class="text-center text-slate-400 py-10">暂无变更记录</div>`;
  } catch (err) {
    /* 401 已由统一处理器锁屏 */
  }
}

$("log-prev").addEventListener("click", () => loadLogs(logPage - 1));
$("log-next").addEventListener("click", () => loadLogs(logPage + 1));

/* ==================== 修改 PIN ==================== */

function openPinModal() {
  ["p-old", "p-new", "p-confirm"].forEach((id) => ($(id).value = ""));
  const m = $("pin-modal");
  m.classList.remove("hidden");
  m.classList.add("flex");
}
function closePinModal() {
  const m = $("pin-modal");
  m.classList.add("hidden");
  m.classList.remove("flex");
}

$("btn-changepin").addEventListener("click", openPinModal);
$("pin-cancel").addEventListener("click", closePinModal);

$("pin-save").addEventListener("click", async () => {
  const oldPin = $("p-old").value.trim();
  const newPin = $("p-new").value.trim();
  const confirmPin = $("p-confirm").value.trim();
  if (!/^\d{4}$/.test(oldPin) || !/^\d{4}$/.test(newPin)) {
    toast("密码必须是 4 位数字", "error"); return;
  }
  if (newPin !== confirmPin) { toast("两次输入的新密码不一致", "error"); return; }
  try {
    await admin.changePin(oldPin, newPin);
    toast("密码修改成功 ✅", "success");
    closePinModal();
  } catch (err) {
    toast(err.message, "error");
  }
});

/* ==================== 锁屏按钮 ==================== */

$("btn-logout").addEventListener("click", async () => {
  try { await admin.logout(); } catch (e) { /* token 失效也直接锁 */ }
  admin.clearToken();
  showLock();
  toast("已锁定 🔒", "info");
});

/* ==================== 启动 ==================== */

buildIconGrid();

(async function init() {
  if (admin.getToken()) {
    try {
      await admin.stats();   // 用一次鉴权请求验证 token 是否有效
      showAdmin();
      return;
    } catch (e) {
      admin.clearToken();
    }
  }
  showLock();
})();
