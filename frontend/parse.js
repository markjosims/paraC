import { fetchInflectionMeta, parse, search } from './api.js';

let metaData = null;

const targetSelect = document.getElementById('parse-target');
const formInput = document.getElementById('parse-form');
const submitBtn = document.getElementById('submit-parse-btn');
const fuzzyToggle = document.getElementById('fuzzy-toggle-btn');
const resultsSection = document.getElementById('parse-results');
const resultsTable = document.getElementById('parse-results-table');

async function loadMeta() {
  try {
    metaData = await fetchInflectionMeta();
    updateTargets();
  } catch (err) {
    console.error('Failed to load parse meta:', err);
  }
}

function updateTargets() {
  if (!metaData) return;
  targetSelect.innerHTML = '';
  metaData.paradigms.forEach(t => {
    const opt = document.createElement('option');
    opt.value = t.name;
    opt.textContent = t.name;
    targetSelect.appendChild(opt);
  });
}

submitBtn.addEventListener('click', async () => {
  const name = targetSelect.value;
  const form = formInput.value.trim();
  if (!form) return;

  submitBtn.disabled = true;
  resultsSection.setAttribute('hidden', '');
  try {
    const data = fuzzyToggle.checked
      ? await search("Paradigm", name, form)
      : await parse("Paradigm", name, form);
    const thead = resultsTable.tHead;
    const tbody = resultsTable.tBodies[0];
    thead.innerHTML = '';
    tbody.innerHTML = '';

    if (!data.parses.length) {
      const row = tbody.insertRow();
      const cell = row.insertCell();
      cell.textContent = '(no parses)';
      cell.colSpan = 99;
    } else {
      const fuzzy = fuzzyToggle.checked;
      const featKeys = [...new Set(data.parses.flatMap(p => Object.keys(p.features)))];
      const headers = [
        ...(fuzzy ? ['Form'] : []),
        'Root', 'Gloss',
        ...featKeys,
        ...(fuzzy ? ['Edit distance'] : []),
      ];
      const hRow = thead.insertRow();
      headers.forEach(h => { const th = document.createElement('th'); th.textContent = h; hRow.appendChild(th); });

      data.parses.forEach(p => {
        const row = tbody.insertRow();
        const cells = [
          ...(fuzzy ? [p.form ?? ''] : []),
          `√${p.root}`, p.gloss,
          ...featKeys.map(k => p.features[k] ?? ''),
          ...(fuzzy ? [p.edit_distance ?? ''] : []),
        ];
        cells.forEach(val => { const td = row.insertCell(); td.textContent = val; });
      });
    }
    resultsSection.removeAttribute('hidden');
  } catch (err) {
    alert(err.message);
  } finally {
    submitBtn.disabled = false;
  }
});

document.querySelector('[data-tab="parse"]').addEventListener('click', () => {
  if (!metaData) loadMeta();
});
