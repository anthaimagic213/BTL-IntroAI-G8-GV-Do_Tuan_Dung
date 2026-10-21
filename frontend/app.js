import { ReplayEngine } from './replay.js';

const $ = (id) => document.getElementById(id);
const boardElement = $('board');
const consoleElement = $('console');
const inputs = [];
const SAMPLE = [
  [5,3,0,0,7,0,0,0,0], [6,0,0,1,9,5,0,0,0], [0,9,8,0,0,0,0,6,0],
  [8,0,0,0,6,0,0,0,3], [4,0,0,8,0,3,0,0,1], [7,0,0,0,2,0,0,0,6],
  [0,6,0,0,0,0,2,8,0], [0,0,0,4,1,9,0,0,5], [0,0,0,0,8,0,0,7,9],
];
function readConfig() {
  const selected = (name) => document.querySelector(`input[name="${name}"]:checked`).value;
  const base_algorithm = selected('base_algorithm');
  if (base_algorithm === 'local_search') return { base_algorithm };
  return { base_algorithm, inference: selected('inference'),
    use_mrv: $('use-mrv').checked, use_lcv: $('use-lcv').checked,
    backtrack_strategy: selected('backtrack_strategy') };
}
let locked = new Set();
let originalBoard = null;
let busy = false;
let result = null;
let controller = null;
let generation = 0;
let logCount = 0;
let lastHighlighted = null;

// Tạo 81 input. Không tính peers, domains hay kiểm tra ràng buộc ở frontend.
for (let r = 0; r < 9; r++) {
  for (let c = 0; c < 9; c++) {
    const input = document.createElement('input');
    input.type = 'text';
    input.maxLength = 1;
    input.inputMode = 'numeric';
    input.pattern = '[1-9]';
    input.autocomplete = 'off';
    input.className = 'cell';
    input.setAttribute('aria-label', `Hàng ${r + 1}, cột ${c + 1}`);
    if (c === 2 || c === 5) input.classList.add('block-right');
    if (r === 2 || r === 5) input.classList.add('block-bottom');
    if (c === 8) input.classList.add('edge-right');
    if (r === 8) input.classList.add('edge-bottom');
    input.addEventListener('input', () => {
      input.value = input.value.replace(/[^1-9]/g, '').slice(-1);
      input.classList.toggle('cell-initial', input.value !== '');
      boardElement.classList.remove('board-success', 'board-fail');
    });
    input.addEventListener('keydown', (event) => {
      const offsets = { ArrowUp: -9, ArrowDown: 9, ArrowLeft: -1, ArrowRight: 1 };
      if (event.key in offsets) {
        event.preventDefault();
        inputs[(r * 9 + c + offsets[event.key] + 81) % 81].focus();
      }
    });
    inputs.push(input);
    boardElement.append(input);
  }
}

function readBoard() {
  return Array.from({ length: 9 }, (_, r) =>
    inputs.slice(r * 9, r * 9 + 9).map((input) => Number(input.value) || 0));
}

function renderBoard(board) {
  inputs.forEach((input, i) => { input.value = board[Math.floor(i / 9)][i % 9] || ''; });
}

function resetEffects() {
  if (lastHighlighted) {
    lastHighlighted.classList.remove('cell-assign', 'cell-prune', 'cell-backtrack');
    lastHighlighted = null;
  }
  boardElement.classList.remove('board-success', 'board-fail');
}

function showMetrics(metrics = { execution_time_ms: 0, peak_memory_kb: 0, total_assignments: 0, total_backtracks: 0, total_prunes: 0 }) {
  $('time').textContent = `${metrics.execution_time_ms.toLocaleString('vi-VN', { maximumFractionDigits: 2 })} ms`;
  $('assignments').textContent = metrics.total_assignments.toLocaleString('vi-VN');
  $('backtracks').textContent = metrics.total_backtracks.toLocaleString('vi-VN');
  $('memory').textContent = `${metrics.peak_memory_kb.toLocaleString('vi-VN', { maximumFractionDigits: 2 })} KB`;
  $('prunes').textContent = metrics.total_prunes.toLocaleString('vi-VN');
}

