import { state } from './state.js';

export function toggleTotalDeviceList() {
  state.isTotalListOpen = !state.isTotalListOpen;
  const content = document.getElementById("total-list-toggle-content");
  const text = document.getElementById("toggle-list-text");
  const icon = document.getElementById("toggle-list-icon");
  
  if (state.isTotalListOpen) {
    if (content) content.style.display = "block";
    if (text) text.innerText = "클릭하여 접기";
    if (icon) icon.setAttribute("data-lucide", "chevron-up");
    filterDevicesLocally(); // Force render when opened
  } else {
    if (content) content.style.display = "none";
    if (text) text.innerText = "클릭하여 펼치기";
    if (icon) icon.setAttribute("data-lucide", "chevron-down");
  }
  if (window.lucide) {
    window.lucide.createIcons();
  }
}

export function updateCriticalAlertMonitor(backendAlarms) {
  const monitorBox = document.getElementById("devices-alert-monitor");
  const monitorBody = document.getElementById("devices-alert-body");
  if (!monitorBox || !monitorBody) return;
  
  const deviceAlarms = (backendAlarms || []).filter(a => a.type === "DEVICE");

  if (deviceAlarms.length > 0) {
    const hasDanger = deviceAlarms.some(a => a.level === 'danger');
    monitorBox.className = `critical-alert-box alert-active ${hasDanger ? 'danger-alert' : 'warning-alert'}`;
    monitorBox.style.borderColor = hasDanger ? "var(--color-danger)" : "var(--color-warning)";
    
    let html = `
      <div class="alert-header-row" style="color: ${hasDanger ? 'var(--color-danger)' : 'var(--color-warning)'}">
        <i data-lucide="${hasDanger ? 'alert-octagon' : 'alert-triangle'}" style="width: 18px; height: 18px;"></i>
        <span>실시간 장애 감지: 총 ${deviceAlarms.length}대의 장비가 통신 지연 또는 에러 상태입니다!</span>
      </div>
      <div style="display:flex; flex-wrap:wrap; gap:0.5rem; margin-top:0.5rem;">
    `;
    deviceAlarms.forEach(a => {
      const badgeClass = a.level === 'danger' ? 'danger' : 'warning';
      const borderRGBA = a.level === 'danger' ? 'rgba(239, 68, 68, 0.3)' : 'rgba(245, 158, 11, 0.3)';
      html += `
        <span class="badge ${badgeClass}" style="padding: 0.25rem 0.5rem; font-size:0.75rem; border-color: ${borderRGBA};">
          <strong>${a.target}</strong> (${a.msg})
        </span>
      `;
    });
    html += `</div>`;
    monitorBody.innerHTML = html;
  } else {
    monitorBox.className = "critical-alert-box alert-safe";
    monitorBox.style.borderColor = "var(--color-primary)";
    monitorBody.innerHTML = `
      <div class="alert-header-row" style="color: var(--color-primary)">
        <i data-lucide="shield-check" style="width: 18px; height: 18px;"></i>
        <span>안전: 현재 20분 이상 장애 기기가 없습니다.</span>
      </div>
      <div style="font-size:0.75rem; color: var(--text-muted); margin-top: 0.15rem;">
        전체 디바이스가 20분 이내에 활발하게 통신 중이며 정상 동작하고 있습니다.
      </div>
    `;
  }
  if (window.lucide) {
    window.lucide.createIcons();
  }
}

export function switchDeviceViewMode(mode) {
  state.deviceViewMode = mode;
  
  // Highlight active button
  const modes = ['accordion', 'compact', 'table'];
  modes.forEach(m => {
    const btn = document.getElementById(`btn-view-${m}`);
    if (btn) {
      if (m === mode) btn.classList.add('active');
      else btn.classList.remove('active');
    }
  });

  // Toggle container visibility
  const accordionContainer = document.getElementById('devices-accordion-container');
  const compactContainer = document.getElementById('devices-compact-container');
  const tableContainer = document.getElementById('devices-table-container');

  if (accordionContainer) accordionContainer.style.display = mode === 'accordion' ? 'block' : 'none';
  if (compactContainer) compactContainer.style.display = mode === 'compact' ? 'block' : 'none';
  if (tableContainer) tableContainer.style.display = mode === 'table' ? 'block' : 'none';

  filterDevicesLocally();
}

