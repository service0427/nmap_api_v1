import { state } from './state.js';

let mobilePage = 1;
const ITEMS_PER_PAGE = 30;

export function filterDestinationsLocally(resetPage = false) {
  if (!state.rawDestinations) return;
  
  const searchInput = document.getElementById("dest-search-input");
  const siteButtonsEl = document.getElementById("dest-site-buttons");
  const countBadge = document.getElementById("dest-slot-count-badge");
  
  const gridEl = document.getElementById("grid-destinations");
  const mobileListEl = document.getElementById("mobile-destinations-list");
  const mobilePagerEl = document.getElementById("mobile-destinations-pagination");

  // 1. Calculate Workload Summary Statistics for the active date
  const rawDests = state.rawDestinations || [];
  let totalTarget = 0;
  let totalSuccess = 0;
  let totalFail = 0;
  
  for (const d of rawDests) {
    totalTarget += (d.target || 0);
    totalSuccess += (d.success || 0);
    totalFail += (d.fail || 0);
  }
  
  const rate = totalTarget > 0 ? ((totalSuccess / totalTarget) * 100).toFixed(1) : '0.0';

  const summaryDateEl = document.getElementById("dest-summary-date");
  const summaryTargetEl = document.getElementById("dest-summary-target");
  const summarySuccessEl = document.getElementById("dest-summary-success");
  const summaryFailEl = document.getElementById("dest-summary-fail");
  const summaryRateEl = document.getElementById("dest-summary-rate");

  if (summaryDateEl) {
    const selDate = state.selectedDestinationDate || (state.lastApiData && state.lastApiData.system.kst_time ? state.lastApiData.system.kst_time.substring(0, 10) : '오늘');
    const isToday = state.lastApiData && state.lastApiData.system.kst_time && state.lastApiData.system.kst_time.substring(0, 10) === selDate;
    summaryDateEl.innerText = `${selDate} ${isToday ? '(오늘)' : ''}`;
  }
  if (summaryTargetEl) summaryTargetEl.innerText = `${totalTarget.toLocaleString()}건`;
  if (summarySuccessEl) summarySuccessEl.innerText = `${totalSuccess.toLocaleString()}건`;
  if (summaryFailEl) summaryFailEl.innerText = `${totalFail.toLocaleString()}건`;
  if (summaryRateEl) summaryRateEl.innerText = `${rate}%`;

  // 2. Populate Site Filter Button Group dynamically
  const activeSite = state.selectedSiteFilter || 'all';
  if (siteButtonsEl) {
    const uniqueSites = ["all", ...new Set(rawDests.map(d => (d.site_id || '').toUpperCase()).filter(Boolean))].sort();
    const existingButtons = Array.from(siteButtonsEl.querySelectorAll("button")).map(b => b.getAttribute("data-site"));
    const isSame = uniqueSites.length === existingButtons.length && uniqueSites.every((v, i) => v === existingButtons[i]);
    
    if (!isSame) {
      siteButtonsEl.innerHTML = "";
      uniqueSites.forEach(site => {
        const btn = document.createElement("button");
        btn.className = "date-tab-btn";
        btn.setAttribute("data-site", site);
        btn.innerText = site === "all" ? "전체" : site;
        
        btn.onclick = () => {
          state.selectedSiteFilter = site;
          siteButtonsEl.querySelectorAll("button").forEach(b => b.classList.remove("active"));
          btn.classList.add("active");
          filterDestinationsLocally(true);
        };
        
        siteButtonsEl.appendChild(btn);
      });
    }
    
    // Set active state
    siteButtonsEl.querySelectorAll("button").forEach(b => {
      b.classList.toggle("active", b.getAttribute("data-site") === activeSite);
    });
  }

  // 3. Filter Destinations locally by search and active site button
  const search = searchInput ? searchInput.value.toLowerCase() : "";
  const siteFilter = activeSite;
  
  if (resetPage) {
    mobilePage = 1;
  }

  const filtered = rawDests.filter(d => {
    const matchesSearch = 
      (d.dest_id || '').toLowerCase().includes(search) || 
      (d.name || '').toLowerCase().includes(search);
    const matchesSite = siteFilter === "all" || (d.site_id || '').toUpperCase() === siteFilter.toUpperCase();
    return matchesSearch && matchesSite;
  });

  if (countBadge) {
    countBadge.innerText = `검색 결과: ${filtered.length}개 목적지`;
  }

  const isMobile = window.innerWidth < 768;

  if (isMobile) {
    // Hide AG Grid, show mobile card list layout
    if (gridEl) gridEl.style.display = "none";
    if (mobileListEl) mobileListEl.style.display = "block";
    if (mobilePagerEl) mobilePagerEl.style.display = "flex";

    const totalPages = Math.max(1, Math.ceil(filtered.length / ITEMS_PER_PAGE));
    if (mobilePage > totalPages) mobilePage = totalPages;

    const pageItems = filtered.slice((mobilePage - 1) * ITEMS_PER_PAGE, mobilePage * ITEMS_PER_PAGE);

    if (mobileListEl) {
      mobileListEl.innerHTML = "";
      if (pageItems.length === 0) {
        mobileListEl.innerHTML = `<div style="text-align:center; color:var(--text-muted); padding:3rem; font-size:0.85rem;">검색 결과가 없습니다.</div>`;
      } else {
        pageItems.forEach(d => {
          const card = document.createElement("div");
          card.style.background = "var(--bg-panel)";
          card.style.border = "1px solid var(--border-color)";
          card.style.borderRadius = "8px";
          card.style.padding = "0.85rem 1rem";
          card.style.marginBottom = "0.75rem";
          card.style.boxShadow = "0 2px 8px rgba(0,0,0,0.1)";

          const target = d.target || 0;
          const success = d.success || 0;
          const pct = target > 0 ? (success / target) * 100 : 0;
          const pctColor = pct >= 100 ? 'var(--success-color)' : (pct > 0 ? 'var(--info-color)' : 'var(--text-muted)');

          card.innerHTML = `
            <div style="display:flex; justify-content:space-between; align-items:flex-start; margin-bottom:0.4rem;">
              <span style="font-size:0.75rem; color:var(--text-muted); font-weight:700;">
                ${d.site_id || 'UNKNOWN'}
              </span>
              <span class="badge ${d.is_optimizer ? 'success' : 'secondary'}" style="cursor:pointer; padding: 0.15rem 0.4rem; font-size:0.65rem;" onclick="window.updateDestOptimizer('${d.dest_id}', ${d.is_optimizer ? 0 : 1})">
                옵티마이저: ${d.is_optimizer ? 'ON' : 'OFF'}
              </span>
            </div>
            
            <h4 style="font-size:1.0rem; font-weight:800; margin:0 0 0.4rem 0; color: ${(d.name || '').startsWith('FAILED_SCRAPE_') || d.check_status === 'FAIL' ? 'var(--danger-color)' : 'var(--text-primary)'}; line-height:1.3;">
              ${(d.name || '').startsWith('FAILED_SCRAPE_') || d.check_status === 'FAIL' ? '<span class="badge danger" style="padding:0.15rem 0.35rem; font-size:0.65rem; margin-right:0.3rem;">[지도 삭제/폐업]</span>' : ''}
              ${d.name || '이름 없음'}
            </h4>
            
            <div style="font-size:0.75rem; color:var(--text-muted); display:flex; align-items:center; margin-bottom:0.75rem; background:rgba(0,0,0,0.15); padding:0.35rem 0.6rem; border-radius:4px; cursor:pointer;" onclick="window.copyToClipboard('${d.dest_id}', this)" title="클릭하여 ID 복사">
              <span>ID: <strong style="font-family:monospace; color:var(--text-primary); font-size:0.8rem; text-decoration:underline;">${d.dest_id}</strong> (터치하여 복사)</span>
            </div>
            
            <!-- 오늘 달성량 & 달성률 -->
            <div style="display:flex; justify-content:space-between; align-items:center; font-size:0.8rem; border-top:1px solid rgba(255,255,255,0.03); padding-top:0.65rem; margin-bottom:0.4rem;">
              <div>
                <span style="color:var(--text-muted); font-weight:500;">오늘 성공:</span>
                <span class="badge success" style="font-weight:800; font-size:0.75rem; padding:0.15rem 0.4rem; margin-left:0.25rem;">
                  ${d.success || 0} 성공
                </span>
                <span style="color:var(--text-muted); margin:0 0.15rem;">/</span>
                <strong style="color:var(--text-primary); font-size:0.85rem;">${d.target || 0} 목표</strong>
              </div>
              <div>
                <span style="font-weight:800; color:${pctColor}; font-size:0.9rem;">
                  ${pct.toFixed(1)}%
                </span>
              </div>
            </div>

            <!-- 오늘 실패 수 (텍스트로 깔끔히) -->
            <div style="font-size:0.75rem; margin-bottom:0.4rem; color:var(--text-muted);">
              오늘 실패: <span style="font-weight:600; color:${d.fail > 0 ? 'var(--danger-color)' : 'var(--text-primary)'};">${d.fail || 0}</span>
              ${d.fail > 0 ? ` (미노출:${d.miss || 0}|넷:${d.timeout || 0}|신원:${d.mismatch || 0})` : ''}
            </div>

            <!-- 어제 달성량 -->
            <div style="display:flex; justify-content:space-between; align-items:center; font-size:0.75rem; color:var(--text-muted); border-top:1px dashed rgba(255,255,255,0.03); padding-top:0.45rem;">
              <span>어제 성공: <strong style="color:var(--text-primary);">${d.y_success || 0}</strong></span>
              <span>어제 실패: <strong style="color:var(--text-primary);">${d.y_fail || 0}</strong></span>
            </div>
          `;
          mobileListEl.appendChild(card);
        });
      }
    }

    if (mobilePagerEl) {
      mobilePagerEl.innerHTML = `
        <button class="badge secondary" style="cursor:pointer; padding:0.35rem 0.75rem; border-radius:4px; font-weight:600;" ${mobilePage <= 1 ? 'disabled style="opacity:0.4; cursor:not-allowed;"' : 'onclick="window.changeMobileDestPage(-1)"'}>이전</button>
        <span style="color:var(--text-muted); font-weight:600;">${mobilePage} / ${totalPages} 페이지</span>
        <button class="badge secondary" style="cursor:pointer; padding:0.35rem 0.75rem; border-radius:4px; font-weight:600;" ${mobilePage >= totalPages ? 'disabled style="opacity:0.4; cursor:not-allowed;"' : 'onclick="window.changeMobileDestPage(1)"'}>다음</button>
      `;
    }
  } else {
    // Show AG Grid layout
    if (gridEl) gridEl.style.display = "block";
    if (mobileListEl) mobileListEl.style.display = "none";
    if (mobilePagerEl) mobilePagerEl.style.display = "none";

    if (state.destinationsGridApi) {
      state.destinationsGridApi.setGridOption('rowData', filtered);
      setTimeout(() => {
        state.destinationsGridApi.sizeColumnsToFit();
      }, 50);
    }
  }
}

