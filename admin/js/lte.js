import { state } from './state.js';
import { formatBytes } from './utils.js';

export function filterLteCards() {
  const container = document.getElementById("lte-cards-container");
  const badge = document.getElementById("lte-summary-badge");
  if (!container || !state.rawLteData) return;
  
  const searchInput = document.getElementById("lte-search-input");
  const sortSelect = document.getElementById("lte-sort-select");
  
  const search = searchInput ? searchInput.value.toLowerCase() : "";
  const sortBy = sortSelect ? sortSelect.value : "name_asc";
  
  // Calculate today & yesterday totals for mapping
  const mapped = state.rawLteData.map(d => {
    const todayUp = Math.max(0, (d.today_now_up || 0) - (d.today_init_up || 0));
    const todayDn = Math.max(0, (d.today_now_dn || 0) - (d.today_init_dn || 0));
    const todayTotal = todayUp + todayDn;
    
    const yesterdayUp = Math.max(0, (d.yesterday_now_up || 0) - (d.yesterday_init_up || 0));
    const yesterdayDn = Math.max(0, (d.yesterday_now_dn || 0) - (d.yesterday_init_dn || 0));
    const yesterdayTotal = yesterdayUp + yesterdayDn;
    
    const diff = todayTotal - yesterdayTotal;
    return {
      ...d,
      todayUp,
      todayDn,
      todayTotal,
      yesterdayTotal,
      diff
    };
  });
  
  // Filter
  const filtered = mapped.filter(d => (d.modem_name || '').toLowerCase().includes(search));
  
  // Sort
  if (sortBy === 'name_asc') {
    filtered.sort((a, b) => a.modem_name.localeCompare(b.modem_name, 'en'));
  } else if (sortBy === 'today_desc') {
    filtered.sort((a, b) => b.todayTotal - a.todayTotal);
  } else if (sortBy === 'diff_desc') {
    filtered.sort((a, b) => b.diff - a.diff);
  }
  
  // Update badge
  if (badge) badge.innerText = `모뎀: ${filtered.length}개`;
  
  // Render
  container.innerHTML = "";
  if (filtered.length === 0) {
    container.innerHTML = `<div style="grid-column: 1/-1; text-align:center; color:var(--text-muted); padding:3rem; font-size:0.85rem;">조회 대상 LTE 모뎀이 없습니다.</div>`;
    return;
  }
  
  filtered.forEach(d => {
    const div = document.createElement("div");
    div.className = "card";
    div.style.padding = "1rem";
    div.style.gap = "0.4rem";
    
    // Alert card border if usage is extremely high (e.g. over 500MB today)
    const isExcessive = d.todayTotal > 500 * 1024 * 1024;
    if (isExcessive) {
      div.style.borderColor = "rgba(239, 68, 68, 0.4)";
      div.style.boxShadow = "0 0 8px rgba(239, 68, 68, 0.05)";
    }
    
    const diffText = d.diff >= 0 ? `▲ ${formatBytes(d.diff)}` : `▼ ${formatBytes(Math.abs(d.diff))}`;
    const diffColor = d.diff >= 0 ? 'var(--color-danger)' : 'var(--color-primary)';
    
    div.innerHTML = `
      <div style="display:flex; justify-content:space-between; align-items:center;">
        <span style="font-weight:700; font-size:0.85rem;">${d.modem_name}</span>
        <span class="badge" style="font-size:0.65rem; color:${diffColor}; background-color:rgba(255,255,255,0.02); border-color:rgba(255,255,255,0.05);" title="어제 대비 증가량">
          ${diffText}
        </span>
      </div>
      
      <div style="margin: 0.25rem 0;">
        <span style="font-size:0.65rem; color:var(--text-muted); text-transform:uppercase;">오늘 실시간 총합</span>
        <div style="font-size:1.35rem; font-weight:800; color:var(--color-primary); line-height:1.2;">
          ${formatBytes(d.todayTotal)}
        </div>
      </div>
      
      <div style="font-size:0.7rem; color:var(--text-muted); display:grid; grid-template-columns:1fr 1fr; gap:0.2rem; border-top:1px dashed rgba(255,255,255,0.04); padding-top:0.4rem; margin-top:0.25rem;">
        <span>업로드: <strong>${formatBytes(d.todayUp)}</strong></span>
        <span>다운로드: <strong>${formatBytes(d.todayDn)}</strong></span>
        <span>어제 최종: <strong>${formatBytes(d.yesterdayTotal)}</strong></span>
        <span>갱신: <strong>${d.today_updated_at ? d.today_updated_at.substring(11, 16) : '--:--'}</strong></span>
      </div>
    `;
    container.appendChild(div);
  });
  if (window.lucide) {
    window.lucide.createIcons();
  }
}

// Bind to window for HTML select/input event handling
window.filterLteCards = filterLteCards;