export function updateEfficiencyBoard(devices) {
  const activeRatioEl = document.getElementById('eff-active-ratio');
  const compareSuccessEl = document.getElementById('eff-compare-success');
  const successRateEl = document.getElementById('eff-success-rate');

  if (!activeRatioEl || !compareSuccessEl || !successRateEl) return;

  const total = devices.length;
  const active = devices.filter(d => d.status === 'ON').length;
  const activePercent = total > 0 ? Math.round((active / total) * 100) : 0;

  activeRatioEl.innerText = `${active} / ${total}대 (${activePercent}%)`;

  // From state (loaded from /api/v1/admin/summary API)
  const todaySuccess = state.totalTodaySuccess || 0;
  const yesterdaySuccess = state.totalYesterdaySuccess || 0;
  const successDiff = todaySuccess - yesterdaySuccess;
  const successDiffPct = yesterdaySuccess > 0 ? ((successDiff / yesterdaySuccess) * 100).toFixed(1) : 0;
  const diffSign = successDiff >= 0 ? '+' : '';

  compareSuccessEl.innerHTML = `
    ${todaySuccess} <span style="font-size:0.75rem; color:var(--text-muted);">/ ${yesterdaySuccess}</span>
    <span style="font-size:0.7rem; color:${successDiff >= 0 ? 'var(--color-success)' : 'var(--color-danger)'}; margin-left:0.25rem;">
      (${diffSign}${successDiff}건, ${diffSign}${successDiffPct}%)
    </span>
  `;

  let totalSuccess = 0;
  let totalFail = 0;
  devices.forEach(d => {
    totalSuccess += (d.today_success || 0);
    totalFail += (d.today_fail || 0);
  });
  const totalTasks = totalSuccess + totalFail;
  const successRate = totalTasks > 0 ? ((totalSuccess / totalTasks) * 100).toFixed(1) : '0.0';

  successRateEl.innerText = `${successRate}%`;
}

export function filterDevicesLocally() {
  if (!state.rawDevices) return;
  
  const searchInput = document.getElementById("device-search-input");
  const statusSelect = document.getElementById("device-status-select");
  
  const search = searchInput ? searchInput.value.toLowerCase() : "";
  const statusFilter = statusSelect ? statusSelect.value : "all";
  
  const filtered = state.rawDevices.filter(d => {
    const isAlerting = d.status === 'ERROR' || 
                       (d.status === 'ON' && d.silence_level === 'danger') || 
                       ((d.today_fail || 0) >= 5 && (d.today_fail || 0) > (d.today_success || 0));
    const matchesSearch = 
      (d.hostname || '').toLowerCase().includes(search) || 
      d.device_id.toLowerCase().includes(search) || 
      (d.current_ip || '').toLowerCase().includes(search) ||
      (d.install_place || '').toLowerCase().includes(search);
    
    let matchesStatus = true;
    if (statusFilter === 'on') matchesStatus = d.status === 'ON';
    else if (statusFilter === 'off') matchesStatus = d.status === 'OFF' && !isAlerting;
    else if (statusFilter === 'error') matchesStatus = isAlerting;
    
    return matchesSearch && matchesStatus;
  });

  // 1. Efficiency Board Update
  updateEfficiencyBoard(filtered);

  if (!state.isTotalListOpen) return;

  // 2. Render Based on Selected View Mode
  const mode = state.deviceViewMode || 'accordion';

  if (mode === 'accordion') {
    renderAccordionView(filtered);
  } else if (mode === 'compact') {
    renderCompactView(filtered);
  } else if (mode === 'table') {
    renderTableView(filtered);
  }
}

