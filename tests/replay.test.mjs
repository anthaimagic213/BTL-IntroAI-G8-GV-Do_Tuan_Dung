import test from 'node:test';
import assert from 'node:assert/strict';
import { ReplayEngine } from '../frontend/replay.js';

function harness() {
  const jobs = new Map();
  const seen = [];
  let counter = 0;
  let finished = 0;
  let delay = 50;
  const engine = new ReplayEngine({
    onStep: (step, index, total) => seen.push([step, index, total]),
    onFinish: () => finished++, getDelay: () => delay,
    schedule: (callback, ms) => { jobs.set(++counter, { callback, ms }); return counter; },
    cancel: (id) => jobs.delete(id),
  });
  return { engine, jobs, seen, finished: () => finished, setDelay: (ms) => { delay = ms; },
    tick: () => { const [id, job] = jobs.entries().next().value; jobs.delete(id); job.callback(); } };
}

test('replay preserves order and finishes once', () => {
  const h = harness();
  h.engine.load(['ASSIGN', 'PRUNE', 'SUCCESS']);
  h.engine.resume();
  h.engine.resume();
  assert.equal(h.jobs.size, 1);
  h.tick(); h.tick(); h.tick();
  assert.deepEqual(h.seen, [['ASSIGN', 1, 3], ['PRUNE', 2, 3], ['SUCCESS', 3, 3]]);
  assert.equal(h.finished(), 1);
  assert.equal(h.jobs.size, 0);
  h.engine.resume();
  assert.equal(h.jobs.size, 0);
});

test('pause cancels timer; resume does not skip or duplicate steps', () => {
  const h = harness();
  h.engine.load([1, 2]); h.engine.resume(); h.tick();
  h.engine.pause();
  assert.equal(h.jobs.size, 0);
  assert.equal(h.engine.index, 1);
  h.engine.resume(); h.tick();
  assert.deepEqual(h.seen.map((item) => item[0]), [1, 2]);
});

test('speed changes apply to next scheduled step', () => {
  const h = harness();
  h.engine.load([1, 2]); h.engine.resume();
  assert.equal([...h.jobs.values()][0].ms, 50);
  h.setDelay(1); h.tick();
  assert.equal([...h.jobs.values()][0].ms, 1);
});

test('load and stop discard old timers', () => {
  const h = harness();
  h.engine.load(['old']); h.engine.resume();
  h.engine.load(['new']);
  assert.equal(h.jobs.size, 0);
  h.engine.resume(); h.tick();
  assert.equal(h.seen[0][0], 'new');
  h.engine.stop();
  assert.equal(h.engine.index, 0);
  assert.deepEqual(h.engine.history, []);
});