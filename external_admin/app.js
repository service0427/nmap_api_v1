let siteType = 'FSD';
let isFetching = false;
let nextRefreshSeconds = 10;
let timerInterval = null;

function logTrace(step, info = {}) {
  fetch('/api/v1/log-error', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ trace_step: step, info: info })
  }).catch(() => {});
}

window.showWorkDetail = async function(name, destId) {
  const modal = document.getElementById("history-modal");
  const destNameEl = document.getElementById("modal-dest-name");
  const destIdEl = document.getElementById("modal-dest-id");
  const tbody = document.getElementById("modal-history-tbody");
  
  if (!modal || !tbody) return;
  
  // Set meta info
  destNameEl.textContent = name;
  destIdEl.textContent = destId;
  
  // Clear table first
  tbody.replaceChildren();
  
  // Add loading row
  const trLoading = document.createElement("tr");
  const tdLoading = document.createElement("td");
  tdLoading.colSpan = 5;
  tdLoading.style.textAlign = "center";
  tdLoading.style.padding = "2rem";
  tdLoading.style.color = "var(--text-muted)";
  tdLoading.textContent = "데이터 로딩 중...";
  trLoading.appendChild(tdLoading);
  tbody.appendChild(trLoading);
  
  // Show modal
  modal.style.display = "flex";
  
  try {
    const res = await fetch(`/api/v1/external/history?site=${siteType}&dest_id=${destId}`);
    if (!res.ok) throw new Error("HTTP Error");
    const data = await res.json();
    
    // Clear loading
    tbody.replaceChildren();
    
    const history = data.history || [];
    if (history.length === 0) {
      const trEmpty = document.createElement("tr");
      const tdEmpty = document.createElement("td");
      tdEmpty.colSpan = 5;
      tdEmpty.style.textAlign = "center";
      tdEmpty.style.padding = "2rem";
      tdEmpty.style.color = "var(--text-muted)";
      tdEmpty.textContent = "작업 내역이 없습니다.";
      trEmpty.appendChild(tdEmpty);
      tbody.appendChild(trEmpty);
      return;
    }
    
    const formatTime = (timeStr) => {
      if (!timeStr) return "-";
      return timeStr.replace("T", " ");
    };
    
    const calculateDuration = (durationSec, startTime, endTime) => {
      if (durationSec && durationSec > 0) return `${durationSec}초`;
      if (!startTime || !endTime) return "-";
      try {
        const start = new Date(startTime);
        const end = new Date(endTime);
        const diffMs = end - start;
        if (isNaN(diffMs) || diffMs < 0) return "-";
        return `${Math.round(diffMs / 1000)}초`;
      } catch (e) {
        return "-";
      }
    };
    
    const getBadgeClass = (status) => {
      const s = status.toUpperCase();
      if (s === "SUCCESS") return "success";
      if (s.startsWith("FAIL") || s.startsWith("ERR")) return "fail";
      if (s === "WORKING" || s === "IP_CHANGED" || s === "SELECTING_DEST" || s === "ALLOCATED") return "working";
      return "other";
    };
    
    history.forEach(item => {
      const tr = document.createElement("tr");
      
      // 1. Start Time
      const tdStart = document.createElement("td");
      tdStart.style.fontFamily = "monospace";
      tdStart.textContent = formatTime(item.start_time);
      tr.appendChild(tdStart);
      
      // 2. End Time
      const tdEnd = document.createElement("td");
      tdEnd.style.fontFamily = "monospace";
      tdEnd.textContent = formatTime(item.end_time);
      tr.appendChild(tdEnd);
      
      // 3. Duration
      const tdDuration = document.createElement("td");
      tdDuration.style.fontFamily = "monospace";
      tdDuration.style.textAlign = "right";
      tdDuration.textContent = calculateDuration(item.duration_sec, item.start_time, item.end_time);
      tr.appendChild(tdDuration);
      
      // 4. Status Badge
      const tdStatus = document.createElement("td");
      tdStatus.style.textAlign = "center";
      const badge = document.createElement("span");
      badge.className = `badge-status ${getBadgeClass(item.status)}`;
      badge.textContent = item.status.toUpperCase();
      tdStatus.appendChild(badge);
      tr.appendChild(tdStatus);
      
      // 5. Result Message
      const tdMsg = document.createElement("td");
      tdMsg.style.fontSize = "0.775rem";
      tdMsg.style.color = "var(--text-muted)";
      tdMsg.textContent = item.result_msg || "-";
      tr.appendChild(tdMsg);
      
      tbody.appendChild(tr);
    });
  } catch (err) {
    console.error("Fetch history error:", err);
    tbody.replaceChildren();
    const trError = document.createElement("tr");
    const tdError = document.createElement("td");
    tdError.colSpan = 5;
    tdError.style.textAlign = "center";
    tdError.style.padding = "2rem";
    tdError.style.color = "#ef4444";
    tdError.textContent = "데이터를 불러오는 중 오류가 발생했습니다.";
    trError.appendChild(tdError);
    tbody.appendChild(trError);
  }
};

