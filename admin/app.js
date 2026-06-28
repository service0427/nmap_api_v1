import { initRouting, switchTab } from './js/routing.js?v=1.1.15';
import { initClock } from './js/clock.js?v=1.1.15';
import { initGrids } from './js/grids.js?v=1.1.15';
import { fetchData } from './js/api.js?v=1.1.15';

// Import other scripts to register global handlers on window automatically
import './js/modals.js?v=1.1.15';
import './js/devices.js?v=1.1.15';
import './js/lte.js?v=1.1.15';
import './js/destinations.js?v=1.1.15';

document.addEventListener("DOMContentLoaded", () => {
  // Initialize ag-Grids
  initGrids();
  
  // Parse initial path and route active tab
  const pathName = window.location.pathname.replace(/^\/|\/$/g, '');
  let initialTab = 'summary';
  if (['summary', 'devices', 'destinations', 'lte', 'logs'].includes(pathName)) {
    initialTab = pathName;
  }
  
  // Setup routing
  initRouting();
  switchTab(initialTab, false);
  
  // Fetch initial state
  fetchData();
  
  // Setup clock KST badge
  initClock();
  
  // Setup periodic refresh (every 10s)
  setInterval(() => {
    fetchData(false);
  }, 10000);
});
