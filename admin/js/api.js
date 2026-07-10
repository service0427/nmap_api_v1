import { state } from './state.js?v=1.1.22';
import { updateCriticalAlertMonitor, filterDevicesLocally } from './devices.js?v=1.1.22';
import { filterLteCards } from './lte.js?v=1.1.22';
import { filterDestinationsLocally, renderDestDateButtons } from './destinations.js?v=1.1.22';

// Fetch API Data
export async function fetchData(manual = false) {
  state.isFetching = true;
  
  // Rotate refresh icon if manual refresh
  const refreshIcon = document.getElementById("refresh-icon");
  if (manual && refreshIcon) {
    refreshIcon.classList.add("spinning");
  }
  
  try {
    const url = state.selectedDestinationDate ? `/api/v1/admin/summary?date=${state.selectedDestinationDate}` : "/api/v1/admin/summary";
    const res = await fetch(url);
    if (!res.ok) throw new Error(`HTTP Error: ${res.status}`);
    const data = await res.json();
    
    state.lastApiData = data; // Cache data
    updateUI(data);
  } catch (err) {
    console.error("Fetch Data Error:", err);
  } finally {
    state.isFetching = false;
    if (refreshIcon) {
      refreshIcon.classList.remove("spinning");
    }
  }
}
window.fetchData = fetchData;


