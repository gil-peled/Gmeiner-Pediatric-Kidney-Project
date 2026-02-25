/**
 * Supply module: takes user input j* (Center, DR1, DR2, UA, Bloodtype),
 * loads supply.csv and center_crosswalk.csv, computes U(i,j*)(k) for each supplier i,
 * returns 3 lists of supplier_IDs (k=0,1,2) and their sizes.
 * Criteria: k = DR mismatches; Blood_type match; distance < 250; UA(j*) not in {DR1(i), DR2(i)}.
 */

const MAX_DISTANCE = 250;
const SUPPLY_URL = 'supply.csv';
const CENTER_CROSSWALK_URL = 'center_crosswalk.csv';

let cachedSupply = null;
let cachedValidPairs = null;

function parseCSV(text) {
  const lines = text.trim().split(/\r?\n/);
  if (lines.length === 0) return { header: [], rows: [] };
  const header = lines[0].split(',').map(c => c.trim());
  const rows = lines.slice(1).map(line => line.split(',').map(c => c.trim()));
  return { header, rows };
}

function buildValidPairs(crosswalkRows) {
  const pairs = new Set();
  for (const row of crosswalkRows) {
    const centerFrom = parseInt(row[0], 10);
    const centerTo = parseInt(row[1], 10);
    const distance = parseFloat(row[2]);
    if (!isNaN(centerFrom) && !isNaN(centerTo) && !isNaN(distance) && distance < MAX_DISTANCE) {
      pairs.add(`${centerFrom},${centerTo}`);
    }
  }
  return pairs;
}

async function loadSupply(onStatus) {
  if (cachedSupply) return cachedSupply;
  if (onStatus) onStatus('Supply: loading supply.csv…');
  const res = await fetch(SUPPLY_URL);
  if (!res.ok) throw new Error(`Failed to load ${SUPPLY_URL}: ${res.status}`);
  const text = await res.text();
  if (onStatus) onStatus('Supply: parsing supply.csv…');
  const { header, rows } = parseCSV(text);
  const col = (name) => {
    const i = header.findIndex(h => h.replace(/\s/g, '') === name.replace(/#/g, ''));
    if (i === -1) return header.findIndex(h => h.includes(name) || h === name);
    return i;
  };
  const idxId = header.findIndex(h => /Supplier_ID|Supplier ID/i.test(h));
  const idxCenter = header.findIndex(h => /Transplant_Center|Transplant Center|Center/i.test(h));
  const idxDr1 = header.findIndex(h => /DR#?1|DR1/i.test(h));
  const idxDr2 = header.findIndex(h => /DR#?2|DR2/i.test(h));
  const idxBlood = header.findIndex(h => /Blood_type|Blood type|Bloodtype/i.test(h));
  const data = rows.map(row => ({
    supplierId: parseInt(row[idxId], 10),
    center: parseInt(row[idxCenter], 10),
    dr1: parseInt(row[idxDr1], 10),
    dr2: parseInt(row[idxDr2], 10),
    bloodType: parseInt(row[idxBlood], 10),
  })).filter(r => !isNaN(r.supplierId));
  cachedSupply = data;
  return data;
}

async function loadValidPairs(onStatus) {
  if (cachedValidPairs) return cachedValidPairs;
  if (onStatus) onStatus('Supply: loading center_crosswalk.csv…');
  const res = await fetch(CENTER_CROSSWALK_URL);
  if (!res.ok) throw new Error(`Failed to load ${CENTER_CROSSWALK_URL}: ${res.status}`);
  const text = await res.text();
  const { header, rows } = parseCSV(text);
  const idxFrom = header.findIndex(h => /center_from|from/i.test(h));
  const idxTo = header.findIndex(h => /center_to|to/i.test(h));
  const idxDist = header.findIndex(h => /distance|dist/i.test(h));
  const fromCol = idxFrom >= 0 ? idxFrom : 0;
  const toCol = idxTo >= 0 ? idxTo : 1;
  const distCol = idxDist >= 0 ? idxDist : 2;
  const normalized = rows.map(row => [row[fromCol], row[toCol], row[distCol]]);
  cachedValidPairs = buildValidPairs(normalized);
  return cachedValidPairs;
}

/**
 * k = number of DR mismatches between j* and i: 0 = both match, 1 = one match, 2 = none.
 * Match: DR(j*) matches DR(i) in either position.
 */
function countDRMatches(dr1_j, dr2_j, dr1_i, dr2_i) {
  const match1 = (dr1_j === dr1_i || dr1_j === dr2_i);
  const match2 = (dr2_j === dr1_i || dr2_j === dr2_i);
  return (match1 ? 1 : 0) + (match2 ? 1 : 0);
}

/**
 * Run Supply: input user input j* = { center, dr1, dr2, ua, bloodtype }.
 * Returns { k0: { list: number[], number: number }, k1: {...}, k2: {...} }.
 */
export async function run(userInput, options = {}) {
  const onStatus = options.onStatus || (() => {});

  const center_j = parseInt(userInput.center, 10);
  const dr1_j = parseInt(userInput.dr1, 10);
  const dr2_j = parseInt(userInput.dr2, 10);
  const ua_j = parseInt(userInput.ua, 10);
  const bloodtype_j = parseInt(userInput.bloodtype, 10);

  onStatus('Supply: loading supply & center crosswalk…');
  const [supplyRows, validPairs] = await Promise.all([
    loadSupply(onStatus),
    loadValidPairs(onStatus),
  ]);

  onStatus('Supply: computing U(i,j*)(k) over ' + supplyRows.length + ' suppliers…');
  const listK0 = [];
  const listK1 = [];
  const listK2 = [];
  const progressEvery = Math.max(1, Math.floor(supplyRows.length / 20));

  for (let idx = 0; idx < supplyRows.length; idx++) {
    if (progressEvery && (idx + 1) % progressEvery === 0) {
      onStatus('Supply: computing… ' + (idx + 1) + ' / ' + supplyRows.length);
    }
    const i = supplyRows[idx];
    const pairKey = `${i.center},${center_j}`;
    if (!validPairs.has(pairKey)) continue;
    if (i.bloodType !== bloodtype_j) continue;
    if (ua_j === i.dr1 || ua_j === i.dr2) continue;

    const numMatches = countDRMatches(dr1_j, dr2_j, i.dr1, i.dr2);
    const k = 2 - numMatches;
    if (k === 0) listK0.push(i.supplierId);
    else if (k === 1) listK1.push(i.supplierId);
    else listK2.push(i.supplierId);
  }

  return {
    k0: { list: listK0, number: listK0.length },
    k1: { list: listK1, number: listK1.length },
    k2: { list: listK2, number: listK2.length },
  };
}
