// Simple Clock helper
export function updateClock() {
  const now = new Date();
  const options = { timeZone: 'Asia/Seoul', hour: '2-digit', minute: '2-digit', second: '2-digit', hour12: false };
  const timeStr = now.toLocaleTimeString('ko-KR', options);
  const kstBadge = document.getElementById("kst-timer");
  if (kstBadge) {
    kstBadge.innerHTML = `<i data-lucide="clock" style="width: 12px; height: 12px;"></i>KST ${timeStr}`;
  }
  if (window.lucide) {
    window.lucide.createIcons();
  }
}

export function initClock() {
  updateClock();
  setInterval(updateClock, 1000);
}
