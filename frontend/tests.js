import { fetchPatterns, fetchRules, testPattern, testRule } from './api.js';

let allPatterns = [];
let allRules = [];

const scopeSelect = document.getElementById('tests-scope');
const targetGroup = document.getElementById('tests-target-group');
const targetSelect = document.getElementById('tests-target');
const freeformGroup = document.getElementById('tests-freeform-group');
const freeformInput = document.getElementById('tests-freeform-input');
const targetInfo = document.getElementById('tests-target-info');
const targetValue = document.getElementById('tests-target-value');

const customPatternTest = document.getElementById('custom-pattern-test');
const customRuleTest = document.getElementById('custom-rule-test');
const includesList = document.getElementById('custom-includes-list');
const excludesList = document.getElementById('custom-excludes-list');
const mappingsList = document.getElementById('custom-mappings-list');

const resultsSection = document.getElementById('custom-test-results');
const resultsSummary = document.getElementById('custom-test-summary');
const resultsTable = document.getElementById('custom-results-table');

async function loadData() {
  try {
    [allPatterns, allRules] = await Promise.all([fetchPatterns(), fetchRules()]);
    populateTargets();
  } catch (err) {
    console.error('Failed to load patterns/rules:', err);
  }
}

function populateTargets() {
  const scope = scopeSelect.value;
  resetResults();

  if (scope === 'freeform') {
    targetGroup.setAttribute('hidden', '');
    freeformGroup.removeAttribute('hidden');
    targetInfo.setAttribute('hidden', '');
    customPatternTest.removeAttribute('hidden');
    customRuleTest.setAttribute('hidden', '');
    includesList.innerHTML = '';
    excludesList.innerHTML = '';
    addStringRow(includesList);
    return;
  }

  freeformGroup.setAttribute('hidden', '');
  targetGroup.removeAttribute('hidden');

  const items = scope === 'defined' ? allPatterns : allRules;
  targetSelect.innerHTML = '';
  items.forEach(item => {
    const opt = document.createElement('option');
    opt.value = scope === 'defined' ? item.ref : item.name;
    opt.textContent = scope === 'defined' ? item.ref : item.name;
    targetSelect.appendChild(opt);
  });

  onTargetChange();
}

function onTargetChange() {
  const scope = scopeSelect.value;
  resetResults();

  if (scope === 'defined') {
    const ref = targetSelect.value;
    const pattern = allPatterns.find(p => p.ref === ref);
    if (!pattern) return;

    targetInfo.removeAttribute('hidden');
    targetValue.textContent = pattern.value;
    customPatternTest.removeAttribute('hidden');
    customRuleTest.setAttribute('hidden', '');
    includesList.innerHTML = '';
    excludesList.innerHTML = '';
    addStringRow(includesList);
  } else if (scope === 'rules') {
    targetInfo.setAttribute('hidden', '');
    customRuleTest.removeAttribute('hidden');
    customPatternTest.setAttribute('hidden', '');
    mappingsList.innerHTML = '';
    addMappingRow();
  }
}

function resetResults() {
  resultsSection.setAttribute('hidden', '');
  resultsTable.querySelector('thead').innerHTML = '';
  resultsTable.querySelector('tbody').innerHTML = '';
}

function addStringRow(container) {
  const row = document.createElement('div');
  row.className = 'string-row';
  const input = document.createElement('input');
  input.type = 'text';
  input.className = 'string-input';
  input.placeholder = 'e.g. a, ba, …';
  const removeBtn = document.createElement('button');
  removeBtn.textContent = '×';
  removeBtn.className = 'remove-row-btn';
  removeBtn.addEventListener('click', () => {
    if (container.children.length > 1) row.remove();
  });
  row.appendChild(input);
  row.appendChild(removeBtn);
  container.appendChild(row);
}

