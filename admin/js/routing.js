import { state } from './state.js?v=1.1.23';

// Switch Tabs and update Endpoint History URL
export function switchTab(tabId, pushState = true) {
  state.currentTab = tabId;
  
  // Navigation Active styling
  document.querySelectorAll(".nav-btn").forEach(btn => {
    btn.classList.remove("active");
  });
  const targetNav = document.getElementById(`nav-${tabId}`);
  if (targetNav) targetNav.classList.add("active");

  // Visibility content toggle
  document.querySelectorAll(".tab-content").forEach(tab => {
    tab.classList.remove("active");
  });
  const targetTab = document.getElementById(`tab-${tabId}`);
  if (targetTab) targetTab.classList.add("active");
  
  // Push history state to match exact FastAPI endpoints
  if (pushState) {
    const path = tabId === 'summary' ? '/' : '/' + tabId;
    history.pushState({ tabId }, '', path);
  }
  
  // Resize ag-Grids to prevent layout overflow
  setTimeout(() => {
    if (tabId === 'destinations' && state.destinationsGridApi) state.destinationsGridApi.sizeColumnsToFit();
    if (tabId === 'logs' && state.logsGridApi) state.logsGridApi.sizeColumnsToFit();
  }, 30);
  
  if (window.lucide) {
    window.lucide.createIcons();
  }
}

// Bind switchTab to global window scope so HTML onclick handlers can find it
window.switchTab = switchTab;

export function initRouting() {
  // Handle Browser Popstate Action (Back/Forward navigation)
  window.addEventListener('popstate', (event) => {
    const pathName = window.location.pathname.replace(/^\/|\/$/g, '');
    let tab = 'summary';
    if (['summary', 'devices', 'destinations', 'lte', 'logs'].includes(pathName)) {
      tab = pathName;
    }
    switchTab(tab, false);
  });
}