function renderAccordionView(filteredDevices) {
  const container = document.getElementById("devices-accordion-container");
  if (!container) return;

  const groups = {};
  filteredDevices.forEach(d => {
    const hostnameStr = (d.hostname || '').trim();
    let groupName = '기타 장비';
    
    if (hostnameStr) {
      const pcMatch = hostnameStr.match(/^(PC[-_\s]?\d+)/i);
      const upMatch = hostnameStr.match(/^([UP][-_\s]?\d+|[UP]\d+)/i);
      
      if (pcMatch) {
        groupName = pcMatch[1].toUpperCase();
      } else if (upMatch) {
        groupName = hostnameStr.toUpperCase();
      } else {
        groupName = '기타 장비';
      }
    }
    
    if (!groups[groupName]) {
      groups[groupName] = [];
    }
    groups[groupName].push(d);
  });

  container.innerHTML = "";
  
  const sortedGroupKeys = Object.keys(groups).sort((a, b) => a.localeCompare(b, 'ko'));
  
  if (sortedGroupKeys.length === 0) {
    container.innerHTML = `<div style="text-align: center; color: var(--text-muted); padding: 3rem; font-size:0.85rem;">조건에 맞는 디바이스가 존재하지 않습니다.</div>`;
    return;
  }

  sortedGroupKeys.forEach(groupName => {
    const devicesInGroup = groups[groupName];
    devicesInGroup.sort((a, b) => (a.device_id || '').localeCompare(b.device_id || '', 'ko'));
    
    let activeCount = 0;
    let errorCount = 0;
    let totalQty = 0;
    const groupDeviceIds = devicesInGroup.map(x => x.device_id);
    devicesInGroup.forEach(x => {
      totalQty += (x.install_count || 1);
      if (x.status === 'ON') activeCount++;
      if (x.status === 'ERROR' || (x.today_fail || 0) >= 5) errorCount++;
    });
    
    const firstPlace = devicesInGroup[0].install_place || "장소 미정";

    const groupDiv = document.createElement("div");
    groupDiv.className = "accordion-group";
    
    const isOpen = state.openedGroups[groupName] !== false;
    const toggleIcon = isOpen ? "chevron-up" : "chevron-down";
    
    groupDiv.innerHTML = `
      <div class="accordion-header" onclick="window.toggleAccordion('${groupName}')">
        <div class="accordion-title">
          <i data-lucide="monitor" style="width:16px; height:16px; color:var(--color-primary)"></i>
          <span>${groupName}</span>
          <span class="badge ${errorCount > 0 ? 'danger' : 'success'}" style="font-size:0.65rem;">
            수행 ${activeCount} / 전체 ${devicesInGroup.length}대
          </span>
        </div>
        <div class="accordion-meta">
          <span>장소: <strong>${firstPlace}</strong></span>
          <i data-lucide="${toggleIcon}" style="width:16px; height:16px;"></i>
        </div>
      </div>
      <div class="accordion-body ${isOpen ? 'open' : ''}" id="group-body-${groupName}">
        <div class="device-grid">
          <!-- Cards rendered here -->
        </div>
      </div>
    `;
    
    const gridDiv = groupDiv.querySelector(".device-grid");
    devicesInGroup.forEach(d => {
      const cardDiv = document.createElement("div");
      const isAlerting = d.status === 'ERROR' || 
                         (d.status === 'ON' && d.silence_level === 'danger') || 
                         ((d.today_fail || 0) >= 5 && (d.today_fail || 0) > (d.today_success || 0));
      
      let statusClass = 'status-off';
      let indClass = 'inactive';
      let borderColor = 'var(--border-color)';
      let statusLabelText = d.status || 'OFF';
      let statusBadgeClass = 'danger';
      
      if (d.status === 'ON') {
        statusBadgeClass = 'success';
        if (d.silence_level === 'danger') {
          statusClass = 'status-error';
          indClass = 'alert';
          borderColor = 'var(--color-danger)';
          statusLabelText = `무응답 (${d.silence_minutes}분)`;
          statusBadgeClass = 'danger';
        } else if (d.silence_level === 'warning') {
          statusClass = 'status-warning';
          indClass = 'alert'; 
          borderColor = 'var(--color-warning)';
          statusLabelText = `지연 (${d.silence_minutes}분)`;
          statusBadgeClass = 'warning';
        } else if ((d.today_fail || 0) >= 5 && (d.today_fail || 0) > (d.today_success || 0)) {
          statusClass = 'status-error';
          indClass = 'alert';
          borderColor = 'var(--color-danger)';
          statusLabelText = `실패과다 (${d.today_fail}회)`;
          statusBadgeClass = 'danger';
        } else {
          statusClass = 'status-on';
          indClass = 'active';
          borderColor = 'rgba(16, 185, 129, 0.35)';
        }
      } else if (isAlerting) {
        statusClass = 'status-error';
        indClass = 'alert';
        borderColor = 'var(--color-danger)';
      }

      const lastActiveFormatted = d.last_task_at ? d.last_task_at.substring(11, 16) : "--:--"; 
      const todaySuccess = d.today_success || 0;
      const yesterdaySuccess = d.yesterday_success || 0;
      const diff = todaySuccess - yesterdaySuccess;
      const diffSign = diff > 0 ? '+' : '';
      const diffColor = diff > 0 ? 'var(--color-success)' : (diff < 0 ? 'var(--color-danger)' : 'var(--text-muted)');
      const compareText = `<span style="font-size:0.65rem; color:${diffColor}; font-weight:800; margin-left:0.15rem;">(${diffSign}${diff})</span>`;

      if (d.has_identity_mismatch) {
        borderColor = 'var(--color-danger)';
        cardDiv.style.background = 'rgba(239, 68, 68, 0.08)';
      }

      cardDiv.className = `device-card ${statusClass}`;
      cardDiv.style.padding = "0.5rem 0.6rem";
      cardDiv.style.gap = "0.25rem";
      cardDiv.style.borderColor = borderColor;
      cardDiv.style.cursor = "pointer";
      cardDiv.setAttribute("onclick", `window.openDeviceDetailModal('${d.device_id}')`);
      
      cardDiv.innerHTML = `
        <div class="device-card-header" style="margin-bottom:0.15rem;">
          <div style="display: flex; align-items: center; gap: 0.25rem; min-width: 0; flex: 1;">
            <span class="device-name" style="font-size:0.775rem; font-weight:700; overflow:hidden; text-overflow:ellipsis; white-space:nowrap; max-width: 90px;" title="기기이름: ${d.hostname || '미정'}&#10;디바이스 ID: ${d.device_id}">${d.device_id}</span>
            <button class="badge secondary" style="cursor:pointer; padding: 0.05rem 0.2rem; font-size: 0.55rem; line-height: 1; flex-shrink: 0;" onclick="event.stopPropagation(); window.copyToClipboard('${d.device_id}', this)" title="ID 복사">복사</button>
            ${d.has_identity_mismatch ? `<span class="badge danger" style="font-size:0.55rem; padding: 0.05rem 0.15rem; font-weight:800; flex-shrink:0; cursor:pointer;" title="신원 정보 불일치 오류 감지 (SSAID/ADID/TOKEN 확인 요망)">⚠️ 신원오류</span>` : ''}
          </div>
          <span class="badge ${statusBadgeClass}" style="font-size:0.6rem; padding:0.05rem 0.15rem; flex-shrink: 0; margin-left: 0.25rem;">
            <span class="status-indicator ${indClass}"></span> ${statusLabelText}
          </span>
        </div>
        <div style="display:flex; justify-content:space-between; align-items:center;">
          <div style="display:flex; gap:0.2rem;">
            <span class="badge success" style="font-size:0.6rem; padding:0.05rem 0.15rem; font-weight:700;">
              S: ${todaySuccess} ${compareText}
            </span>
            <span class="badge ${d.today_fail > 0 ? 'danger' : 'secondary'}" style="font-size:0.6rem; padding:0.05rem 0.15rem; font-weight:700;">
              F: ${d.today_fail || 0}
            </span>
          </div>
          <span style="font-size:0.65rem; color:var(--text-muted); font-weight:500;">통신 ${lastActiveFormatted}</span>
        </div>
      `;
      gridDiv.appendChild(cardDiv);
    });

    container.appendChild(groupDiv);
  });
  
  if (window.lucide) {
    window.lucide.createIcons();
  }
}

