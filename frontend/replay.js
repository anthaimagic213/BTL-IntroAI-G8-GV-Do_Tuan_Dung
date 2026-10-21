/** Chỉ lập lịch phát dữ liệu có sẵn, hoàn toàn không chứa luật Sudoku. */
export class ReplayEngine {
  constructor({ onStep, onFinish, getDelay,
    schedule = (callback, ms) => globalThis.setTimeout(callback, ms),
    cancel = (id) => globalThis.clearTimeout(id) }) {
    Object.assign(this, { onStep, onFinish, getDelay, schedule, cancel });
    this.history = [];
    this.index = 0;
    this.timer = null;
    this.running = false;
  }

  load(history) {
    this.stop();
    this.history = history;
    this.index = 0;
  }

  resume() {
    if (this.running || this.index >= this.history.length) return;
    this.running = true;
    this.queueNext();
  }

  queueNext() {
    this.timer = this.schedule(() => {
      this.timer = null;
      if (!this.running) return;
      this.onStep(this.history[this.index++], this.index, this.history.length);
      if (this.index === this.history.length) {
        this.running = false;
        this.onFinish();
      } else if (this.running) {
        this.queueNext();
      }
    }, this.getDelay());
  }

  pause() {
    this.running = false;
    if (this.timer !== null) this.cancel(this.timer);
    this.timer = null;
  }

  stop() {
    this.pause();
    this.history = [];
    this.index = 0;
  }
}