// Render Date selector buttons dynamically
export function renderDestDateButtons(serverTodayStr) {
  const container = document.getElementById("dest-date-buttons");
  if (!container) return;
  
  const isMobile = window.innerWidth < 768;
  const expectedCount = isMobile ? 3 : 15;
  
  if (container.children.length === expectedCount) {
    // Already rendered correctly. Just toggle active states to prevent button flicker redraw.
    const selDate = state.selectedDestinationDate || serverTodayStr;
    container.querySelectorAll(".date-tab-btn").forEach(btn => {
      btn.classList.toggle("active", btn.getAttribute("data-date") === selDate);
    });
    return;
  }

  container.innerHTML = "";
  
  const baseDate = new Date(serverTodayStr + "T00:00:00");
  
  const yesterday = new Date(baseDate.getTime());
  yesterday.setDate(baseDate.getDate() - 1);
  const yesterdayStr = `${yesterday.getFullYear()}-${String(yesterday.getMonth()+1).padStart(2,'0')}-${String(yesterday.getDate()).padStart(2,'0')}`;
  
  const tomorrow = new Date(baseDate.getTime());
  tomorrow.setDate(baseDate.getDate() + 1);
  const tomorrowStr = `${tomorrow.getFullYear()}-${String(tomorrow.getMonth()+1).padStart(2,'0')}-${String(tomorrow.getDate()).padStart(2,'0')}`;

  const dates = [];
  if (isMobile) {
    dates.push(yesterdayStr, serverTodayStr, tomorrowStr);
  } else {
    for (let i = -7; i <= 7; i++) {
      const d = new Date(baseDate.getTime());
      d.setDate(baseDate.getDate() + i);
      
      const year = d.getFullYear();
      const month = String(d.getMonth() + 1).padStart(2, '0');
      const dateVal = String(d.getDate()).padStart(2, '0');
      const dateStr = `${year}-${month}-${dateVal}`;
      dates.push(dateStr);
    }
  }
  
  dates.forEach(dateStr => {
    const btn = document.createElement("button");
    btn.className = "date-tab-btn";
    btn.setAttribute("data-date", dateStr);
    
    const isSelected = state.selectedDestinationDate ? (state.selectedDestinationDate === dateStr) : (dateStr === serverTodayStr);
    if (isSelected) {
      btn.classList.add("active");
    }
    
    let label = dateStr.substring(5); // MM-DD
    if (dateStr === serverTodayStr) {
      label = "오늘";
    } else if (dateStr === yesterdayStr) {
      label = "어제";
    } else if (dateStr === tomorrowStr) {
      label = "내일";
    }
    
    btn.innerText = label;
    btn.title = dateStr;
    
    btn.onclick = async () => {
      state.selectedDestinationDate = dateStr;
      container.querySelectorAll(".date-tab-btn").forEach(b => b.classList.remove("active"));
      btn.classList.add("active");
      
      // Fetch data for the newly selected date
      await window.fetchData(true);
    };
    
    container.appendChild(btn);
  });
}

window.changeMobileDestPage = (diff) => {
  mobilePage = Math.max(1, mobilePage + diff);
  filterDestinationsLocally();
};

window.onDestSearch = () => {
  filterDestinationsLocally(true);
};

window.addEventListener('resize', () => {
  filterDestinationsLocally();
  if (state.destinationsGridApi) {
    state.destinationsGridApi.sizeColumnsToFit();
  }
});

// Bind to window for HTML event handling
window.filterDestinationsLocally = filterDestinationsLocally;
window.renderDestDateButtons = renderDestDateButtons;
