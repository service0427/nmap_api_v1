import { state } from './state.js?v=1.1.22';

export async function openDeviceDetailModal(deviceId) {
  const modal = document.getElementById("device-detail-modal");
  if (!modal || !state.rawDevices) return;

  const d = state.rawDevices.find(x => x.device_id === deviceId);
  if (!d) return;

  // Set inputs
  document.getElementById("detail-device-id").value = d.device_id;
  const devCodeEl = document.getElementById("detail-device-code");
  if (devCodeEl) devCodeEl.innerText = d.device_id; // Set Device ID
  const devIdTextEl = document.getElementById("detail-device-id-text");
  if (devIdTextEl) devIdTextEl.innerText = d.device_id;
  document.getElementById("detail-ip-display").innerText = `IP: ${d.current_ip || '--'}`;

  const hostnameEl = document.getElementById("detail-hostname") || document.getElementById("detail-memo");
  if (hostnameEl) {
    hostnameEl.value = d.hostname || "";
    const parent = hostnameEl.closest('.form-group') || hostnameEl.parentElement;
    if (parent) parent.style.display = 'flex';
  }

  const placeEl = document.getElementById("detail-place");
  if (placeEl) {
    placeEl.value = d.install_place || "";
    const parent = placeEl.closest('.form-group') || placeEl.parentElement;
    if (parent) parent.style.display = 'flex';
  }

  // Show/Hide Identity Mismatch Warning
  const mismatchBanner = document.getElementById("detail-mismatch-banner");
  if (mismatchBanner) {
    mismatchBanner.style.display = d.has_identity_mismatch ? "block" : "none";
  }

  // Show/Hide Penalty Warning Banner
  const penaltyBanner = document.getElementById("detail-penalty-banner");
  const penaltyTimeEl = document.getElementById("detail-penalty-time");
  if (penaltyBanner) {
    const kstNow = new Date(new Date().toLocaleString("en-US", { timeZone: "Asia/Seoul" }));
    const isPenalized = d.penalty_until && new Date(d.penalty_until.replace(' ', 'T')) > kstNow;
    if (isPenalized) {
      penaltyBanner.style.display = "block";
      if (penaltyTimeEl) penaltyTimeEl.innerText = `만료 예정: ${d.penalty_until}`;
    } else {
      penaltyBanner.style.display = "none";
    }
  }

  // Make sure Single elements are visible
  const devCodeCont = document.getElementById("detail-code-container");
  if (devCodeCont) devCodeCont.style.display = 'flex';
  document.getElementById("detail-trend-container").style.display = 'flex';
  
  const muteBtn = document.getElementById("detail-mute-btn");
  if (muteBtn) {
    muteBtn.closest('div').style.display = 'flex';
    if (d.is_alert_muted) {
      muteBtn.className = "btn sm primary";
      muteBtn.innerHTML = `<svg xmlns="http://www.w3.org/2000/svg" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="width:12px; height:12px;"><path d="M13.7 4.7a2 2 0 0 0-3.4 0"/><path d="M18.6 13a10.5 10.5 0 0 0-1.6-4.5"/><path d="M21.1 22.5a6.5 6.5 0 0 0-4-2.5"/><path d="M8 8A6 6 0 0 0 8 8c0 7-3 9-3 9h18"/><path d="M10.3 21a1.94 1.94 0 0 0 3.4 0"/><line x1="1" x2="23" y1="1" y2="23"/></svg> <span id="detail-mute-text">알람 꺼짐</span>`;
    } else {
      muteBtn.className = "btn sm secondary";
      muteBtn.innerHTML = `<svg xmlns="http://www.w3.org/2000/svg" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="width:12px; height:12px;"><path d="M6 8a6 6 0 0 1 12 0c0 7 3 9 3 9H3s3-2 3-9"/><path d="M10.3 21a1.94 1.94 0 0 0 3.4 0"/></svg> <span id="detail-mute-text">알람 켜짐</span>`;
    }
  }

  // Populate daily success list
  const dailyContainer = document.getElementById("detail-daily-success-list");
  if (dailyContainer) {
    let dailyHtml = "";
    const history = d.history_success || [0,0,0,0,0,0,0];
    const pastDates = state.pastDateStrs || [];
    
    history.forEach((cnt, idx) => {
      const fullDate = pastDates[idx] || "";
      const shortDate = fullDate ? fullDate.substring(5) : `--/--`; // "06-19"
      dailyHtml += `
        <div style="background: rgba(255,255,255,0.03); border: 1px solid var(--border-color); border-radius: 4px; padding: 0.3rem 0.15rem; display:flex; flex-direction:column; gap:0.15rem; align-items:center;">
          <span style="font-size:0.525rem; color:var(--text-muted); font-weight:600; white-space:nowrap;">${shortDate}</span>
          <span style="font-size:0.7rem; color:var(--color-primary); font-weight:800;">${cnt}</span>
        </div>
      `;
    });
    dailyContainer.innerHTML = dailyHtml;
  }

  // Set Today History Title with date
  const pastDatesForTitle = state.pastDateStrs || [];
  const todayStrVal = pastDatesForTitle[pastDatesForTitle.length - 1] || new Date().toISOString().split('T')[0];
  const historyTitleEl = document.getElementById("detail-history-title");
  if (historyTitleEl) {
    historyTitleEl.innerText = `오늘 (${todayStrVal}) 작업 이력`;
  }

  // Set Title
  document.getElementById("detail-modal-title").innerHTML = `
    <svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="width:18px; height:18px; color:var(--color-primary);"><rect width="14" height="20" x="5" y="2" rx="2" ry="2"/><path d="M12 18h.01"/></svg>
    <span>[${d.hostname || d.device_id}] 상세 제어 및 이력</span>
  `;

  // Set history table to loading
  const historyBody = document.getElementById("detail-history-body");
  if (historyBody) {
    historyBody.innerHTML = `<tr><td colspan="4" style="text-align:center; color:var(--text-muted); padding:1.5rem;">로딩 중...</td></tr>`;
  }

  modal.style.display = "flex";

  // Fetch log history from API
  try {
    const res = await fetch(`/api/v1/admin/history/device/${deviceId}`);
    if (!res.ok) throw new Error("Fetch device history failed");
    const data = await res.json();
    
    if (historyBody) {
      historyBody.innerHTML = "";
      const historyTitleEl = document.getElementById("detail-history-title");
      if (historyTitleEl) {
        const pastDatesForTitle = state.pastDateStrs || [];
        const todayStrVal = pastDatesForTitle[pastDatesForTitle.length - 1] || new Date().toISOString().split('T')[0];
        historyTitleEl.innerText = `오늘 (${todayStrVal}) 작업 이력 (총 ${data.length}건)`;
      }
      if (data && data.length > 0) {
        data.forEach(h => {
          const tr = document.createElement("tr");
          tr.style.borderBottom = "1px solid var(--border-color)";
          const durationFormatted = h.duration !== null ? `${h.duration}분` : "--";
          tr.innerHTML = `
            <td style="padding: 0.45rem 0.5rem; max-width: 155px; overflow:hidden; text-overflow:ellipsis; white-space:nowrap;">
              <strong>${h.dest_name || '--'}</strong><br/>
              <span style="font-size:0.625rem; color:var(--text-muted); font-family:monospace;">${h.dest_id || '--'}</span>
            </td>
            <td style="padding: 0.45rem 0.5rem;">
              <span class="badge ${h.status === 'SUCCESS' ? 'success' : 'danger'}" style="font-size:0.6rem; padding:0 0.25rem;">${h.status}</span>
              <div style="font-size:0.55rem; color:var(--text-muted); font-family:monospace; margin-top:0.15rem; white-space:nowrap;">ID: ${h.task_id || '--'}</div>
            </td>
            <td style="padding: 0.45rem 0.5rem;"><code>${h.time}</code></td>
            <td style="padding: 0.45rem 0.5rem; text-align:right;">${durationFormatted}</td>
          `;
          historyBody.appendChild(tr);
        });
      } else {
        historyBody.innerHTML = `<tr><td colspan="4" style="text-align:center; color:var(--text-muted); padding:1.5rem;">금일 작업 수행 이력이 없습니다.</td></tr>`;
      }
    }
  } catch (err) {
    if (historyBody) {
      historyBody.innerHTML = `<tr><td colspan="4" style="text-align:center; color:var(--color-danger); padding:1.5rem;">이력 로딩 실패</td></tr>`;
    }
  }

}

