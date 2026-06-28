import { fetchInflectionMeta, parse } from './api.js';

let metaData = null;

const typeSelect = document.getElementById('parse-type');
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
  const type = typeSelect.value;
  targetSelect.innerHTML = '';
  const items = type === 'paradigm' ? metaData.paradigms : metaData.sequences;
  items.forEach(t => {
    const opt = document.createElement('option');
    opt.value = t.name;
    opt.textContent = t.name;
    targetSelect.appendChild(opt);
  });
}

typeSelect.addEventListener('change', updateTargets);

submitBtn.addEventListener('click', async () => {
  const kind = typeSelect.value;
  const name = targetSelect.value;
  const form = formInput.value.trim();
  if (!form) return;

  submitBtn.disabled = true;
  resultsSection.setAttribute('hidden', '');
  try {
    const data = await parse(kind, name, form);
    resultsList.innerHTML = '';
    if (!data.parses.length) {
      resultsList.textContent = '(no parses)';
    } else {
      data.parses.forEach(p => {
        const div = document.createElement('div');
        div.textContent = p;
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
