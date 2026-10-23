/** 通用工具：金额展示、Toast 提示、奖励弹出动效。 */

/** 金额展示：1 -> "1"，1.5 -> "1.5"，0.5 -> "0.5"（不显示多余的小数位） */
export function fmtMoney(n) {
  const v = Math.round(n * 100) / 100;
  return Number.isInteger(v) ? String(v) : String(parseFloat(v.toFixed(2)));
}

/** 顶部悬浮提示，type: success | error | info */
export function toast(msg, type = "info") {
  const root = document.getElementById("toast-root");
  const el = document.createElement("div");
  const colors = { success: "bg-emerald-500", error: "bg-rose-500", info: "bg-gray-800" };
  el.className = `toast px-6 py-3 rounded-2xl text-lg font-bold text-white shadow-xl ${colors[type] || colors.info}`;
  el.textContent = msg;
  root.appendChild(el);
  setTimeout(() => {
    el.style.transition = "opacity .3s";
    el.style.opacity = "0";
    setTimeout(() => el.remove(), 320);
  }, 2400);
}

/** 提交成功后的大字奖励动效，如「+2.5 元 🎉」 */
export function popBonus(text) {
  const overlay = document.getElementById("pop-overlay");
  const el = document.getElementById("pop-text");
  el.textContent = text;
  overlay.classList.remove("hidden");
  overlay.classList.add("flex");
  el.classList.remove("pop");
  void el.offsetWidth;   // 重启动画
  el.classList.add("pop");
  setTimeout(() => {
    overlay.classList.add("hidden");
    overlay.classList.remove("flex");
  }, 1300);
}