function renderCompactView(filteredDevices) {
  const container = document.getElementById("devices-compact-container");
  if (!container) return;

  if (filteredDevices.length === 0) {
    container.innerHTML = `<div style="text-align: center; color: var(--text-muted); padding: 3rem; font-size:0.85rem;">조건에 맞는 디바이스가 존재하지 않습니다.</div>`;
    return;
  }

  // Header showing aggregate counts
  let html = `
    <div style="display:flex; justify-content:space-between; margin-bottom: 0.75rem; font-size: 0.75rem; color: var(--text-muted);">
      <span>* 각 배지를 클릭하면 통합 기기 정보 수정, 일자별 성공수, 최근 50건 이력 제어가 제공됩니다.</span>
      <span>필터링된 수량: <strong>${filteredDevices.length}대</strong></span>
    </div>
    <div style="display: grid; grid-template-columns: repeat(auto-fill, minmax(75px, 1fr)); gap: 0.35rem;">
  `;

  filteredDevices.forEach(d => {
    const isAlerting = d.status === 'ERROR' || (d.today_fail || 0) >= 5;
    
    // Status colors: Active Green, Inactive Gray, Warning Yellow, Alert Red
    let bgColor = 'rgba(255, 255, 255, 0.02)';
    let borderColor = 'var(--border-color)';
    let statusDotColor = 'var(--text-muted)';
    
    if (d.status === 'ON') {
      if (d.silence_level === 'danger') {
        bgColor = 'rgba(239, 68, 68, 0.08)';
        borderColor = 'rgba(239, 68, 68, 0.4)';
        statusDotColor = 'var(--color-danger)';
      } else if (d.silence_level === 'warning') {
        bgColor = 'rgba(245, 158, 11, 0.08)';
        borderColor = 'rgba(245, 158, 11, 0.4)';
        statusDotColor = 'var(--color-warning)';
      } else {
        bgColor = 'rgba(16, 185, 129, 0.05)';
        borderColor = 'rgba(16, 185, 129, 0.25)';
        statusDotColor = 'var(--color-success)';
      }
    } else if (isAlerting) {
      bgColor = 'rgba(239, 68, 68, 0.08)';
      borderColor = 'rgba(239, 68, 68, 0.4)';
      statusDotColor = 'var(--color-danger)';
    }

    const shortName = d.hostname ? d.hostname.replace('PC-', '') : d.device_id.substring(0, 5);
    const lastTime = d.last_task_at ? d.last_task_at.substring(11, 16) : '--:--';
    
    const diff = (d.today_success || 0) - (d.yesterday_success || 0);
    const diffText = diff > 0 ? `+${diff}` : `${diff}`;

    if (d.has_identity_mismatch) {
      bgColor = 'rgba(239, 68, 68, 0.12)';
      borderColor = 'var(--color-danger)';
    }

    const tooltip = `기기: ${d.hostname || '미정'} (${d.device_id})&#10;IP: ${d.current_ip || '--'}&#10;상태: ${d.status || 'OFF'}&#10;오늘성공: ${d.today_success || 0}건 (${diffText})&#10;오늘실패: ${d.today_fail || 0}건&#10;최근통신: ${lastTime}&#10;설치처: ${d.install_place || '미정'}` + 
      (d.has_identity_mismatch ? '\u000A⚠️ 신원오류 감지: SSAID/ADID/TOKEN 불일치' : '');

    html += `
      <div class="compact-badge" 
           onclick="window.openDeviceDetailModal('${d.device_id}')"
           title="${tooltip}"
           style="cursor:pointer; display:flex; flex-direction:column; align-items:center; justify-content:center; padding: 0.4rem 0.2rem; border-radius: 4px; border:1px solid ${borderColor}; background:${bgColor}; font-size:0.65rem; transition: all 0.2s;"
           onmouseover="this.style.borderColor='var(--color-primary)'; this.style.transform='translateY(-1px)';"
           onmouseout="this.style.borderColor='${borderColor}'; this.style.transform='none';">
        <span style="font-weight:700; width:100%; text-align:center; overflow:hidden; text-overflow:ellipsis; white-space:nowrap;">${shortName}${d.has_identity_mismatch ? ' ⚠️' : ''}</span>
        <div style="display:flex; align-items:center; gap:0.15rem; font-size:0.55rem; color:var(--text-muted); font-weight:600; margin-top:0.1rem;">
          <span style="width: 5px; height: 5px; border-radius: 50%; background-color: ${statusDotColor}; display:inline-block;"></span>
          <span>S:${d.today_success || 0}</span>
        </div>
      </div>
    `;
  });

  html += `</div>`;
  container.innerHTML = html;
}

