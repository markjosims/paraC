import { fetchInflectionMeta, fetchRoots, fetchLexicalFeatures, runInflection } from './api.js';

let metaData = null;

const typeSelect = document.getElementById('inflect-type');
const targetSelect = document.getElementById('inflect-target');
const stemsContainer = document.getElementById('stems-container');
const featuresContainer = document.getElementById('features-container');
const submitBtn = document.getElementById('submit-inflect-btn');
const resultsSection = document.getElementById('inflection-results');
const formsList = document.getElementById('result-forms-list');
const stagesTableHead = document.querySelector('#stages-table thead');
const stagesTableBody = document.querySelector('#stages-table tbody');
const navInflectBtn = document.getElementById('nav-inflect-btn');

async function loadMeta() {
  try {
    metaData = await fetchInflectionMeta();
    updateTargets();
  } catch (err) {
    console.error('Failed to load inflection meta:', err);
  }
}

function updateTargets() {
  if (!metaData) return;
  const type = typeSelect.value;
  targetSelect.innerHTML = '';

  const targets = type === 'paradigm' ? metaData.paradigms : metaData.sequences;
  targets.forEach(t => {
    const opt = document.createElement('option');
    opt.value = t.name;
    opt.textContent = t.name;
    targetSelect.appendChild(opt);
  });

  updateFields();
}

async function updateFields() {
  if (!metaData) return;
  const type = typeSelect.value;
  const targetName = targetSelect.value;

  stemsContainer.innerHTML = '';
  featuresContainer.innerHTML = '';
  resultsSection.setAttribute('hidden', '');

  if (!targetName) return;

  if (type === 'paradigm') {
    const p = metaData.paradigms.find(x => x.name === targetName);
    if (!p) return;

    const select = buildRootSelect(`Select a root…`);
    try {
      const roots = await fetchRoots('paradigm', targetName);
      populateRootSelect(select, roots);
    } catch (err) {
      console.warn('Failed to load roots:', err);
    }
    select.addEventListener('change', () => onRootChange('paradigm', targetName, select.value));
    stemsContainer.appendChild(select);

    const allFeatures = [...new Set([...p.features, ...p.lexical_features])];
    renderFeatureSelectors(allFeatures);

  } else {
    const seq = metaData.sequences.find(x => x.name === targetName);
    if (!seq) return;

    for (let i = 0; i < seq.num_stems; i++) {
      const kind = seq.stem_kinds?.[i];
      const name = seq.stem_names?.[i];

      if (kind && name) {
        const apiKind = kind.toLowerCase();
        const select = buildRootSelect(`Select ${name} root…`);
        try {
          const roots = await fetchRoots(apiKind, name);
          populateRootSelect(select, roots);
        } catch (err) {
          console.warn(`Failed to load roots for ${name}:`, err);
        }
        select.addEventListener('change', () => onRootChange(apiKind, name, select.value));
        stemsContainer.appendChild(select);
      } else {
        const input = document.createElement('input');
        input.type = 'text';
        input.placeholder = `Stem ${i + 1}`;
        input.className = 'stem-input';
        stemsContainer.appendChild(input);
      }
    }

    renderFeatureSelectors(seq.features);
  }
}

function buildRootSelect(placeholder) {
  const select = document.createElement('select');
  select.className = 'stem-input root-select';
  const blank = document.createElement('option');
  blank.value = '';
  blank.textContent = placeholder;
  select.appendChild(blank);
  return select;
}

function populateRootSelect(select, roots) {
  roots.forEach(r => {
    const opt = document.createElement('option');
    opt.value = r;
    opt.textContent = r;
    select.appendChild(opt);
  });
}

async function onRootChange(kind, name, root) {
  if (!root) return;
  try {
    const lexFeatures = await fetchLexicalFeatures(kind, name, root);
    applyLexicalFeatures(lexFeatures);
  } catch (err) {
    console.warn('Failed to load lexical features:', err);
  }
}

function applyLexicalFeatures(lexFeatures) {
  featuresContainer.querySelectorAll('.feature-select').forEach(sel => {
    const val = lexFeatures[sel.dataset.feature];
    if (val !== undefined) {
      sel.value = val;
      sel.disabled = true;
    }
  });
}