// Update UI elements based on API payload
export function updateUI(data) {
  // 1. Statistics Progress Cards
  const activeDate = state.activeDate || 'today';
  const stats = data.summary[activeDate] || data.summary;
  
  // Highlight active date tab in UI
  document.querySelectorAll(".date-tab-btn").forEach(btn => {
    btn.classList.toggle("active", btn.id === `btn-date-${activeDate}`);
  });
  
  // Update date labels
  const dateLabel = document.getElementById("summary-date-label");
  if (dateLabel) {
    if (activeDate === 'yesterday') dateLabel.innerText = " (어제)";
    else if (activeDate === 'today') dateLabel.innerText = " (오늘 현재)";
    else if (activeDate === 'tomorrow') dateLabel.innerText = " (내일)";
  }
  
  // Today's unified summary card highlight
  const totalCard = document.getElementById("total-summary-card");
  if (totalCard) {
    if (activeDate === 'today') {
      totalCard.classList.add("active-today-highlight");
    } else {
      totalCard.classList.remove("active-today-highlight");
    }
  }

  state.totalTodaySuccess = data.summary.total_today_success || 0;
  state.totalYesterdaySuccess = data.summary.total_yesterday_success || 0;
  state.pastDateStrs = data.summary.past_date_strs || [];
  
  const isMobile = window.innerWidth < 768;
  const formatCounts = (success, target, fail) => {
    const s = (success || 0).toLocaleString();
    const t = (target || 0).toLocaleString();
    const f = (fail || 0).toLocaleString();
    if (isMobile) {
      return `${s}/${t}`;
    }
    return `성공: ${s} / 목표: ${t} (실패: ${f})`;
  };

  // FSD
  const fsdPct = stats.fsd_target > 0 ? Math.round((stats.fsd_success / stats.fsd_target) * 100) : 0;
  const fsdPctEl = document.getElementById("fsd-percent");
  const fsdProgressFill = document.getElementById("fsd-progress-fill");
  const fsdCounts = document.getElementById("fsd-counts");
  if (fsdPctEl) fsdPctEl.innerText = `${fsdPct}%`;
  if (fsdProgressFill) fsdProgressFill.style.width = `${Math.min(100, fsdPct)}%`;
  if (fsdCounts) fsdCounts.innerText = formatCounts(stats.fsd_success, stats.fsd_target, stats.fsd_fail);

  // LUF
  const lufPct = stats.luf_target > 0 ? Math.round((stats.luf_success / stats.luf_target) * 100) : 0;
  const lufPctEl = document.getElementById("luf-percent");
  const lufProgressFill = document.getElementById("luf-progress-fill");
  const lufCounts = document.getElementById("luf-counts");
  if (lufPctEl) lufPctEl.innerText = `${lufPct}%`;
  if (lufProgressFill) lufProgressFill.style.width = `${Math.min(100, lufPct)}%`;
  if (lufCounts) lufCounts.innerText = formatCounts(stats.luf_success, stats.luf_target, stats.luf_fail);

  // TEST
  const testPct = stats.test_target > 0 ? Math.round((stats.test_success / stats.test_target) * 100) : 0;
  const testPctEl = document.getElementById("test-percent");
  const testProgressFill = document.getElementById("test-progress-fill");
  const testCounts = document.getElementById("test-counts");
  if (testPctEl) testPctEl.innerText = `${testPct}%`;
  if (testProgressFill) testProgressFill.style.width = `${Math.min(100, testPct)}%`;
  if (testCounts) testCounts.innerText = formatCounts(stats.test_success, stats.test_target, stats.test_fail);

  // ssolup
  const ssolupPct = stats.ssolup_target > 0 ? Math.round((stats.ssolup_success / stats.ssolup_target) * 100) : 0;
  const ssolupPctEl = document.getElementById("ssolup-percent");
  const ssolupProgressFill = document.getElementById("ssolup-progress-fill");
  const ssolupCounts = document.getElementById("ssolup-counts");
  if (ssolupPctEl) ssolupPctEl.innerText = `${ssolupPct}%`;
  if (ssolupProgressFill) ssolupProgressFill.style.width = `${Math.min(100, ssolupPct)}%`;
  if (ssolupCounts) ssolupCounts.innerText = formatCounts(stats.ssolup_success, stats.ssolup_target, stats.ssolup_fail);

  // quixslot
  const quixslotPct = stats.quixslot_target > 0 ? Math.round((stats.quixslot_success / stats.quixslot_target) * 100) : 0;
  const quixslotPctEl = document.getElementById("quixslot-percent");
  const quixslotProgressFill = document.getElementById("quixslot-progress-fill");
  const quixslotCounts = document.getElementById("quixslot-counts");
  if (quixslotPctEl) quixslotPctEl.innerText = `${quixslotPct}%`;
  if (quixslotProgressFill) quixslotProgressFill.style.width = `${Math.min(100, quixslotPct)}%`;
  if (quixslotCounts) quixslotCounts.innerText = formatCounts(stats.quixslot_success, stats.quixslot_target, stats.quixslot_fail);

  // ghost
  const ghostPct = stats.ghost_target > 0 ? Math.round((stats.ghost_success / stats.ghost_target) * 100) : 0;
  const ghostPctEl = document.getElementById("ghost-percent");
  const ghostProgressFill = document.getElementById("ghost-progress-fill");
  const ghostCounts = document.getElementById("ghost-counts");
  if (ghostPctEl) ghostPctEl.innerText = `${ghostPct}%`;
  if (ghostProgressFill) ghostProgressFill.style.width = `${Math.min(100, ghostPct)}%`;
  if (ghostCounts) ghostCounts.innerText = formatCounts(stats.ghost_success, stats.ghost_target, stats.ghost_fail);

  // rudolph
  const rudolphPct = stats.rudolph_target > 0 ? Math.round((stats.rudolph_success / stats.rudolph_target) * 100) : 0;
  const rudolphPctEl = document.getElementById("rudolph-percent");
  const rudolphProgressFill = document.getElementById("rudolph-progress-fill");
  const rudolphCounts = document.getElementById("rudolph-counts");
  if (rudolphPctEl) rudolphPctEl.innerText = `${rudolphPct}%`;
  if (rudolphProgressFill) rudolphProgressFill.style.width = `${Math.min(100, rudolphPct)}%`;
  if (rudolphCounts) rudolphCounts.innerText = formatCounts(stats.rudolph_success, stats.rudolph_target, stats.rudolph_fail);

  // wjd
  const wjdPct = stats.wjd_target > 0 ? Math.round((stats.wjd_success / stats.wjd_target) * 100) : 0;
  const wjdPctEl = document.getElementById("wjd-percent");
  const wjdProgressFill = document.getElementById("wjd-progress-fill");
  const wjdCounts = document.getElementById("wjd-counts");
  if (wjdPctEl) wjdPctEl.innerText = `${wjdPct}%`;
  if (wjdProgressFill) wjdProgressFill.style.width = `${Math.min(100, wjdPct)}%`;
  if (wjdCounts) wjdCounts.innerText = formatCounts(stats.wjd_success, stats.wjd_target, stats.wjd_fail);

  // Total Unified
  const totalPct = stats.total_target > 0 ? Math.round((stats.success / stats.total_target) * 100) : 0;
  const totalPctEl = document.getElementById("total-percent");
  const totalProgressFill = document.getElementById("total-progress-fill");
  if (totalPctEl) totalPctEl.innerText = `${totalPct}%`;
  if (totalProgressFill) totalProgressFill.style.width = `${Math.min(100, totalPct)}%`;

  // Bind new grid metric items
  const statSuccess = document.getElementById("stat-success");
  const statTarget = document.getElementById("stat-target");
  const statRemain = document.getElementById("stat-remain");
  const statFaulty = document.getElementById("stat-faulty");

  const formatNum = (num) => (num || 0).toLocaleString();

  if (statSuccess) statSuccess.innerText = formatNum(stats.success);
  if (statTarget) statTarget.innerText = formatNum(stats.total_target);
  if (statRemain) statRemain.innerText = formatNum(stats.remain);

  // Compute faulty device count from data.devices
  const devices = data.devices || [];
  let faultyCount = 0;
  devices.forEach(d => {
    const isAlerting = d.status === 'ERROR' || 
                       (d.status === 'ON' && d.silence_minutes >= 20) || 
                       ((d.today_fail || 0) >= 5 && (d.today_fail || 0) > (d.today_success || 0));
    if (isAlerting) {
      faultyCount++;
    }
  });
  if (statFaulty) statFaulty.innerText = `${faultyCount}대`;

  // 2. System Health Info
  const sys = data.system;
  const sysCpu = document.getElementById("sys-cpu");
  const sysRam = document.getElementById("sys-ram");
  const sysDisk = document.getElementById("sys-disk");
  if (sysCpu) sysCpu.innerText = sys.cpu;
  if (sysRam) sysRam.innerText = `${sys.ram_mb} MB`;
  if (sysDisk) sysDisk.innerText = `${sys.disk_free_gb} GB`;

  // 3. LTE Quick info on dashboard
  const lteQuick = document.getElementById("lte-quick-list");
  if (lteQuick) {
    lteQuick.innerHTML = "";
    if (data.lte && data.lte.length > 0) {
      data.lte.slice(0, 4).forEach(l => {
        const upUsedBytes = (l.today_now_up || 0) - (l.today_init_up || 0);
        const dnUsedBytes = (l.today_now_dn || 0) - (l.today_init_dn || 0);
        const totalMB = Math.max(0, (upUsedBytes + dnUsedBytes) / (1024 * 1024)).toFixed(1);
        
        const div = document.createElement("div");
        div.innerHTML = `
          <div style="display: flex; justify-content: space-between; font-size: 0.8rem; margin-bottom: 0.2rem;">
            <span style="font-weight: 600;">${l.modem_name}</span>
            <span style="color: var(--color-primary); font-weight: bold;">${totalMB} MB</span>
          </div>
          <div class="progress-bar" style="height: 5px;">
            <div class="progress-fill primary" style="width: ${Math.min(100, (totalMB / 10))}%;"></div>
          </div>
        `;
        lteQuick.appendChild(div);
      });
    } else {
      lteQuick.innerHTML = `<div style="text-align: center; color: var(--text-muted); font-size: 0.8rem;">오늘 데이터 사용량 집계가 없습니다.</div>`;
    }
  }

  // 4. Timeline successes feed
  const feed = document.getElementById("success-feed-container");
  if (feed) {
    feed.innerHTML = `
      <div class="panel-header" style="border-bottom: 1px solid var(--border-color); padding: 0.75rem 0.25rem;">
        <h3 class="panel-title"><i data-lucide="check-circle-2" style="width:16px; height:16px; color: var(--color-primary);"></i>실시간 작업 성공 피드</h3>
      </div>
    `;
    const feedItemsDiv = document.createElement("div");
    feedItemsDiv.className = "timeline";
    if (data.success_feed && data.success_feed.length > 0) {
      data.success_feed.forEach(f => {
        const item = document.createElement("div");
        item.className = "timeline-item";
        
        const formatTime = (tStr) => {
          if (!tStr || typeof tStr !== "string") return "--:--:--";
          if (tStr.length >= 19) return tStr.substring(11, 19);
          const tIdx = tStr.indexOf("T");
          if (tIdx !== -1 && tStr.length >= tIdx + 9) return tStr.substring(tIdx + 1, tIdx + 9);
          return tStr;
        };
        
        const startFormatted = formatTime(f.start_time);
        const endFormatted = formatTime(f.end_time);
        
        let durationFormatted = "";
        if (f.duration_sec) {
          const mins = Math.floor(f.duration_sec / 60);
          const secs = f.duration_sec % 60;
          durationFormatted = mins > 0 ? `${mins}분 ${secs}초` : `${secs}초`;
        } else {
          durationFormatted = "미측정";
        }
        
        item.innerHTML = `
          <div class="timeline-icon">
            <svg xmlns="http://www.w3.org/2000/svg" width="8" height="8" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"><polyline points="20 6 9 17 4 12"></polyline></svg>
          </div>
          <div class="timeline-content">
            <span class="timeline-title" style="font-weight:600; font-size:0.8rem; display:block;">${f.dest_name}</span>
            <div style="font-size:0.7rem; color:var(--text-muted); margin-top:2px;">
              <span>${f.device_memo}</span>
            </div>
            <div style="font-size:0.65rem; color:var(--text-muted); margin-top:1px; display:flex; gap:6px; flex-wrap:wrap;">
              <span>시작: <span style="color:#6366f1;">${startFormatted}</span></span>
              <span>종료: <span style="color:#10b981;">${endFormatted}</span></span>
              <span>소요: <strong style="color:var(--color-primary);">${durationFormatted}</strong></span>
            </div>
          </div>
        `;
        feedItemsDiv.appendChild(item);
      });
    } else {
      feedItemsDiv.innerHTML = `<div style="text-align: center; color: var(--text-muted); padding: 2rem; font-size: 0.8rem;">최근 성공 이력이 없습니다.</div>`;
    }
    feed.appendChild(feedItemsDiv);
  }

  // 5. Store devices globally to support group accordion filtering
  state.rawDevices = data.devices || [];
  const countBadge = document.getElementById("total-devices-count-badge");
  if (countBadge) countBadge.innerText = `${state.rawDevices.length}대 등록됨`;
  
  // Calculate 20m Critical Alerts & Populate banner
  updateCriticalAlertMonitor(data.alarms);
  
  // Render Device group list
  filterDevicesLocally();

  // 6. Bind data to LTE Cards
  state.rawLteData = data.lte || [];
  filterLteCards();
  
  // Store destinations globally for manual input filtering
  state.rawDestinations = data.destinations || [];
  const serverTodayStr = data.system && data.system.kst_time ? data.system.kst_time.substring(0, 10) : new Date().toISOString().substring(0, 10);
  renderDestDateButtons(serverTodayStr);
  filterDestinationsLocally();
  
  if (window.lucide) {
    window.lucide.createIcons();
  }
}

