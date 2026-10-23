/** 儿童端 · 打卡页逻辑：加载家务、勾选/计数、实时金额、一键提交。 */
import { api } from "./api.js";
import { fmtMoney, toast, popBonus } from "./common.js";

const state = {
  tasks: [],
  todayTotal: 0,
  selected: new Map(),   // task_id -> quantity（本次勾选）
};

const grid = document.getElementById("task-grid");
const emptyTip = document.getElementById("empty-tip");
const todayTotalEl = document.getElementById("today-total");
const pendingBox = document.getElementById("pending-preview");
const pendingEl = document.getElementById("pending-amount");
const submitBtn = document.getElementById("submit-btn");

const byId = (id) => state.tasks.find((t) => t.id === id);

/* ---------- 数据加载 ---------- */

async function loadAll() {
  const [taskRes, todayRes] = await Promise.all([api.tasks(), api.today()]);
  state.tasks = taskRes.tasks;
  state.todayTotal = todayRes.total;
  // 任务可能被家长下架，同步清掉失效勾选
  for (const id of [...state.selected.keys()]) {
    if (!byId(id)) state.selected.delete(id);
  }
  render();
}

/* ---------- 渲染 ---------- */

function cardHTML(t) {
  const qty = state.selected.get(t.id) || 0;
  const remain = t.remain_today;                 // null = 不限次数
  const full = remain !== null && remain <= 0;
  const on = qty > 0;

  const tone = full
    ? "bg-gray-100 opacity-60 cursor-not-allowed"
    : on
      ? "bg-emerald-50 ring-4 ring-emerald-400 shadow-lg"
      : "bg-white shadow-md hover:shadow-lg active:scale-95 cursor-pointer";

  const badgeFull = full
    ? `<span class="absolute top-2 left-2 bg-gray-200 text-gray-500 text-xs font-bold px-2 py-1 rounded-full">✅ 今日完成</span>` : "";
  const check = on
    ? `<span class="absolute top-2 right-2 w-8 h-8 rounded-full bg-emerald-500 text-white text-lg font-black flex items-center justify-center">✓</span>` : "";
  const doneTip = !full && t.done_today > 0
    ? `<div class="text-xs text-amber-500 font-bold mt-1">jīn rì yǐ zuò · 今日已做 ${t.done_today} 次</div>` : "";
  const stepper = on && (remain === null || remain > 1)
    ? `<div class="flex items-center gap-3 mt-2">
         <button data-action="minus" class="w-11 h-11 rounded-full bg-white ring-2 ring-emerald-300 text-2xl font-bold text-emerald-600 active:scale-90 transition">−</button>
         <span class="text-2xl font-black text-emerald-600">${qty}</span>
         <button data-action="plus" ${(remain !== null && qty >= remain) ? "disabled" : ""}
           class="w-11 h-11 rounded-full bg-white ring-2 ring-emerald-300 text-2xl font-bold text-emerald-600 active:scale-90 transition disabled:opacity-30">＋</button>
       </div>` : "";

  return `
  <div class="task-card relative rounded-3xl p-3 sm:p-4 flex flex-col items-center text-center transition-all duration-150 ${tone}"
       data-id="${t.id}">
    ${badgeFull}${check}
    <div class="text-6xl sm:text-7xl mt-1">${t.icon}</div>
    <div class="text-sm sm:text-base text-gray-400 mt-1">${t.pinyin}</div>
    <div class="text-2xl sm:text-3xl font-extrabold text-gray-800">${t.name}</div>
    <div class="text-lg sm:text-xl font-bold text-amber-500 mt-1">${fmtMoney(t.price)} 元<span class="text-sm text-gray-400">/次</span></div>
    ${doneTip}${stepper}
  </div>`;
}

