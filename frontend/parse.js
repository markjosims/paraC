import { fetchInflectionMeta, parse } from './api.js';

let metaData = null;

const targetSelect = document.getElementById('parse-target');
const formInput = document.getElementById('parse-form');
const submitBtn = document.getElementById('submit-parse-btn');
const resultsSection = document.getElementById('parse-results');
const resultsList = document.getElementById('parse-results-list');

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
    const data = await parse('paradigm', name, form);
    resultsList.innerHTML = '';
    if (!data.parses.length) {
      resultsList.textContent = '(no parses)';
    } else {
      data.parses.forEach(p => {
        const div = document.createElement('div');
        const featStr = Object.entries(p.features).map(([f, v]) => `[${f}=${v}]`).join('');
        div.textContent = `${p.root} ${featStr}`;
        resultsList.appendChild(div);
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