function addMappingRow() {
  const row = document.createElement('div');
  row.className = 'mapping-row';
  const inputA = document.createElement('input');
  inputA.type = 'text';
  inputA.className = 'string-input';
  inputA.placeholder = 'input';
  const arrow = document.createElement('span');
  arrow.textContent = '→';
  arrow.className = 'mapping-arrow';
  const inputB = document.createElement('input');
  inputB.type = 'text';
  inputB.className = 'string-input';
  inputB.placeholder = 'expected output';
  const removeBtn = document.createElement('button');
  removeBtn.textContent = '×';
  removeBtn.className = 'remove-row-btn';
  removeBtn.addEventListener('click', () => {
    if (mappingsList.children.length > 1) row.remove();
  });
  row.appendChild(inputA);
  row.appendChild(arrow);
  row.appendChild(inputB);
  row.appendChild(removeBtn);
  mappingsList.appendChild(row);
}

function getStringValues(container) {
  return Array.from(container.querySelectorAll('.string-input'))
    .map(i => i.value.trim())
    .filter(Boolean);
}

function getMappingValues() {
  return Array.from(mappingsList.querySelectorAll('.mapping-row'))
    .map(row => {
      const inputs = row.querySelectorAll('.string-input');
      return [inputs[0].value.trim(), inputs[1].value.trim()];
    })
    .filter(([a, b]) => a || b);
}

function renderResults(result, isPattern) {
  resultsSection.removeAttribute('hidden');
  const allPass = result.all_pass;
  resultsSummary.textContent = allPass ? '✓ All passed' : '✗ Some failed';
  resultsSummary.className = 'test-summary ' + (allPass ? 'pass' : 'fail');

  const thead = resultsTable.querySelector('thead');
  const tbody = resultsTable.querySelector('tbody');
  tbody.innerHTML = '';

  if (isPattern) {
    thead.innerHTML = '<tr><th>String</th><th>Kind</th><th>Result</th></tr>';
    result.results.forEach(r => {
      const tr = document.createElement('tr');
      tr.innerHTML = `
        <td><code>${r.string}</code></td>
        <td>${r.test_kind}</td>
        <td class="${r.pass ? 'pass' : 'fail'}">${r.pass ? '✓ pass' : '✗ fail'}</td>
      `;
      tbody.appendChild(tr);
    });
  } else {
    thead.innerHTML = '<tr><th>Input</th><th>Expected</th><th>Got</th><th>Result</th></tr>';
    result.results.forEach(r => {
      const outputs = Array.isArray(r.output) ? r.output.join(', ') : (r.output ?? '—');
      const tr = document.createElement('tr');
      tr.innerHTML = `
        <td><code>${r.input}</code></td>
        <td><code>${r.expected_output}</code></td>
        <td><code>${outputs}</code></td>
        <td class="${r.pass ? 'pass' : 'fail'}">${r.pass ? '✓ pass' : '✗ fail'}</td>
      `;
      tbody.appendChild(tr);
    });
  }
}

document.getElementById('add-include-btn').addEventListener('click', () => addStringRow(includesList));
document.getElementById('add-exclude-btn').addEventListener('click', () => addStringRow(excludesList));
document.getElementById('add-mapping-btn').addEventListener('click', addMappingRow);

document.getElementById('run-pattern-test-btn').addEventListener('click', async () => {
  const scope = scopeSelect.value;
  const pattern = scope === 'freeform' ? freeformInput.value.trim() : targetSelect.value;
  if (!pattern) return;
  const includes = getStringValues(includesList);
  const excludes = getStringValues(excludesList);
  if (!includes.length && !excludes.length) return;
  try {
    const result = await testPattern(pattern, includes, excludes);
    renderResults(result, true);
  } catch (err) {
    alert(err.message);
  }
});

document.getElementById('run-rule-test-btn').addEventListener('click', async () => {
  const name = targetSelect.value;
  const mappings = getMappingValues();
  if (!mappings.length) return;
  try {
    const result = await testRule(name, mappings);
    renderResults(result, false);
  } catch (err) {
    alert(err.message);
  }
});

scopeSelect.addEventListener('change', populateTargets);
targetSelect.addEventListener('change', onTargetChange);

document.querySelector('[data-tab="tests"]').addEventListener('click', () => {
  if (!allPatterns.length && !allRules.length) loadData();
});