function render(popId = null) {
  if (state.tasks.length === 0) {
    grid.innerHTML = "";
    emptyTip.classList.remove("hidden");
  } else {
    emptyTip.classList.add("hidden");
    grid.innerHTML = state.tasks.map(cardHTML).join("");
    if (popId !== null) {
      const el = grid.querySelector(`[data-id="${popId}"]`);
      if (el) el.classList.add("pop");
    }
  }
  updateSummary();
}

function updateSummary() {
  let pending = 0;
  for (const [id, q] of state.selected) {
    const t = byId(id);
    if (t) pending += q * t.price;
  }
  todayTotalEl.textContent = fmtMoney(state.todayTotal);
  if (pending > 0) {
    pendingBox.classList.remove("hidden");
    pendingEl.textContent = fmtMoney(pending);
    submitBtn.disabled = false;
    submitBtn.textContent = `dǎ kǎ tí jiāo · 打卡提交 +${fmtMoney(pending)} 元`;
  } else {
    pendingBox.classList.add("hidden");
    submitBtn.disabled = true;
    submitBtn.textContent = "dǎ kǎ tí jiāo · 打卡提交";
  }
}

/* ---------- 交互 ---------- */

function setQty(id, qty) {
  const t = byId(id);
  if (!t) return;
  const remain = t.remain_today;
  if (qty <= 0) {
    state.selected.delete(id);
    render();
    return;
  }
  if (remain !== null) qty = Math.min(qty, remain);
  state.selected.set(id, qty);
  render(id);
}

function shakeCard(card) {
  card.classList.add("shake");
  setTimeout(() => card.classList.remove("shake"), 350);
}

grid.addEventListener("click", (e) => {
  const card = e.target.closest(".task-card");
  if (!card) return;
  const id = Number(card.dataset.id);
  const t = byId(id);
  if (!t) return;
  const action = e.target.closest("[data-action]");
  const qty = state.selected.get(id) || 0;
  const remain = t.remain_today;
  const full = remain !== null && remain <= 0;

  if (action) {                          // 步进器
    if (action.dataset.action === "plus") {
      if (remain === null || qty < remain) setQty(id, qty + 1);
      else shakeCard(card);
    } else {
      setQty(id, qty - 1);
    }
    return;
  }
  if (full) {                            // 已完成的卡片：轻晃提示
    shakeCard(card);
    return;
  }
  setQty(id, qty > 0 ? 0 : 1);           // 点卡片主体：勾选 / 取消
});

submitBtn.addEventListener("click", async () => {
  if (state.selected.size === 0 || submitBtn.disabled) return;
  const items = [...state.selected].map(([task_id, quantity]) => ({ task_id, quantity }));
  submitBtn.disabled = true;
  submitBtn.textContent = "tí jiāo zhōng · 提交中…";
  try {
    const res = await api.submit(items);
    state.selected.clear();
    popBonus(`+${fmtMoney(res.added_amount)} 元 🎉`);
    await loadAll();
    toast("打卡成功，你真棒！💪", "success");
  } catch (err) {
    toast(err.message, "error");
    updateSummary();
  }
});

/* ---------- Tab 切换（小金库第 5 步开发） ---------- */

const tabs = document.querySelectorAll(".tab");
const views = {
  checkin: document.getElementById("view-checkin"),
  bank: document.getElementById("view-bank"),
};

function switchTab(name) {
  for (const [k, v] of Object.entries(views)) v.classList.toggle("hidden", k !== name);
  tabs.forEach((a) => a.classList.toggle("tab-active", a.dataset.tab === name));
}

window.addEventListener("hashchange", () => switchTab(location.hash.slice(1) || "checkin"));

/* 回到页面时静默刷新（家长可能改了任务） */
document.addEventListener("visibilitychange", () => {
  if (!document.hidden) loadAll().catch(() => {});
});

/* ---------- 启动 ---------- */
(async function init() {
  switchTab(location.hash.slice(1) || "checkin");
  try {
    await loadAll();
  } catch (err) {
    toast(err.message, "error");
  }
})();
