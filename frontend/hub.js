import { fetchGrammarHealth, fetchGrammarStats, recompileGrammar } from './api.js';

let lastHealth = null;
let lastStats = null;
let isFetching = false;

const statusDot = document.querySelector('.status-dot');
const statusLabel = document.querySelector('.status-label');
const statsSection = document.getElementById('stats-section');
const statsGrid = document.getElementById('stats-grid');
const recompileBtn = document.getElementById('recompile-btn');


const CARD_KEYS = {
  inventory: {
    title: 'Inventory',
    format: (d) => [`${d.files} files`, `${d.phones} phones`, `${d.tags} tags`, `${d.classes} classes`]
  },
  feature_definitions: {
    title: 'Feat. Definitions',
    format: (d) => [`${d.files} files`, `${d.total} features`]
  },
  // TODO: FeatureCombinations, MorphemeSet and MorphemeSequence are buggy
  // so they are commented out for now
  // feature_combinations: {
  //   title: 'Feat. Combinations',
  //   format: (d) => [`${d.files} files`, `${d.total} combinations`]
  // },
  patterns: {
    title: 'Patterns',
    format: (d) => [`${d.files} files`, `${d.total} patterns`]
  },
  rules: {
    title: 'Rules',
    format: (d) => [`${d.files} files`, `${d.total} rules`]
  },
  feature_markers: {
    title: 'Feat. Markers',
    format: (d) => [`${d.files} files`, `${d.total} markers`]
  },
  contingent_markers: {
    title: 'Cont. Markers',
    format: (d) => [`${d.files} files`, `${d.total} markers`]
  },
  paradigms: {
    title: 'Paradigms',
    format: (d) => [`${d.files} files`, `${d.total} paradigms`]
  },
  part_of_speech: {
    title: 'Part of Sp.',
    format: (d) => [`${d.files} files`, `${d.total} lexemes`]
  },
  // morpheme_sets: {
  //   title: 'Morph. Sets',
  //   format: (d) => [`${d.files} files`, `${d.total} sets`]
  // },
  // morpheme_sequences: {
  //   title: 'Morph. Seqs.',
  //   format: (d) => [`${d.files} files`, `${d.total} sequences`]
  // }
};

function updateStatusUI(status) {
  statusDot.className = 'status-dot ' + status;
  if (status === 'loaded') statusLabel.textContent = 'Loaded';
  else if (status === 'unloaded') statusLabel.textContent = 'Not loaded';
  else if (status === 'error') statusLabel.textContent = 'Load error';
  else statusLabel.textContent = 'Checking…';
}

function renderStats(stats, isStale) {
  if (!stats) {
    statsSection.setAttribute('hidden', '');
    return;
  }
  statsSection.removeAttribute('hidden');
  
  if (isStale) {
    statsGrid.classList.add('stale');
  } else {
    statsGrid.classList.remove('stale');
  }

  statsGrid.innerHTML = '';
  for (const [key, meta] of Object.entries(CARD_KEYS)) {
    const data = stats[key];
    if (!data) continue;

    const card = document.createElement('div');
    card.className = 'stat-card';

    const title = document.createElement('h4');
    title.textContent = meta.title;
    card.appendChild(title);

    const list = document.createElement('ul');
    meta.format(data).forEach(line => {
      const li = document.createElement('li');
      li.textContent = line;
      list.appendChild(li);
    });
    card.appendChild(list);
    statsGrid.appendChild(card);
  }
}

async function checkGrammar() {
  if (isFetching) return;
  isFetching = true;

  let health = 'checking';
  let stats = null;

  try {
    const healthRes = await fetchGrammarHealth();
    health = healthRes.status;
  } catch {
    health = 'unloaded';
  }

  if (health === 'loaded') {
    try {
      stats = await fetchGrammarStats();
    } catch (err) {
      health = err.status === 503 ? 'error' : 'unloaded';
    }
  }

  lastHealth = health;
  if (stats) lastStats = stats;

  updateStatusUI(health);
  renderStats(lastStats, health !== 'loaded');
  isFetching = false;
}

recompileBtn.addEventListener('click', async () => {
  recompileBtn.disabled = true;
  recompileBtn.textContent = 'Recompiling...';
  try {
    await recompileGrammar();
  } catch (err) {
    alert(err.message);
  } finally {
    recompileBtn.disabled = false;
    recompileBtn.textContent = 'Recompile';
    await checkGrammar();
  }
});

checkGrammar();
setInterval(checkGrammar, 5000);

