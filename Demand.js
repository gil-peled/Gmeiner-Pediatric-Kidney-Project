/**
 * Demand module: takes Supply output (uses k0 list only).
 * Loads connections_k0.csv only. Returns list of consumer_IDs j that have at least
 * one connection to any supplier in the k0 list, and the size of that list.
 */

const CONNECTIONS_K0_URL = 'connections_k0.csv';

let cachedConnectionsK0 = null;

function parseCSV(text) {
  const lines = text.trim().split(/\r?\n/);
  if (lines.length === 0) return { header: [], rows: [] };
  const header = lines[0].split(',').map(c => c.trim());
  const rows = lines.slice(1).map(line => line.split(',').map(c => c.trim()));
  return { header, rows };
}

async function loadConnectionsK0(onStatus) {
  if (cachedConnectionsK0) return cachedConnectionsK0;
  if (onStatus) onStatus('Demand: loading connections_k0.csv…');
  const res = await fetch(CONNECTIONS_K0_URL);
  if (!res.ok) throw new Error(`Failed to load ${CONNECTIONS_K0_URL}: ${res.status}`);
  const text = await res.text();
  if (onStatus) onStatus('Demand: parsing connections_k0.csv…');
  const { header, rows } = parseCSV(text);
  const idxSupplier = header.findIndex(h => /supplier_id|supplier id/i.test(h));
  const idxConsumer = header.findIndex(h => /consumer_id|consumer id/i.test(h));
  if (idxSupplier === -1) throw new Error(`connections_k0.csv: missing supplier_id column. Header: ${header.join(', ')}`);
  if (idxConsumer === -1) throw new Error(`connections_k0.csv: missing consumer_id column. Header: ${header.join(', ')}`);
  const pairs = rows.map(row => ({
    supplierId: parseInt(row[idxSupplier], 10),
    consumerId: parseInt(row[idxConsumer], 10),
  })).filter(p => !isNaN(p.supplierId) && !isNaN(p.consumerId));
  cachedConnectionsK0 = pairs;
  return pairs;
}

/**
 * For a given k, supplier list S, and connection pairs (supplier_id, consumer_id):
 * j is in the output list if there exists some i in S with (i, j) in connections.
 * So: collect all consumer_id where supplier_id is in S, then unique.
 */
function consumerListForSupplierSet(pairs, supplierIdSet) {
  const consumerSet = new Set();
  for (const p of pairs) {
    if (supplierIdSet.has(p.supplierId)) {
      consumerSet.add(p.consumerId);
    }
  }
  return Array.from(consumerSet);
}

/**
 * Run Demand: input supplyOutput = { k0: { list, number }, ... }. Uses only k0 list.
 * options = { onStatus: (msg) => void }
 * Returns { k0: { list: number[], number: number } }.
 */
export async function run(supplyOutput, options = {}) {
  const onStatus = options.onStatus || (() => {});

  const pairs0 = await loadConnectionsK0(onStatus);

  onStatus('Demand: computing consumer list (K=0)…');
  const set0 = new Set(supplyOutput.k0.list);
  const list0 = consumerListForSupplierSet(pairs0, set0);

  return {
    k0: { list: list0, number: list0.length },
  };
}