// Server-side pagination and filter states (100 rows by default)
let currentPage = 1;
let pageSize = 100;
let totalItems = 0;
let statusFilter = 'active'; // Default tab: active (사용 중)

// ag-Grid API reference
let gridApi = null;

// Parse current endpoint to set FSD or LUP mode
const pathName = window.location.pathname.replace(/^\/|\/$/g, '').toUpperCase();
if (pathName === 'LUP' || pathName === 'LUF') {
  siteType = 'LUP';
} else {
  siteType = 'FSD';
}

// ag-Grid options configuration
const gridOptions = {
  columnDefs: [
    { 
      field: 'dest_id', 
      headerName: '코드', 
      width: 100, 
      minWidth: 90, 
      suppressSizeToFit: true,
      cellRenderer: params => {
        if (!params.data) return '';
        return `<span style="font-family: monospace; font-size: 0.8rem; color: var(--text-muted);">${params.value}</span>`;
      }
    },
    { 
      field: 'name', 
      headerName: '목적지', 
      flex: 1, 
      minWidth: 160, 
      cellRenderer: params => {
        if (!params.data) return '';
        return `<strong style="color: #ffffff; font-size: 0.85rem;">${params.value}</strong>`;
      }
    },
    { 
      field: 'slot_status', 
      headerName: '슬롯 상태', 
      width: 80, 
      minWidth: 80, 
      suppressSizeToFit: true,
      cellRenderer: params => {
        if (!params.data) return '';
        const isRun = params.value === 'on';
        const badgeClass = isRun ? 'success' : 'danger';
        return `<span class="badge ${badgeClass}">${params.value.toUpperCase()}</span>`;
      }
    },
    { 
      field: 'target', 
      headerName: '목표', 
      width: 55, 
      minWidth: 50, 
      suppressSizeToFit: true,
      cellRenderer: params => {
        if (!params.data) return '';
        return `<span style="font-family: monospace; font-weight: 700; color: var(--color-primary);">${params.value}</span>`;
      }
    },
    { 
      field: 'success', 
      headerName: '성공', 
      width: 55, 
      minWidth: 50, 
      suppressSizeToFit: true,
      cellRenderer: params => {
        if (!params.data) return '';
        return `<span style="font-family: monospace; font-weight: 700; color: #ffffff;">${params.value}</span>`;
      }
    },
    { 
      field: 'fail', 
      headerName: '실패', 
      width: 55, 
      minWidth: 50, 
      suppressSizeToFit: true,
      cellRenderer: params => {
        if (!params.data) return '';
        const failColor = params.value > 0 ? '#ef4444' : 'rgba(239, 68, 68, 0.4)';
        return `<span style="font-family: monospace; font-weight: 700; color: ${failColor};">${params.value}</span>`;
      }
    },
    { 
      field: 'rate', 
      headerName: '진행도', 
      width: 120, 
      minWidth: 110, 
      suppressSizeToFit: true,
      cellRenderer: params => {
        if (!params.data) return '';
        const rate = params.data.target > 0 ? Math.round((params.data.success / params.data.target) * 100) : 0;
        return `
          <div style="display:flex; align-items:center; gap:0.5rem; width:100%; height: 100%;">
            <div class="progress-bar" style="flex: 1;">
              <div class="progress-fill" style="width:${Math.min(100, rate)}%;"></div>
            </div>
            <span style="font-weight:700; font-size:0.75rem; font-family:monospace; min-width:32px; text-align:right;">${rate}%</span>
          </div>
        `;
      }
    },
    { 
      field: 'start_date', 
      headerName: '시작일', 
      width: 65, 
      minWidth: 65, 
      suppressSizeToFit: true,
      cellRenderer: params => {
        if (!params.data) return '';
        let val = params.value ? params.value : '';
        if (val && val.length >= 10 && val.charAt(4) === '-') {
          val = val.substring(5);
        }
        const startDate = val ? val : '미지정';
        return `<span style="font-family: monospace; font-size: 0.75rem; color: var(--text-muted);">${startDate}</span>`;
      }
    },
    { 
      field: 'end_date', 
      headerName: '만료일', 
      width: 65, 
      minWidth: 65, 
      suppressSizeToFit: true,
      cellRenderer: params => {
        if (!params.data) return '';
        let val = params.value ? params.value : '';
        if (val && val.length >= 10 && val.charAt(4) === '-') {
          val = val.substring(5);
        }
        const expDate = val ? val : '미지정';
        return `<span style="font-family: monospace; font-size: 0.75rem; color: var(--text-muted);">${expDate}</span>`;
      }
    },
    { 
      headerName: '상세보기', 
      width: 85, 
      minWidth: 80, 
      suppressSizeToFit: true,
      cellRenderer: params => {
        if (!params.data) return '';
        return `
          <button class="btn secondary sm" style="padding: 0.2rem 0.5rem; min-height: 24px; font-size: 0.75rem;" 
                  onclick="showWorkDetail('${params.data.name.replace(/'/g, "\\'")}', '${params.data.dest_id}')">
            상세보기
          </button>
        `;
      }
    }
  ],
  domLayout: 'normal',
  rowHeight: 52,
  headerHeight: 44,
  suppressCellFocus: true,
  autoSizeStrategy: { type: 'fitGridWidth' }
};

