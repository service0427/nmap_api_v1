import { state } from './state.js';

export function filterDestinationsLocally() {
  if (!state.destinationsGridApi || !state.rawDestinations) return;
  const searchInput = document.getElementById("dest-search-input");
  const siteSelect = document.getElementById("dest-site-select");
  const countBadge = document.getElementById("dest-slot-count-badge");
  
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
  
  const filtered = state.rawDestinations.filter(d => {
    const matchesSearch = 
      (d.dest_id || '').toLowerCase().includes(search) || 
      (d.name || '').toLowerCase().includes(search);
    const matchesSite = siteFilter === "all" || (d.site_id || '').toUpperCase() === siteFilter.toUpperCase();
    return matchesSearch && matchesSite;
  });

  state.destinationsGridApi.setGridOption('rowData', filtered);
  
  if (countBadge) {
    countBadge.innerText = `검색 결과: ${filtered.length}개 목적지`;
  }
}

// Bind to window for HTML event handling
window.filterDestinationsLocally = filterDestinationsLocally;
window.onDestSearch = filterDestinationsLocally;
