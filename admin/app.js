import { initRouting, switchTab } from './js/routing.js';
import { initClock } from './js/clock.js';
import { initGrids } from './js/grids.js';
import { fetchData } from './js/api.js';

// Import other scripts to register global handlers on window automatically
import './js/modals.js';
import './js/devices.js';
import './js/lte.js';
import './js/destinations.js';

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