// Action: Toggle Device Mute
export async function toggleMute(deviceId, isMuted) {
  try {
    const res = await fetch("/api/v1/admin/device/toggle_mute", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ device_id: deviceId, is_muted: isMuted })
    });
    if (!res.ok) throw new Error("Toggle Mute fail");
    fetchData();
  } catch (err) {
    alert("알람 상태 변경 실패: " + err.message);
  }
}

// Action: Update Dest Limit
export async function updateDestLimit(destId, newLimit) {
  try {
    const res = await fetch("/api/v1/admin/dest/update", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ dest_id: destId, limit: parseInt(newLimit, 10) })
    });
    if (!res.ok) throw new Error("Update limit failed");
    
    // Update local memory data instantly to avoid grid redraw lag
    if (state.rawDestinations) {
      const targetObj = state.rawDestinations.find(x => x.dest_id === destId);
      if (targetObj) targetObj.target = parseInt(newLimit, 10);
    }
  } catch (err) {
    alert("한도값 변경 실패: " + err.message);
    fetchData();
  }
}

// Action: Update Dest Status
export async function updateDestStatus(destId, newStatus) {
  try {
    const res = await fetch("/api/v1/admin/dest/update", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ dest_id: destId, status: newStatus })
    });
    if (!res.ok) throw new Error("Update status failed");
    fetchData();
  } catch (err) {
    alert("목적지 활성 상태 변경 실패: " + err.message);
  }
}

