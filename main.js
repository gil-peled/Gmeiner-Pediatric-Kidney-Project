/**
 * Main orchestrator: reads form, validates, calls Supply then Demand.
 * Displays ERROR_INCOMPLETE if any field is missing.
 * Shows Supply and Demand tables for K=0 only.
 */
import { run as supplyRun } from './Supply.js';
import { run as demandRun } from './Demand.js';

const ERROR_INCOMPLETE = 'ERROR_INCOMPLETE';

function getValue(id) {
  const el = document.getElementById(id);
  if (!el) return '';
  const v = el.value;
  return typeof v === 'string' ? v.trim() : String(v ?? '');
}

function setResult(htmlOrText, isError) {
  const el = document.getElementById('result');
  if (!el) return;
  if (typeof htmlOrText === 'string' && !isError && (htmlOrText.startsWith('<') || htmlOrText.includes('<'))) {
    el.innerHTML = htmlOrText;
  } else {
    el.textContent = htmlOrText;
  }
  el.className = isError ? 'error' : '';
}

function setStatus(msg) {
  const el = document.getElementById('status');
  if (el) el.textContent = msg;
}

function formatListPreview(list, maxShow = 5) {
  if (!list || list.length === 0) return '{}';
  const show = list.slice(0, maxShow);
  const rest = list.length > maxShow ? `, ... (+${list.length - maxShow} more)` : '';
  return '{' + show.join(', ') + rest + '}';
}

function buildSupplyTable(supplyOutput) {
  const k0 = supplyOutput.k0;
  let html = '<table><thead><tr><th></th><th>K=0</th></tr></thead><tbody>';
  html += '<tr><td>List</td><td>' + formatListPreview(k0.list) + '</td></tr>';
  html += '<tr><td>Number</td><td>' + k0.number + '</td></tr>';
  html += '</tbody></table>';
  return html;
}

function buildDemandTable(demandOutput) {
  const k0 = demandOutput.k0;
  let html = '<table><thead><tr><th></th><th>K=0</th></tr></thead><tbody>';
  html += '<tr><td>List</td><td>' + formatListPreview(k0.list) + '</td></tr>';
  html += '<tr><td>Number</td><td>' + k0.number + '</td></tr>';
  html += '</tbody></table>';
  return html;
}

document.getElementById('input-form').addEventListener('submit', async (e) => {
  e.preventDefault();

  const center = getValue('center');
  const dr1 = getValue('dr1');
  const dr2 = getValue('dr2');
  const ua = getValue('ua');
  const bloodtype = getValue('bloodtype');

  const allPresent = center !== '' && dr1 !== '' && dr2 !== '' && ua !== '' && bloodtype !== '';

  if (!allPresent) {
    setResult(ERROR_INCOMPLETE, true);
    setStatus('Idle. Select all fields and click Calculate.');
    return;
  }

  const btn = document.getElementById('btn-calculate');
  if (btn.disabled) return;
  btn.disabled = true;
  setStatus('Starting…');
  setResult('', false);

  const userInput = { center, dr1, dr2, ua, bloodtype };

  try {
    setStatus('Supply: loading data…');
    const supplyOutput = await supplyRun(userInput, { onStatus: setStatus });
    setStatus('Supply done. Running Demand with Supply list as input…');
    setResult('<h3>Supply</h3>' + buildSupplyTable(supplyOutput), false);

    setStatus('Demand: using Supply list as input, loading connections…');
    const demandOutput = await demandRun(supplyOutput, { onStatus: setStatus });
    setStatus('Done.');
    const fullOutput = '<h3>Supply</h3>' + buildSupplyTable(supplyOutput) +
      '<h3>Demand</h3><p>Input: supplier lists from Supply above.</p>' + buildDemandTable(demandOutput);
    setResult(fullOutput, false);
  } catch (err) {
    setStatus('Error.');
    setResult('Error: ' + (err && err.message ? err.message : String(err)), true);
  } finally {
    btn.disabled = false;
    setStatus('Idle. Select all fields and click Calculate.');
  }
});