// Set UI Themes and event listeners based on Site ID
document.addEventListener("DOMContentLoaded", () => {
  logTrace("DOMContentLoaded_start", { siteType, statusFilter });
  const root = document.documentElement;
  const titleEl = document.getElementById("header-logo-title");
  
  if (siteType === 'LUP') {
    // Indigo theme for LUP
    root.style.setProperty('--color-primary', '#6366f1');
    root.style.setProperty('--color-primary-glow', 'rgba(99, 102, 241, 0.15)');
    titleEl.innerText = "LUP EXTERNAL MONITOR";
    document.title = "LUP EXTERNAL MONITOR";
  } else {
    // Emerald theme for FSD
    root.style.setProperty('--color-primary', '#10b981');
    root.style.setProperty('--color-primary-glow', 'rgba(16, 185, 129, 0.15)');
    titleEl.innerText = "FSD EXTERNAL MONITOR";
    document.title = "FSD EXTERNAL MONITOR";
  }
  
  // Setup tabs event listeners
  const tabButtons = document.querySelectorAll(".tab-btn");
  tabButtons.forEach(btn => {
    btn.addEventListener("click", (e) => {
      tabButtons.forEach(b => b.classList.remove("active"));
      e.currentTarget.classList.add("active");
      statusFilter = e.currentTarget.getAttribute("data-status");
      triggerSearch();
    });
  });
  
  // Initialize ag-Grid
  const gridDiv = document.querySelector('#myGrid');
  gridApi = agGrid.createGrid(gridDiv, gridOptions);
  logTrace("grid_created", { gridApiExists: !!gridApi, hasSetGridOption: gridApi ? typeof gridApi.setGridOption : 'none' });
  
  // Fit columns to width on window resize
  window.addEventListener("resize", () => {
    if (gridApi) {
      gridApi.sizeColumnsToFit();
    }
  });
  
  fetchData();
  setInterval(updateClock, 1000);
  
  // Start Countdown Timer
  startCountdown();

  // Modal close event handlers
  const modal = document.getElementById("history-modal");
  const closeBtn = document.getElementById("modal-close-btn");
  if (closeBtn && modal) {
    closeBtn.addEventListener("click", () => {
      modal.style.display = "none";
    });
    
    // Close when clicking outside content
    modal.addEventListener("click", (e) => {
      if (e.target === modal) {
        modal.style.display = "none";
      }
    });
  }
  
  // Close on Escape key
  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape" && modal && modal.style.display === "flex") {
      modal.style.display = "none";
    }
  });
});

function updateClock() {
  const now = new Date();
  const options = { timeZone: 'Asia/Seoul', hour: '2-digit', minute: '2-digit', second: '2-digit', hour12: false };
  const timeStr = now.toLocaleTimeString('ko-KR', options);
  const kstBadge = document.getElementById("kst-timer");
  if (kstBadge) {
    kstBadge.innerHTML = `<i data-lucide="clock" style="width: 14px; height: 14px;"></i>KST ${timeStr}`;
  }
}

function startCountdown() {
  if (timerInterval) clearInterval(timerInterval);
  
  nextRefreshSeconds = 10;
  const timerEl = document.getElementById("update-countdown");
  timerEl.innerText = `${nextRefreshSeconds}초 후 갱신`;
  
  timerInterval = setInterval(() => {
    nextRefreshSeconds--;
    if (nextRefreshSeconds <= 0) {
      timerEl.innerText = "갱신 중...";
      fetchData(true); // soft background refresh
      nextRefreshSeconds = 10;
    } else {
      timerEl.innerText = `${nextRefreshSeconds}초 후 갱신`;
    }
  }, 1000);
}

// Search trigger
function triggerSearch() {
  currentPage = 1;
  fetchData();
}

// Auto search trigger on code ID input (runs autocomplete logic)
window.onCodeInput = function(value) {
  if (value.length >= 4 || value.length === 0) {
    triggerSearch();
  }
};

// Page Size Change Callback
window.onPageSizeChange = function(value) {
  pageSize = parseInt(value, 10);
  currentPage = 1;
  fetchData();
};

