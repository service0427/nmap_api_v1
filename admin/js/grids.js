import { state } from './state.js';

export function initGrids() {
  // 1. Destinations Grid
  const destinationsGridOptions = {
    columnDefs: [
      { field: "site_id", headerName: "사이트", width: 110, filter: true },
      { 
        field: "dest_id", 
        headerName: "목적지 ID", 
        cellClass: 'font-mono', 
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
      { field: "name", headerName: "상호", width: 220, filter: true },
      { 
        field: "is_optimizer", 
        headerName: "옵티마이저", 
        width: 110,
        cellRenderer: p => `
          <span class="badge ${p.value ? 'success' : 'secondary'}" style="cursor:pointer; padding: 0.15rem 0.4rem;" onclick="window.updateDestOptimizer('${p.data.dest_id}', ${p.value ? 0 : 1})" title="클릭하여 옵티마이저 토글">
            ${p.value ? 'ON' : 'OFF'}
          </span>
        `
      },
      { 
        field: "check_status", 
        headerName: "상태", 
        width: 110,
        cellRenderer: p => {
          const mapping = {
            'VERIFIED': '<span class="badge success">검증 완료</span>',
            'NORMAL': '<span class="badge info">일반</span>',
            'PENDING': '<span class="badge warning">대기</span>',
            'FAIL': '<span class="badge danger">실패</span>'
          };
          return mapping[p.value] || `<span class="badge secondary">${p.value || '미점검'}</span>`;
        }
      },
       { 
        field: "slot_status", 
        headerName: "슬롯 상태", 
        width: 100,
        cellRenderer: p => `
          <span class="badge ${p.value === 'on' ? 'success' : 'danger'}">
            ${p.value === 'on' ? '활성' : '비활성'}
          </span>
        `
      },
      { 
        field: "target", 
        headerName: "목표 할당량", 
        width: 100,
        valueFormatter: p => p.value || 0
      },
      { 
        field: "success", 
        headerName: "오늘 성공", 
        width: 100,
        valueFormatter: p => p.value || 0
      },
      { 
        field: "fail", 
        headerName: "오늘 실패", 
        width: 150,
        cellRenderer: p => {
          const f = p.value || 0;
          const miss = p.data.miss || 0;
          const timeout = p.data.timeout || 0;
          const mismatch = p.data.mismatch || 0;
          if (f > 0) {
            let tooltip = `미노출(Miss): ${miss}건 | 네트워크: ${timeout}건 | 신원오류: ${mismatch}건`;
            return `<span class="badge danger" style="font-weight:700;" title="${tooltip}">${f} 실패 (M:${miss}|N:${timeout}|I:${mismatch})</span>`;
          }
          return `<span class="badge warning" style="font-weight:700;">0 실패</span>`;
        }
      },
      { 
        field: "y_success", 
        headerName: "어제 성공", 
        width: 100,
        valueFormatter: p => p.value || 0
      },
      { 
        field: "y_fail", 
        headerName: "어제 실패", 
        width: 100,
        valueFormatter: p => p.value || 0
      },
      { 
        field: "start_date", 
        headerName: "시작일", 
        width: 110,
        valueFormatter: p => p.value ? p.value.substring(0, 10) : ''
      },
      { 
        field: "end_date", 
        headerName: "만료일", 
        width: 110,
        valueFormatter: p => p.value ? p.value.substring(0, 10) : ''
      }
    ],
    pagination: true,
    paginationPageSize: 100,
    paginationPageSizeSelector: [50, 100, 200],
    enableCellTextSelection: true,
    ensureDomOrder: true
  };
  state.destinationsGridApi = agGrid.createGrid(document.querySelector('#grid-destinations'), destinationsGridOptions);

  // 2. Logs Grid
  const logsGridOptions = {
    columnDefs: [
      { field: "id", headerName: "ID", width: 80, cellClass: 'text-muted' },
      { field: "dest_name", headerName: "목적지명", width: 220 },
      { field: "device_id", headerName: "장비 ID", cellClass: 'font-mono', width: 140 },
      { field: "ip", headerName: "할당 IP", cellClass: 'font-mono', width: 130 },
      { 
        field: "status", 
        headerName: "수행 상태", 
        width: 110,
        cellRenderer: p => `
          <span class="badge ${p.value === 'SUCCESS' ? 'success' : (p.value === 'FAIL' ? 'danger' : 'info')}">
            ${p.value}
          </span>
        `
      },
      { 
        field: "start_time", 
        headerName: "시작 시간", 
        width: 130,
        valueFormatter: p => p.value ? p.value.substring(11, 19) : "--"
      },
      { 
        field: "end_time", 
        headerName: "종료 시간", 
        width: 130,
        valueFormatter: p => p.value ? p.value.substring(11, 19) : "--"
      }
    ],
    pagination: true,
    paginationPageSize: 100,
    paginationPageSizeSelector: [50, 100, 200]
  };
  state.logsGridApi = agGrid.createGrid(document.querySelector('#grid-logs'), logsGridOptions);
}
