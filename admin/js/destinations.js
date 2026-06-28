import { state } from './state.js';

let mobilePage = 1;
const ITEMS_PER_PAGE = 30;

export function filterDestinationsLocally(resetPage = false) {
  if (!state.rawDestinations) return;
  
  const searchInput = document.getElementById("dest-search-input");
  const siteSelect = document.getElementById("dest-site-select");
  const countBadge = document.getElementById("dest-slot-count-badge");
  
  const gridEl = document.getElementById("grid-destinations");
  const mobileListEl = document.getElementById("mobile-destinations-list");
  const mobilePagerEl = document.getElementById("mobile-destinations-pagination");

  if (siteSelect) {
    const uniqueSites = [...new Set(state.rawDestinations.map(d => (d.site_id || '').toUpperCase()).filter(Boolean))].sort();
    const existingOptions = Array.from(siteSelect.options).map(o => o.value).filter(v => v !== "all").sort();
    const isSame = uniqueSites.length === existingOptions.length && uniqueSites.every((v, i) => v === existingOptions[i]);
    
    if (!isSame) {
      const currentVal = siteSelect.value;
      siteSelect.innerHTML = '<option value="all">전체 사이트</option>';
      uniqueSites.forEach(site => {
        const option = document.createElement("option");
        option.value = site;
        option.innerText = site;
        siteSelect.appendChild(option);
      });
      if (uniqueSites.includes(currentVal.toUpperCase()) || currentVal === "all") {
        siteSelect.value = currentVal;
      } else {
        siteSelect.value = "all";
      }
    }
  }

  const search = searchInput ? searchInput.value.toLowerCase() : "";
  const siteFilter = siteSelect ? siteSelect.value : "all";
  
  if (resetPage) {
    mobilePage = 1;
  }

  const filtered = state.rawDestinations.filter(d => {
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
    // Hide AG Grid, show mobile layout
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

          const checkBadgeClass = d.check_status === 'VERIFIED' ? 'success' : 
                                  (d.check_status === 'NORMAL' ? 'info' : 
                                  (d.check_status === 'PENDING' ? 'warning' : 'danger'));
          const checkStatusText = d.check_status === 'VERIFIED' ? '검증 완료' :
                                  (d.check_status === 'NORMAL' ? '일반' :
                                  (d.check_status === 'PENDING' ? '대기' : (d.check_status || '실패')));

          card.innerHTML = `
            <div style="display:flex; justify-content:space-between; align-items:flex-start; margin-bottom:0.4rem;">
              <div style="display:flex; align-items:center; gap:0.25rem;">
                <span class="badge ${d.slot_status === 'on' ? 'success' : 'danger'}" style="font-size:0.65rem; padding:0.1rem 0.35rem;">
                  ${d.slot_status === 'on' ? '활성' : '비활성'}
                </span>
                <span class="badge ${checkBadgeClass}" style="font-size:0.65rem; padding:0.1rem 0.35rem;">
                  ${checkStatusText}
                </span>
              </div>
              <span style="font-size:0.65rem; color:var(--text-muted); font-weight:600; background:rgba(255,255,255,0.03); padding:0.1rem 0.3rem; border-radius:3px;">
                ${d.site_id || 'UNKNOWN'}
              </span>
            </div>
            
            <h4 style="font-size:1.0rem; font-weight:800; margin:0 0 0.4rem 0; color:var(--text-primary); line-height:1.3;">
              ${d.name || '이름 없음'}
            </h4>
            
            <div style="font-size:0.75rem; color:var(--text-muted); display:flex; justify-content:space-between; align-items:center; margin-bottom:0.75rem; background:rgba(0,0,0,0.15); padding:0.35rem 0.6rem; border-radius:4px;">
              <span>ID: <strong style="font-family:monospace; color:var(--text-primary); font-size:0.8rem;">${d.dest_id}</strong></span>
              <button class="badge secondary" style="cursor:pointer; padding: 0.15rem 0.4rem; font-size:0.65rem; border:1px solid var(--border-color);" onclick="window.copyToClipboard('${d.dest_id}', this)">ID 복사</button>
            </div>
            
            <div style="display:flex; justify-content:space-between; align-items:center; font-size:0.8rem; border-top:1px solid rgba(255,255,255,0.03); padding-top:0.65rem; margin-bottom:0.65rem;">
              <div>
                <span style="color:var(--text-muted);">달성/목표:</span>
                <span class="badge success" style="font-weight:800; font-size:0.75rem; padding:0.15rem 0.4rem; margin-left:0.25rem;">
                  ${d.success || 0} 성공
                </span>
                <span style="color:var(--text-muted); margin:0 0.15rem;">/</span>
                <strong style="color:var(--text-primary); font-size:0.85rem;">${d.target || 0}</strong>
              </div>
              <div>
                <span class="badge ${d.fail > 0 ? 'danger' : 'secondary'}" style="font-weight:700; font-size:0.65rem; padding:0.1rem 0.35rem;">
                  실패: ${d.fail || 0}
                </span>
              </div>
            </div>
            
            <div style="display:flex; justify-content:space-between; align-items:center; background:rgba(255,255,255,0.01); border:1px solid var(--border-color); padding:0.45rem 0.65rem; border-radius:6px;">
              <span style="font-size:0.7rem; font-weight:600; color:var(--text-muted);">GPS 옵티마이저</span>
              <span class="badge ${d.is_optimizer ? 'success' : 'secondary'}" style="cursor:pointer; padding: 0.2rem 0.5rem; font-size:0.65rem; font-weight:700;" onclick="window.updateDestOptimizer('${d.dest_id}', ${d.is_optimizer ? 0 : 1})">
                ${d.is_optimizer ? 'ON' : 'OFF'}
              </span>
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
    }
  }
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
});

// Bind to window for HTML event handling
window.filterDestinationsLocally = filterDestinationsLocally;