export function openEditDeviceGroupModal(groupName, deviceIds) {
  const modal = document.getElementById("device-detail-modal");
  if (!modal || !state.rawDevices || !deviceIds || deviceIds.length === 0) return;
  
  const firstId = deviceIds[0];
  const d = state.rawDevices.find(x => x.device_id === firstId) || {};
  
  document.getElementById("detail-device-id").value = `GROUP:${JSON.stringify(deviceIds)}`;
  document.getElementById("detail-place").value = d.install_place || "";
  document.getElementById("detail-count").value = d.install_count || 1;
  document.getElementById("detail-network").value = d.network_type || "wired";
  document.getElementById("detail-ip-display").innerText = `대상 수량: ${deviceIds.length}대`;
  
  // Hide Single elements in group mode
  const memoEl = document.getElementById("detail-memo") || document.getElementById("detail-hostname");
  if (memoEl) memoEl.closest('.form-group').style.display = 'none';
  const devCodeCont = document.getElementById("detail-code-container");
  if (devCodeCont) devCodeCont.style.display = 'none';
  document.getElementById("detail-trend-container").style.display = 'none';
  document.getElementById("detail-mute-btn").closest('div').style.display = 'none';
  
  document.getElementById("detail-modal-title").innerHTML = `
    <svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="width:18px; height:18px; color:var(--color-accent);"><line x1="4" x2="4" y1="21" y2="14"/><line x1="4" x2="4" y1="10" y2="3"/><line x1="12" x2="12" y1="21" y2="12"/><line x1="12" x2="12" y1="8" y2="3"/><line x1="20" x2="20" y1="21" y2="16"/><line x1="20" x2="20" y1="12" y2="3"/><line x1="2" x2="6" y1="14" y2="14"/><line x1="10" x2="14" y1="8" y2="8"/><line x1="18" x2="22" y1="16" y2="16"/></svg>
    <span>[${groupName}] PC 그룹 일괄 설정 (${deviceIds.length}대)</span>
  `;
  
  const historyBody = document.getElementById("detail-history-body");
  if (historyBody) {
    historyBody.innerHTML = `<tr><td colspan="4" style="text-align:center; color:var(--text-muted); padding:1.5rem;">그룹 설정 모드에서는 최근 이력이 출력되지 않습니다.</td></tr>`;
  }
  
  modal.style.display = "flex";
}

