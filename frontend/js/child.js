/** 儿童端 · 打卡页逻辑：加载家务、单次勾选、实时金额、一键提交。
 *
 * 交互模型：一次勾选 = 打卡 1 次；同一家务一天内可在不同时间多次打卡
 * （每次重新勾选、提交），能否继续打由 remain_today 决定；
 * 今日完成次数实时显示在卡片左上角徽章。
 */
import { api } from "./api.js";
import { fmtMoney, toast, popBonus } from "./common.js";
import { loadBank } from "./bank.js";

const state = {
  tasks: [],
  todayTotal: 0,
  selected: new Set(),   // 本次勾选的 task_id 集合（每项计 1 次）
};

const grid = document.getElementById("task-grid");
const loadingEl = document.getElementById("grid-loading");
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
  for (const id of [...state.selected]) {
    if (!byId(id)) state.selected.delete(id);
  }
  render();
}

/* ---------- 渲染 ---------- */

function cardHTML(t) {
  const on = state.selected.has(t.id);
  const limit = t.daily_limit;                    // null = 不限次数
  const full = t.remain_today !== null && t.remain_today <= 0;
  const done = t.done_today || 0;

  const tone = full
    ? "bg-gray-100 opacity-60 cursor-not-allowed"
    : on
      ? "bg-emerald-50 ring-4 ring-emerald-400 shadow-lg"
      : "bg-white shadow-md hover:shadow-lg active:scale-95 cursor-pointer";

  // 左上角：今日完成次数徽章（做了才有；满了变灰 + ✅）
  const badge = done > 0
    ? `<span class="absolute top-2 left-2 text-xs font-bold px-2 py-1 rounded-full whitespace-nowrap
                    ${full ? "bg-gray-200 text-gray-500" : "bg-amber-100 text-amber-600"}">
         ${full ? "✅" : ""}今日完成 ${limit ? `${done}/${limit}` : done} 次
       </span>` : "";
  const check = on
    ? `<span class="absolute top-2 right-2 w-8 h-8 rounded-full bg-emerald-500 text-white text-lg font-black flex items-center justify-center">✓</span>` : "";

  return `
  <div class="task-card relative rounded-3xl p-3 sm:p-4 flex flex-col items-center text-center transition-all duration-150 ${tone}"
       data-id="${t.id}">
    ${badge}${check}
    <div class="text-6xl sm:text-7xl mt-4">${t.icon}</div>
    <div class="text-sm sm:text-base text-gray-400 mt-1">${t.pinyin}</div>
    <div class="text-2xl sm:text-3xl font-extrabold text-gray-800">${t.name}</div>
    <div class="text-lg sm:text-xl font-bold text-amber-500 mt-1">${fmtMoney(t.price)} 元<span class="text-sm text-gray-400">/次</span></div>
  </div>`;
}

function render(popId = null) {
  if (loadingEl) loadingEl.classList.add("hidden");
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
  for (const id of state.selected) {
    const t = byId(id);
    if (t) pending += t.price;
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

  if (t.remain_today !== null && t.remain_today <= 0) {
    shakeCard(card);            // 今日额度已用完：轻晃提示
    return;
  }
  if (state.selected.has(id)) state.selected.delete(id);
  else state.selected.add(id);  // 勾选 / 取消（每次 1 次）
  render(id);
});

submitBtn.addEventListener("click", async () => {
  if (state.selected.size === 0 || submitBtn.disabled) return;
  const items = [...state.selected].map((task_id) => ({ task_id, quantity: 1 }));
  submitBtn.disabled = true;
  submitBtn.textContent = "tí jiāo zhōng · 提交中…";
  try {
    const res = await api.submit(items);
    state.selected.clear();
    popBonus(`+${fmtMoney(res.added_amount)} 元 🎉`);
    // 新解锁的成就徽章依次弹出（与金额反馈错开节奏）
    (res.unlocked || []).forEach((u, i) => {
      setTimeout(() => popBonus(`${u.icon} jiě suǒ chéng jiù · 解锁成就：${u.name}！`), 1400 + i * 1500);
    });
    await loadAll();
    toast("打卡成功，你真棒！💪", "success");
  } catch (err) {
    toast(err.message, "error");
    updateSummary();
  }
});

/* ---------- Tab 切换 ---------- */

const tabs = document.querySelectorAll(".tab");
const views = {
  checkin: document.getElementById("view-checkin"),
  bank: document.getElementById("view-bank"),
};

function switchTab(name) {
  for (const [k, v] of Object.entries(views)) v.classList.toggle("hidden", k !== name);
  tabs.forEach((a) => a.classList.toggle("tab-active", a.dataset.tab === name));
  if (name === "bank") loadBank();   // 每次切到小金库都拉取最新数据
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
    if (loadingEl) loadingEl.classList.add("hidden");
    toast(err.message, "error");
  }
})();