function appendLog(action, text, step = null) {
  const line = document.createElement('div');
  line.className = `log-line log-${action.toLowerCase()}`;
  const number = document.createElement('span');
  number.className = 'log-step';
  number.textContent = step === null ? '›' : String(step).padStart(5, '0');
  line.append(number, document.createTextNode(`[${action}] ${text}`));
  consoleElement.append(line);
  // History vẫn giữ nguyên; giới hạn DOM để replay dài không làm chậm trang.
  while (consoleElement.childElementCount > 600) consoleElement.firstElementChild.remove();
  consoleElement.scrollTop = consoleElement.scrollHeight;
  // Status phía bàn cờ có thể đổi chiều cao trong cùng frame (đặc biệt
  // ở bước kết thúc). Cuộn lại sau layout để dòng cuối không bị khuất.
  requestAnimationFrame(() => { consoleElement.scrollTop = consoleElement.scrollHeight; });
  $('log-count').textContent = `${++logCount} dòng · giữ 600 dòng gần nhất`;
}

function setBusy(value) {
  busy = value;
  describeAlgorithm();
  $('play').disabled = value;
  // Khóa cả ô trống để người dùng không làm sai snapshot đang phát.
  inputs.forEach((input) => { input.readOnly = value; });
}

const replay = new ReplayEngine({
  getDelay: () => Number($('speed').value),
  onStep: (step, index, total) => {
    resetEffects();
    renderBoard(step.board_snapshot);
    showMetrics(step.metrics);
    if (step.cell) {
      const input = inputs[step.cell[0] * 9 + step.cell[1]];
      const classes = { ASSIGN: 'cell-assign', BACKTRACK: 'cell-backtrack', PRUNE: 'cell-prune' };
      if (classes[step.action] && !locked.has(step.cell[0] * 9 + step.cell[1])) {
        // Buộc restart animation nếu hai sự kiện liên tiếp tác động cùng ô.
        void input.offsetWidth;
        input.classList.add(classes[step.action]);
        lastHighlighted = input;
      }
    }
    if (step.action === 'SUCCESS') boardElement.classList.add('board-success');
    if (step.action === 'FAIL') boardElement.classList.add('board-fail');
    $('step-label').textContent = `Bước ${index.toLocaleString('vi-VN')} / ${total.toLocaleString('vi-VN')}`;
    $('phase-label').textContent = step.action;
    $('progress').value = index;
    $('status').textContent = step.log;
    appendLog(step.action, step.log, step.step);
  },
  onFinish: () => {
    setBusy(false);
    $('pause').hidden = true;
    showMetrics(result.metrics);
    $('phase-label').textContent = { success: 'THÀNH CÔNG', unsolvable: 'VÔ NGHIỆM', not_found: 'CHƯA TÌM THẤY', limit_reached: 'ĐẠT GIỚI HẠN' }[result.status];
    // Kết thúc: trở lại đề gốc trước khi giải lại, không coi lời giải là đề mới.
    $('play').textContent = '↻ Giải lại đề gốc';
  },
});

function resetSession(board) {
  generation++;
  controller?.abort();
  controller = null;
  replay.stop();
  result = null;
  originalBoard = null;
  resetEffects();
  setBusy(false);
  locked = new Set();
  renderBoard(board);
  inputs.forEach((input) => input.classList.toggle('cell-initial', input.value !== ''));
  consoleElement.replaceChildren();
  logCount = 0;
  $('log-count').textContent = '0 sự kiện';
  showMetrics();
  $('pause').hidden = true;
  $('play').textContent = '▶ Giải Sudoku';
  $('progress').value = 0;
  $('progress').max = 1;
  $('step-label').textContent = 'Bước 0 / 0';
  $('phase-label').textContent = 'SẴN SÀNG';
}