export async function saveDetailDeviceInfo() {
  const deviceIdVal = document.getElementById("detail-device-id").value;
  const place = document.getElementById("detail-place").value;
  const count = parseInt(document.getElementById("detail-count").value, 10) || 1;
  const network = document.getElementById("detail-network").value;

  try {
    if (deviceIdVal.startsWith("GROUP:")) {
      const deviceIds = JSON.parse(deviceIdVal.replace("GROUP:", ""));
      const res = await fetch("/api/v1/admin/device/group_update", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          device_ids: deviceIds,
          install_place: place,
          install_count: count,
          network_type: network
        })
      });
      if (!res.ok) throw new Error("PC Group batch update failed");
    } else {
      const hostnameEl = document.getElementById("detail-hostname") || document.getElementById("detail-memo");
      const hostname = hostnameEl ? hostnameEl.value : "";
      const res = await fetch("/api/v1/admin/device/info_update", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          device_id: deviceIdVal,
          hostname: hostname,
          install_place: place,
          install_count: count,
          network_type: network
        })
      });
      if (!res.ok) throw new Error("Single device update failed");
    }
    
    document.getElementById("device-detail-modal").style.display = "none";
    window.fetchData();
  } catch (err) {
    alert("설정 저장 실패: " + err.message);
  }
}

export async function toggleDetailMute() {
  const deviceIdVal = document.getElementById("detail-device-id").value;
  if (!deviceIdVal || deviceIdVal.startsWith("GROUP:")) return;

  const d = state.rawDevices.find(x => x.device_id === deviceIdVal);
  if (!d) return;

  const newMuted = !d.is_alert_muted;
  try {
    const res = await fetch("/api/v1/admin/device/toggle_mute", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ device_id: deviceIdVal, is_muted: newMuted })
    });
    if (!res.ok) throw new Error("Toggle Mute failed");
    
    d.is_alert_muted = newMuted;
    
    const muteBtn = document.getElementById("detail-mute-btn");
    if (muteBtn) {
      if (newMuted) {
        muteBtn.className = "btn sm primary";
        muteBtn.innerHTML = `<svg xmlns="http://www.w3.org/2000/svg" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="width:12px; height:12px;"><path d="M13.7 4.7a2 2 0 0 0-3.4 0"/><path d="M18.6 13a10.5 10.5 0 0 0-1.6-4.5"/><path d="M21.1 22.5a6.5 6.5 0 0 0-4-2.5"/><path d="M8 8A6 6 0 0 0 8 8c0 7-3 9-3 9h18"/><path d="M10.3 21a1.94 1.94 0 0 0 3.4 0"/><line x1="1" x2="23" y1="1" y2="23"/></svg> <span id="detail-mute-text">알람 꺼짐</span>`;
      } else {
        muteBtn.className = "btn sm secondary";
        muteBtn.innerHTML = `<svg xmlns="http://www.w3.org/2000/svg" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="width:12px; height:12px;"><path d="M6 8a6 6 0 0 1 12 0c0 7 3 9 3 9H3s3-2 3-9"/><path d="M10.3 21a1.94 1.94 0 0 0 3.4 0"/></svg> <span id="detail-mute-text">알람 켜짐</span>`;
      }
    }
    window.fetchData();
  } catch (err) {
    alert("알람 상태 변경 실패: " + err.message);
  }
}

