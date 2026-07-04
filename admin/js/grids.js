import { state } from './state.js';

export function initGrids() {
  // 1. Destinations Grid
  const destinationsGridOptions = {
    columnDefs: [
      { 
        headerName: "No.", 
        valueGetter: "node.rowIndex + 1", 
        width: 60, 
        cellClass: 'text-muted font-mono',
        sortable: false
      },
      { field: "site_id", headerName: "사이트", width: 100, filter: true },
      { 
        field: "name", 
        headerName: "상호", 
        width: 260,
        filter: true,
        cellRenderer: p => {
          const name = p.value || '';
          const style = "cursor:pointer; text-decoration:underline; font-weight:600; color:var(--text-main); text-overflow:ellipsis; overflow:hidden; white-space:nowrap;";
          const adjustedBadge = p.data.is_adjusted ? `<span class="badge warning" style="font-weight:800; font-size:0.75rem; padding:0.15rem 0.35rem; margin-right:0.3rem; flex-shrink:0;" title="일일 총 한도 제한에 의해 작업 개수가 조율/감소되었습니다.">[한도]</span>` : '';
          
          let deleteBadge = '';
          if (name.startsWith('FAILED_SCRAPE_') || p.data.check_status === 'FAIL') {
            deleteBadge = `<span class="badge danger" style="font-weight:800; font-size:0.75rem; padding:0.15rem 0.35rem; margin-right:0.3rem; flex-shrink:0;">[지도 삭제/폐업]</span>`;
          }
          
          return `<div style="display:inline-flex; align-items:center; width:100%; overflow:hidden; text-overflow:ellipsis; white-space:nowrap;">
            ${deleteBadge}
            ${adjustedBadge}
            <span style="${style}" onclick="window.openDestinationDetailModal('${p.data.dest_id}')">${name}</span>
          </div>`;
        }
      },
      { 
        field: "dest_id", 
        headerName: "목적지 ID", 
        width: 140,
        cellRenderer: p => `
          <span class="font-mono" style="cursor:pointer; text-decoration:underline; font-weight:600; color:var(--color-primary);" onclick="window.copyToClipboard('${p.value}', this)" title="클릭하여 ID 복사">
            ${p.value}
          </span>
        `
      },
      { 
        field: "target", 
        headerName: "목표 할당량", 
        width: 110,
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
          return `<span style="color:var(--text-muted); font-weight:500;">0</span>`;
        }
      },
      { 
        headerName: "달성률", 
        width: 100,
        valueGetter: p => {
          const target = p.data.target || 0;
          const success = p.data.success || 0;
          if (target === 0) return "0.0%";
          return ((success / target) * 100).toFixed(1) + "%";
        },
        comparator: (valueA, valueB) => {
          return (parseFloat(valueA) || 0) - (parseFloat(valueB) || 0);
        },
        cellRenderer: p => {
          const target = p.data.target || 0;
          const success = p.data.success || 0;
          const pct = target > 0 ? (success / target) * 100 : 0;
          const color = pct >= 100 ? 'success' : (pct > 0 ? 'info' : 'secondary');
          return `<span class="badge ${color}" style="font-weight:700;">${pct.toFixed(1)}%</span>`;
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
        field: "max_total_limit", 
        headerName: "일일 제한", 
        width: 100,
        valueFormatter: p => p.value !== null && p.value !== undefined ? p.value : 20
      },
      { 
        field: "max_active_slots", 
        headerName: "슬롯 분산", 
        width: 100,
        valueFormatter: p => p.value !== null && p.value !== undefined ? p.value : 4
      },
      { 
        field: "is_optimizer", 
        headerName: "옵티마이저", 
        width: 110,
        cellRenderer: p => `
          <span class="badge ${p.value ? 'success' : 'secondary'}" style="cursor:pointer; padding: 0.15rem 0.4rem;" onclick="window.updateDestOptimizer('${p.data.dest_id}', ${p.value ? 0 : 1})" title="클릭하여 옵티마이저 토글">
            ${p.value ? 'ON' : 'OFF'}
          </span>
        `
      }
    ],
    pagination: true,
    paginationPageSize: 100,
    paginationPageSizeSelector: [50, 100, 200],
    enableCellTextSelection: true,
    ensureDomOrder: true
  };
  state.destinationsGridApi = agGrid.createGrid(document.querySelector('#grid-destinations'), destinationsGridOptions);
}