function renderFeatureSelectors(featuresList) {
  featuresList.forEach(featName => {
    const values = metaData.features[featName] || [];
    
    const fieldWrapper = document.createElement('div');
    fieldWrapper.style.display = 'flex';
    fieldWrapper.style.flexDirection = 'column';
    fieldWrapper.style.gap = '0.25rem';

    const label = document.createElement('span');
    label.textContent = featName;
    label.style.fontSize = '0.85rem';
    label.style.fontWeight = 'bold';

    const select = document.createElement('select');
    select.className = 'feature-select';
    select.dataset.feature = featName;

    const defOpt = document.createElement('option');
    defOpt.value = 'unmarked';
    defOpt.textContent = 'unmarked';
    select.appendChild(defOpt);

    values.forEach(v => {
      const opt = document.createElement('option');
      opt.value = v;
      opt.textContent = v;
      select.appendChild(opt);
    });

    fieldWrapper.appendChild(label);
    fieldWrapper.appendChild(select);
    featuresContainer.appendChild(fieldWrapper);
  });
}

typeSelect.addEventListener('change', updateTargets);
targetSelect.addEventListener('change', updateFields);
navInflectBtn.addEventListener('click', loadMeta);

submitBtn.addEventListener('click', async () => {
  if (!metaData) return;
  const type = typeSelect.value;
  const name = targetSelect.value;

  const stemInputs = stemsContainer.querySelectorAll('.stem-input');
  const stems = Array.from(stemInputs).map(inp => inp.value.trim()).filter(Boolean);

  if (stems.length === 0) {
    alert('Please enter at least one stem / root.');
    return;
  }

  const features = {};
  const featureSelects = featuresContainer.querySelectorAll('.feature-select');
  featureSelects.forEach(sel => {
    features[sel.dataset.feature] = sel.value;
  });

  submitBtn.disabled = true;
  submitBtn.textContent = 'Generating...';

  try {
    const res = await runInflection(type, name, stems, features);
    displayResults(type, res);
  } catch (err) {
    alert(err.message);
  } finally {
    submitBtn.disabled = false;
    submitBtn.textContent = 'Generate Inflected Forms';
  }
});

function displayResults(type, data) {
  resultsSection.removeAttribute('hidden');
  
  formsList.innerHTML = '';
  if (data.forms && data.forms.length > 0) {
    data.forms.forEach(f => {
      const div = document.createElement('div');
      div.textContent = f;
      formsList.appendChild(div);
    });
  } else {
    formsList.innerHTML = '<span style="color:#ef4444;">No forms generated.</span>';
  }

  stagesTableHead.innerHTML = '';
  stagesTableBody.innerHTML = '';

  if (type === 'paradigm') {
    stagesTableHead.innerHTML = `
      <tr>
        <th>Order</th>
        <th>Marker Kind</th>
        <th>Marker Value</th>
        <th>Feature Value</th>
        <th>Form</th>
      </tr>
    `;

    data.stages.forEach(s => {
      const tr = document.createElement('tr');
      tr.innerHTML = `
        <td>${s.order ?? ''}</td>
        <td>${s.marker_kind ?? ''}</td>
        <td>${s.marker_value ?? ''}</td>
        <td>${s.feature_value ?? ''}</td>
        <td>${s.form ?? ''}</td>
      `;
      stagesTableBody.appendChild(tr);
    });
  } else {
    stagesTableHead.innerHTML = `
      <tr>
        <th>Step</th>
        <th>Kind</th>
        <th>Value</th>
        <th>Form</th>
      </tr>
    `;

    data.stages.forEach(s => {
      const tr = document.createElement('tr');
      tr.innerHTML = `
        <td>${s.step ?? ''}</td>
        <td>${s.kind ?? ''}</td>
        <td>${s.value ?? ''}</td>
        <td>${s.form ?? ''}</td>
      `;
      stagesTableBody.appendChild(tr);
    });
  }
}

loadMeta();