// Direct page jump selection callback
window.jumpToPage = function(value) {
  const pageNum = parseInt(value, 10);
  const maxPages = Math.ceil(totalItems / pageSize) || 1;
  if (pageNum >= 1 && pageNum <= maxPages) {
    currentPage = pageNum;
    fetchData();
  } else {
    alert(`1에서 ${maxPages} 사이의 페이지 번호를 입력해주세요.`);
    document.getElementById("page-jump-input").value = currentPage;
  }
};

// Change Page Number
function changePage(direction) {
  const newPage = currentPage + direction;
  const maxPages = Math.ceil(totalItems / pageSize) || 1;
  if (newPage >= 1 && newPage <= maxPages) {
    currentPage = newPage;
    fetchData();
  }
}

// Fetch summary & destinations stats API
async function fetchData(background = false) {
  if (isFetching) return;
  isFetching = true;
  
  const refreshIcon = document.getElementById("refresh-icon");
  if (refreshIcon) refreshIcon.classList.add("spinning");
  
  const search = document.getElementById("dest-search-input").value;
  const code = document.getElementById("code-search-input").value;
  const status = statusFilter;
  
  try {
    const res = await fetch(`/api/v1/external/summary?site=${siteType}&page=${currentPage}&page_size=${pageSize}&search=${encodeURIComponent(search)}&code=${encodeURIComponent(code)}&status=${status}`);
    if (!res.ok) throw new Error("HTTP Error");
    const data = await res.json();
    logTrace("fetch_data_success", { total_count: data.total_count, destinations_length: data.destinations ? data.destinations.length : 0 });
    
    totalItems = data.total_count || 0;
    updateUI(data);
  } catch (err) {
    logTrace("fetch_data_error", { error: err.toString() });
    console.error("Fetch Error:", err);
  } finally {
    isFetching = false;
    if (refreshIcon) {
      setTimeout(() => {
        refreshIcon.classList.remove("spinning");
      }, 400);
    }
    // Reset countdown after reload
    nextRefreshSeconds = 10;
    document.getElementById("update-countdown").innerText = `${nextRefreshSeconds}초 후 갱신`;
  }
}

function updateUI(data) {
  // 1. Statistics Summary
  const summary = data.summary || { target: 0, success: 0, fail: 0, remain: 0 };
  
  // Calculate percentage
  const successPct = summary.target > 0 ? Math.round((summary.success / summary.target) * 100) : 0;
  
  // Numbers transition
  document.getElementById("stats-target").innerText = summary.target.toLocaleString();
  document.getElementById("stats-success").innerText = summary.success.toLocaleString();
  document.getElementById("stats-remain").innerText = summary.remain.toLocaleString();
  document.getElementById("stats-fail").innerText = summary.fail.toLocaleString();
  document.getElementById("stats-percent").innerText = `${successPct}%`;
  
  // Update linear progress bar
  const progressFill = document.getElementById("stats-progress-fill");
  if (progressFill) {
    progressFill.style.width = `${Math.min(100, successPct)}%`;
  }
  
  // Update bottom metadata text
  const siteName = siteType === 'LUP' ? 'LUP' : 'FSD';
  document.getElementById("showcase-title").innerText = `${siteName} 진행도`;
  
  // 2. Pagination bar updates
  const totalPages = Math.ceil(totalItems / pageSize) || 1;
  document.getElementById("page-num-badge").innerText = `Page ${currentPage} / ${totalPages}`;
  
  const startItem = totalItems > 0 ? (currentPage - 1) * pageSize + 1 : 0;
  const endItem = Math.min(totalItems, currentPage * pageSize);
  document.getElementById("pagination-info-text").innerText = `전체 ${totalItems.toLocaleString()}개 항목 중 ${startItem} - ${endItem} 표시 중`;
  
  document.getElementById("btn-prev-page").disabled = (currentPage <= 1);
  document.getElementById("btn-next-page").disabled = (currentPage >= totalPages);
  document.getElementById("dest-total-count-badge").innerText = `조회 건수: ${totalItems.toLocaleString()}개`;
  
  // Sync page jump inputs
  const pageJumpInput = document.getElementById("page-jump-input");
  if (pageJumpInput) {
    pageJumpInput.value = currentPage;
    pageJumpInput.max = totalPages;
  }

  // 3. Update ag-Grid Row Data
  if (gridApi) {
    const rowData = data.destinations || [];
    if (typeof gridApi.setGridOption === 'function') {
      gridApi.setGridOption('rowData', rowData);
    } else if (typeof gridApi.setRowData === 'function') {
      gridApi.setRowData(rowData);
    }
    // Autoscale columns to fit
    setTimeout(() => {
      gridApi.sizeColumnsToFit();
    }, 50);
  }
  
  logTrace("updateUI_end", { destinations_length: data.destinations ? data.destinations.length : 0 });
  lucide.createIcons();
}