function renderTableView(filteredDevices) {
  const tableContainer = document.getElementById("devices-table-container");
  const gridDiv = document.querySelector('#grid-devices-table');
  if (!tableContainer || !gridDiv) return;

  if (state.devicesGridApi) {
    state.devicesGridApi.setGridOption('rowData', filteredDevices);
    setTimeout(() => {
      state.devicesGridApi.sizeColumnsToFit();
    }, 50);
    return;
  }

  const gridOptions = {
    columnDefs: [
      { 
        field: 'hostname', 
        headerName: '기기이름', 
        sortable: true, 
        filter: true, 
        width: 150,
        cellRenderer: params => {
          const d = params.data;
          const warning = d.has_identity_mismatch ? `<span class="badge danger" style="font-size:0.55rem; padding:0.05rem 0.15rem; font-weight:800; margin-left:0.25rem;">⚠️ 신원오류</span>` : '';
          return `<span>${d.hostname || '미정'}</span>${warning}`;
        }
      },
      { 
        field: 'device_id', 
        headerName: '디바이스 ID', 
        sortable: true, 
        filter: true, 
        width: 140,
        cellRenderer: p => `
          <div style="display:flex; align-items:center; justify-content:space-between; width:100%;">
            <span>${p.value}</span>
            <button class="badge secondary" style="cursor:pointer; padding: 0.1rem 0.35rem; margin-left: 0.25rem; font-size: 0.65rem;" onclick="window.copyToClipboard('${p.value}', this)" title="ID 복사">
              복사
            </button>
          </div>
        `
      },
      { field: 'current_ip', headerName: 'IP 주소', sortable: true, filter: true, width: 120 },
      { field: 'status', headerName: '상태', width: 110, cellRenderer: params => {
          const d = params.data;
          const isAlerting = d.status === 'ERROR' || 
                             (d.status === 'ON' && d.silence_level === 'danger') || 
                             ((d.today_fail || 0) >= 5 && (d.today_fail || 0) > (d.today_success || 0));
          let badgeClass = 'secondary';
          let statusText = d.status || 'OFF';
          
          if (d.status === 'ON') {
            if (d.silence_level === 'danger') {
              badgeClass = 'danger';
              statusText = `무응답 (${d.silence_minutes}m)`;
            } else if (d.silence_level === 'warning') {
              badgeClass = 'warning';
              statusText = `지연 (${d.silence_minutes}m)`;
            } else if ((d.today_fail || 0) >= 5 && (d.today_fail || 0) > (d.today_success || 0)) {
              badgeClass = 'danger';
              statusText = `실패과다 (${d.today_fail}f)`;
            } else {
              badgeClass = 'success';
              statusText = 'ON';
            }
          } else if (isAlerting) {
            badgeClass = 'danger';
            statusText = 'ERROR';
          }
          return `<span class="badge ${badgeClass}" style="font-size:0.65rem; padding:0.1rem 0.3rem;">${statusText}</span>`;
        }
      },
      { field: 'today_success', headerName: '오늘 성공', sortable: true, width: 95, cellRenderer: params => {
          const today = params.data.today_success || 0;
          const yesterday = params.data.yesterday_success || 0;
          const diff = today - yesterday;
          let diffHtml = '';
          if (diff > 0) diffHtml = `<span style="color:var(--color-success); font-size:0.65rem; font-weight:700; margin-left:0.25rem;">+${diff}▲</span>`;
          else if (diff < 0) diffHtml = `<span style="color:var(--color-danger); font-size:0.65rem; font-weight:700; margin-left:0.25rem;">${diff}▼</span>`;
          return `<span>${today}</span>${diffHtml}`;
        }
      },
      { field: 'today_fail', headerName: '오늘 실패', sortable: true, width: 85, cellRenderer: params => {
          const fail = params.data.today_fail || 0;
          const color = fail > 0 ? 'var(--color-danger)' : 'inherit';
          return `<span style="color:${color}; font-weight:${fail > 0 ? '700' : 'normal'}">${fail}</span>`;
        }
      },
      { headerName: '최근 7일 추이', width: 125, cellRenderer: params => {
          const history = params.data.history_success || [0,0,0,0,0,0,0];
          const maxVal = Math.max(...history);
          return `
            <div style="display:flex; align-items:flex-end; gap:2px; height:18px; width:55px; padding-top:4px;" title="최근 7일 성공 건수: ${history.join(', ')}">
              ${history.map(h => {
                const pct = maxVal > 0 ? (h / maxVal) * 100 : 0;
                return `<div style="flex:1; height:${pct}%; background:var(--color-primary); border-radius:1px; min-height:1px;"></div>`;
              }).join('')}
            </div>
          `;
        }
      },
      { field: 'last_task_at', headerName: '최근 통신', sortable: true, width: 100, valueFormatter: params => {
          return params.value ? params.value.substring(11, 16) : '--:--';
        }
      },
      { field: 'install_place', headerName: '설치장소', sortable: true, filter: true, width: 150 },
      { headerName: '작업 제어', width: 145, pinned: 'right', cellRenderer: params => {
          const d = params.data;
          const muteTitle = d.is_alert_muted ? "알람 켜기" : "알람 끄기";
          const muteBtnClass = d.is_alert_muted ? "btn primary sm" : "btn secondary sm";
          const alertActionText = d.is_alert_muted ? "벨ON" : "벨OFF";
          
          return `
            <div style="display:flex; gap:0.25rem; align-items:center; height:100%; padding-top:2px;">
              <button class="${muteBtnClass}" style="padding:0.1rem 0.3rem; height:24px; font-size:0.6rem;" onclick="window.toggleMute('${d.device_id}', ${!d.is_alert_muted})" title="${muteTitle}">
                ${alertActionText}
              </button>
              <button class="btn secondary sm" style="padding:0.1rem 0.4rem; height:24px; font-size:0.6rem;" onclick="window.openDeviceDetailModal('${d.device_id}')">
                상세
              </button>
            </div>
          `;
        }
      }
    ],
    rowData: filteredDevices,
    rowHeight: 34,
    headerHeight: 34,
    enableCellTextSelection: true,
    ensureDomOrder: true
  };

  state.devicesGridApi = agGrid.createGrid(gridDiv, gridOptions);
  setTimeout(() => {
    state.devicesGridApi.sizeColumnsToFit();
  }, 50);
}

window.addEventListener('resize', () => {
  if (state.devicesGridApi) {
    state.devicesGridApi.sizeColumnsToFit();
  }
});

export function toggleAccordion(groupName) {
  const body = document.getElementById(`group-body-${groupName}`);
  if (!body) return;
  
  if (body.classList.contains("open")) {
    body.classList.remove("open");
    state.openedGroups[groupName] = false;
  } else {
    body.classList.add("open");
    state.openedGroups[groupName] = true;
  }
  
  filterDevicesLocally();
}

// Bind to window for HTML element event handling
window.toggleTotalDeviceList = toggleTotalDeviceList;
window.toggleAccordion = toggleAccordion;
window.onDeviceSearch = filterDevicesLocally;
window.switchDeviceViewMode = switchDeviceViewMode;