// Action: Update Dest Optimizer Status
export async function updateDestOptimizer(destId, isOptimizerVal) {
  try {
    const res = await fetch("/api/v1/admin/dest/update", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ dest_id: destId, is_optimizer: isOptimizerVal })
    });
    if (!res.ok) throw new Error("Update optimizer failed");
    fetchData();
  } catch (err) {
    alert("옵티마이저 활성 상태 변경 실패: " + err.message);
  }
}

// Action: Switch date view (yesterday, today, tomorrow)
export function switchDate(dateKey) {
  state.activeDate = dateKey;
  if (state.lastApiData) {
    updateUI(state.lastApiData);
  }
}

// Action: Reset Device Penalty
export async function resetPenalty(deviceId) {
  // 1. Optimistically update local memory state instantly! (0.01s response)
  if (state.rawDevices) {
    const d = state.rawDevices.find(x => x.device_id === deviceId);
    if (d) {
      d.penalty_until = null;
      d.today_fail = 0;
    }
  }
  if (state.lastApiData && state.lastApiData.devices) {
    const d = state.lastApiData.devices.find(x => x.device_id === deviceId);
    if (d) {
      d.penalty_until = null;
      d.today_fail = 0;
    }
  }
  // 2. Redraw active UI immediately
  filterDevicesLocally();

  try {
    const res = await fetch("/api/v1/admin/device/reset_penalty", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ device_id: deviceId })
    });
    if (!res.ok) throw new Error("Reset Penalty fail");
    fetchData(); // Background fetch to sync fully
  } catch (err) {
    alert("페널티 초기화 실패: " + err.message);
  }
}

// Bind to window for HTML click handlers
window.fetchData = fetchData;
window.toggleMute = toggleMute;
window.updateDestLimit = updateDestLimit;
window.updateDestStatus = updateDestStatus;
window.updateDestOptimizer = updateDestOptimizer;
window.switchDate = switchDate;
window.resetPenalty = resetPenalty;