export function copyDeviceCode() {
  const code = document.getElementById("detail-device-id").value;
  if (!code) return;
  navigator.clipboard.writeText(code).then(() => {
    const alertDiv = document.createElement("div");
    alertDiv.style.position = "fixed";
    alertDiv.style.bottom = "20px";
    alertDiv.style.left = "50%";
    alertDiv.style.transform = "translateX(-50%)";
    alertDiv.style.background = "var(--color-primary)";
    alertDiv.style.color = "#000";
    alertDiv.style.padding = "0.5rem 1rem";
    alertDiv.style.borderRadius = "4px";
    alertDiv.style.fontSize = "0.75rem";
    alertDiv.style.fontWeight = "700";
    alertDiv.style.zIndex = "99999";
    alertDiv.innerText = `기기 ID [${code}] 복사 완료!`;
    document.body.appendChild(alertDiv);
    setTimeout(() => alertDiv.remove(), 1500);
  }).catch(err => {
    alert("복사 실패: " + err);
  });
}

export async function openDestinationDetailModal(destId) {
  const modal = document.getElementById("dest-detail-modal");
  if (!modal || !state.rawDestinations) return;

  const d = state.rawDestinations.find(x => x.dest_id === destId);
  if (!d) return;

  // Set Inputs
  document.getElementById("detail-dest-id").value = d.dest_id;
  document.getElementById("detail-dest-id-text").innerText = d.dest_id;
  document.getElementById("detail-dest-name").innerText = d.name || "이름 없음";

  // 기본값 설정 (NULL일 경우 각각 1000과 4가 기본값으로 입력되도록 설정)
  document.getElementById("detail-dest-total-limit").value = d.max_total_limit !== null && d.max_total_limit !== undefined ? d.max_total_limit : 1000;
  document.getElementById("detail-dest-active-slots").value = d.max_active_slots !== null && d.max_active_slots !== undefined ? d.max_active_slots : 4;
  document.getElementById("detail-dest-optimizer-check").checked = !!d.is_optimizer;

  modal.style.display = "flex";
}

export async function saveDestinationDetailInfo() {
  const destIdVal = document.getElementById("detail-dest-id").value;
  const maxTotalLimit = parseInt(document.getElementById("detail-dest-total-limit").value, 10);
  const maxActiveSlots = parseInt(document.getElementById("detail-dest-active-slots").value, 10);
  const isOptimizer = document.getElementById("detail-dest-optimizer-check").checked ? 1 : 0;

  if (isNaN(maxTotalLimit) || maxTotalLimit < 0) {
    alert("일일 총 작업 제한은 0 이상의 숫자여야 합니다.");
    return;
  }
  if (isNaN(maxActiveSlots) || maxActiveSlots < 0) {
    alert("최대 활성 슬롯 제한은 0 이상의 숫자여야 합니다.");
    return;
  }

  try {
    const res = await fetch("/api/v1/admin/dest/update", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        dest_id: destIdVal,
        max_total_limit: maxTotalLimit,
        max_active_slots: maxActiveSlots,
        is_optimizer: isOptimizer
      })
    });
    if (!res.ok) throw new Error("Destination update failed");
    
    document.getElementById("dest-detail-modal").style.display = "none";
    window.fetchData(true);
  } catch (err) {
    alert("설정 저장 실패: " + err.message);
  }
}

// Action: Reset device penalty from detail modal
export async function resetDetailPenalty() {
  const deviceId = document.getElementById("detail-device-id").value;
  if (!deviceId) return;
  if (deviceId.startsWith("GROUP:")) return; // Group edit ignore
  
  if (window.resetPenalty) {
    await window.resetPenalty(deviceId);
    document.getElementById('device-detail-modal').style.display = 'none';
  }
}

// Bind to window for HTML click handlers
window.openDeviceDetailModal = openDeviceDetailModal;
window.openEditDeviceGroupModal = openEditDeviceGroupModal;
window.saveDetailDeviceInfo = saveDetailDeviceInfo;
window.toggleDetailMute = toggleDetailMute;
window.copyDeviceCode = copyDeviceCode;
window.copyDeviceID = copyDeviceCode;
window.openDestinationDetailModal = openDestinationDetailModal;
window.saveDestinationDetailInfo = saveDestinationDetailInfo;
window.resetDetailPenalty = resetDetailPenalty;
