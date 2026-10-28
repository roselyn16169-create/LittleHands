/** 儿童端 · 小金库页：累计收益、今日明细（按家务聚合）、按月每日打卡记录。 */
import { api } from "./api.js";
import { fmtMoney, toast } from "./common.js";

const WEEK = ["日", "一", "二", "三", "四", "五", "六"];

let currentMonth = null;          // "YYYY-MM"
const detailCache = new Map();    // date -> items（当日明细缓存）

const $ = (id) => document.getElementById(id);

/* ---------- 格式化工具 ---------- */

function fmtDate(dateStr) {
  const [, m, d] = dateStr.split("-");
  const wd = WEEK[new Date(dateStr + "T00:00:00").getDay()];
  return `${Number(m)}月${Number(d)}日 · 星期${wd}`;
}

function localMonth() {
  const n = new Date();
  return `${n.getFullYear()}-${String(n.getMonth() + 1).padStart(2, "0")}`;
}

function shiftMonth(ym, delta) {
  const [y, m] = ym.split("-").map(Number);
  const d = new Date(y, m - 1 + delta, 1);
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}`;
}

/* ---------- 加载 ---------- */

async function loadBank() {
  try {
    const [sum, today] = await Promise.all([api.summary(), api.today()]);
    $("bank-grand").textContent = fmtMoney(sum.grand_total);
    $("bank-today").textContent = fmtMoney(sum.today_total);
    $("bank-month").textContent = fmtMoney(sum.month_total);
    $("bank-days").textContent = sum.checked_days;
    $("bank-balance").textContent = fmtMoney(sum.balance);
    $("bank-settled").textContent = "¥" + fmtMoney(sum.settled_total);
    $("bank-earned").textContent = "¥" + fmtMoney(sum.grand_total);
    renderToday(today);
    renderSettlements();
    if (!currentMonth) currentMonth = today.date.slice(0, 7);
    await loadHistory();
  } catch (err) {
    toast(err.message, "error");
  }
}

function renderToday(today) {
  const box = $("bank-today-list");
  if (!today.items.length) {
    box.innerHTML = `<div class="py-10 text-center text-lg text-gray-400">今天还没打卡哦，快去打卡页赚积分吧！💪</div>`;
    return;
  }
  box.innerHTML = today.items.map((i) => `
    <div class="flex items-center gap-3 px-4 py-3">
      <span class="text-4xl">${i.icon}</span>
      <div class="flex-1">
        <div class="text-lg font-extrabold text-gray-700">${i.name} <span class="text-pink-500">×${i.quantity}</span></div>
        <div class="text-sm text-gray-400">${fmtMoney(i.price)} 元/次</div>
      </div>
      <div class="text-2xl font-black text-pink-500">+${fmtMoney(i.amount)}</div>
    </div>`).join("");
}

/* ---------- 兑换记录（家长结算后孩子可见） ---------- */

async function renderSettlements() {
  const box = $("bank-settlement-list");
  try {
    const res = await api.settlements();
    if (!res.items.length) {
      box.innerHTML = `<div class="py-6 text-center text-gray-300 text-lg">hái méi yǒu · 还没兑换过奖励哦 🎁</div>`;
      return;
    }
    box.innerHTML = res.items.map((i) => `
    <div class="flex items-center gap-3 px-4 py-3">
      <span class="text-3xl">🎁</span>
      <div class="flex-1">
        <div class="text-lg font-extrabold text-gray-700">${i.method}${i.note ? ` · ${i.note}` : ""}</div>
        <div class="text-sm text-gray-400">${i.created_at.slice(0, 10)}</div>
      </div>
      <div class="text-2xl font-black text-indigo-400">−${fmtMoney(i.amount)}</div>
    </div>`).join("");
  } catch (err) {
    box.innerHTML = "";
  }
}

/* ---------- 每日打卡记录 ---------- */

async function loadHistory() {
  const list = $("bank-history-list");
  const [y, m] = currentMonth.split("-").map(Number);
  $("month-label").textContent = `${y}年${m}月`;
  const atNow = currentMonth >= localMonth();
  $("month-next").disabled = atNow;
  $("month-next").classList.toggle("opacity-30", atNow);
  list.innerHTML = `<div class="py-6 text-center text-gray-300 text-lg">jiā zǎi zhōng · 加载中…</div>`;

  let data;
  try {
    data = await api.history(currentMonth);
  } catch (err) {
    toast(err.message, "error");
    list.innerHTML = "";
    return;
  }
  $("bank-hist-month-total").textContent = fmtMoney(data.month_total);

  if (!data.days.length) {
    list.innerHTML = `<div class="py-10 text-center text-lg text-gray-400 bg-white rounded-3xl shadow">这个月还没有打卡记录 🐷</div>`;
    return;
  }
  list.innerHTML = data.days.map((d) => `
    <div data-date="${d.date}">
      <div class="day-row w-full bg-white rounded-2xl shadow px-4 py-3 flex items-center justify-between cursor-pointer active:scale-[0.98] transition">
        <div class="text-left">
          <div class="text-lg font-extrabold text-gray-700">${fmtDate(d.date)}</div>
          <div class="text-sm text-gray-400">dǎ kǎ ${d.quantity} cì · 打卡 ${d.quantity} 次</div>
        </div>
        <div class="text-2xl font-black text-pink-500">¥${fmtMoney(d.total)}</div>
      </div>
      <div class="day-detail hidden bg-white/80 rounded-b-2xl px-4 pb-3 -mt-1 pt-2 space-y-1 shadow-sm"></div>
    </div>`).join("");

  list.querySelectorAll(".day-row").forEach((row) => {
    row.addEventListener("click", () => toggleDetail(row.parentElement));
  });
}

/** 点击某天：懒加载并展开/收起当日明细 */
async function toggleDetail(rowEl) {
  const detail = rowEl.querySelector(".day-detail");
  const date = rowEl.dataset.date;
  if (!detail.classList.contains("hidden")) {
    detail.classList.add("hidden");
    return;
  }
  if (!detailCache.has(date)) {
    try {
      const d = await api.day(date);
      detailCache.set(date, d.items);
    } catch (err) {
      toast(err.message, "error");
      return;
    }
  }
  const items = detailCache.get(date);
  detail.innerHTML = items.map((i) => `
    <div class="flex items-center gap-2 text-base text-gray-500">
      <span class="text-2xl">${i.icon}</span>
      <span class="flex-1 font-bold">${i.name} ×${i.quantity}</span>
      <span class="font-black text-amber-500">+${fmtMoney(i.amount)} 元</span>
    </div>`).join("");
  detail.classList.remove("hidden");
}

/* ---------- 月份切换 ---------- */

$("month-prev").addEventListener("click", () => {
  detailCache.clear();
  currentMonth = shiftMonth(currentMonth, -1);
  loadHistory();
});
$("month-next").addEventListener("click", () => {
  if ($("month-next").disabled) return;
  detailCache.clear();
  currentMonth = shiftMonth(currentMonth, 1);
  loadHistory();
});

export { loadBank };