$('play').addEventListener('click', async () => {
  if (busy) return;
  // Sau khi đã sửa bảng kết quả, coi nội dung sửa là một đề mới.
  const board = originalBoard ?? readBoard();
  resetSession(board);
  originalBoard = board.map((row) => [...row]);
  locked = new Set(inputs.flatMap((input, i) => input.value ? [i] : []));
  setBusy(true);
  $('play').textContent = 'Đang tính ở backend…';
  $('status').textContent = 'Đang ghi lại toàn bộ quá trình tại backend. Chưa phát animation.';
  $('phase-label').textContent = 'RECORD';
  const config = readConfig();
  appendLog('INFO', `Cấu hình: ${JSON.stringify(config)}. Backend ghi history một lần.`);
  const ticket = generation;
  controller = new AbortController();
  try {
    const response = await fetch('/solve', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ board, ...config }), signal: controller.signal,
    });
    const data = await response.json();
    if (ticket !== generation) return;
    if (!response.ok) {
      throw new Error(typeof data.detail === 'string' ? data.detail : 'Dữ liệu không hợp lệ: cần ma trận 9×9, số nguyên 0–9.');
    }
    if (!Array.isArray(data.history) || !data.history.length) throw new Error('Backend trả history rỗng.');
    result = data;
    replay.load(data.history);
    $('progress').max = data.history.length;
    $('pause').hidden = false;
    $('pause').textContent = 'Ⅱ Tạm dừng';
    $('play').textContent = 'Đang phát lại…';
    $('phase-label').textContent = 'REPLAY';
    appendLog('INFO', `Đã ghi ${data.history.length} bước. Tổng thời gian backend: ${data.metrics.execution_time_ms} ms.`);
    replay.resume();
  } catch (error) {
    if (ticket !== generation || error.name === 'AbortError') return;
    replay.stop();
    $('pause').hidden = true;
    setBusy(false);
    $('play').textContent = '▶ Thử lại';
    $('status').textContent = `Lỗi: ${error.message}`;
    $('phase-label').textContent = 'LỖI';
    appendLog('FAIL', error.message);
    originalBoard = null;
  } finally {
    if (ticket === generation) controller = null;
  }
});

inputs.forEach((input) => input.addEventListener('input', () => {
  if (!busy) {
    originalBoard = null;
    $('play').textContent = '▶ Giải Sudoku';
  }
}));

$('pause').addEventListener('click', () => {
  if (replay.running) {
    replay.pause();
    $('pause').textContent = '▶ Tiếp tục';
    $('phase-label').textContent = 'TẠM DỪNG';
  } else {
    $('pause').textContent = 'Ⅱ Tạm dừng';
    $('phase-label').textContent = 'REPLAY';
    replay.resume();
  }
});
$('clear').addEventListener('click', () => {
  resetSession(Array.from({ length: 9 }, () => Array(9).fill(0)));
  $('status').textContent = 'Đã xóa bảng. Nhập đề mới hoặc chọn “Tạo đề mẫu”.';
});
$('sample').addEventListener('click', () => {
  resetSession(SAMPLE);
  $('status').textContent = 'Đã tải đề mẫu. Chọn thuật toán và nhấn “Giải Sudoku”.';
});
$('speed').addEventListener('input', () => {
  $('speed-label').textContent = `${$('speed').value} ms / step`;
});
function describeAlgorithm() {
  const config = readConfig();
  const local = config.base_algorithm === 'local_search';
  $('base-options').disabled = busy;
  document.querySelectorAll('.dfs-options').forEach((group) => { group.disabled = busy || local; });
  $('algorithm-description').textContent = local
    ? 'Min-Conflicts: tối đa 10.000 bước, có restart; không đảm bảo tìm được lời giải.'
    : `DFS · ${config.inference.toUpperCase()} · MRV ${config.use_mrv ? 'bật' : 'tắt'} · LCV ${config.use_lcv ? 'bật' : 'tắt'} · ${config.backtrack_strategy.toUpperCase()}`;
  $('local-warning').hidden = !local;
}
document.querySelectorAll('.module-group input').forEach((input) => input.addEventListener('change', describeAlgorithm));
describeAlgorithm();