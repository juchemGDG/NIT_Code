// app.js – iPad-Blockly: Blöcke + Live-Python-Editor + Konsole

// Inject-Optionen identisch zu NIT_Codes editor.html (gleiche Optik im iPad-Modus).
const workspace = Blockly.inject('blocklyDiv', {
  toolbox: document.getElementById('toolbox'),
  media: '/blockly/media/',
  renderer: 'zelos',
  trashcan: true,
  sounds: true,
  grid: { spacing: 22, length: 3, colour: '#e6e6ee', snap: true },
  zoom: { controls: true, wheel: true, startScale: 0.95, maxScale: 2, minScale: 0.4 },
  move: { scrollbars: true, drag: true, wheel: true }
});

const statusEl  = document.getElementById('status');
const codeEl    = document.getElementById('code');
const consoleEl = document.getElementById('console');
const btnEdit   = document.getElementById('btnEdit');
const boardEl   = document.getElementById('board');

// SSID dieses Boards anzeigen (hilft im Klassensatz, das richtige Board zu erkennen)
(async function showBoardName() {
  try {
    const res = await fetch('/api/info');
    if (!res.ok) return;
    const data = await res.json();
    if (data.ssid) boardEl.textContent = '📶 ' + data.ssid;
  } catch (e) { /* im Browser-Vorschaumodus ohne Board ignorieren */ }
})();

// manualMode = true: der Editor ist die Quelle (Blöcke überschreiben nicht mehr)
let manualMode = false;
let pollTimer = null;
let outputCursor = 0;   // wie viele Ausgabezeilen wir schon geholt haben

function generateCode() {
  try { return Blockly.Python.workspaceToCode(workspace); }
  catch (e) { return '# Fehler bei der Code-Erzeugung: ' + e; }
}

// Blöcke -> Editor (solange nicht manuell bearbeitet wird)
function refreshCodeFromBlocks() {
  if (manualMode) return;
  codeEl.value = generateCode();
}

// ── Speichern / Laden (Blockly-Serialisierung als JSON) ───────────────────
const AUTOSAVE_KEY = 'nit_autosave';
const PROJECTS_KEY = 'nit_projects';

function saveState() {
  return JSON.stringify(Blockly.serialization.workspaces.save(workspace));
}
function loadState(text) {
  const state = (typeof text === 'string') ? JSON.parse(text) : text;
  Blockly.serialization.workspaces.load(state, workspace);
}
function getProjects() {
  try { return JSON.parse(localStorage.getItem(PROJECTS_KEY) || '{}'); }
  catch (e) { return {}; }
}
function setProjects(obj) { localStorage.setItem(PROJECTS_KEY, JSON.stringify(obj)); }

// Beim Start: zuletzt bearbeiteten Stand automatisch wiederherstellen
try {
  const auto = localStorage.getItem(AUTOSAVE_KEY);
  if (auto) loadState(auto);
} catch (e) { /* beschädigter Stand -> ignorieren */ }

// Nach jeder Änderung: Code aktualisieren + automatisch sichern
workspace.addChangeListener(function () {
  refreshCodeFromBlocks();
  try { localStorage.setItem(AUTOSAVE_KEY, saveState()); } catch (e) {}
});
refreshCodeFromBlocks();

// Umschalten zwischen "aus Blöcken" und "manuell bearbeiten"
btnEdit.addEventListener('click', () => {
  if (!manualMode) {
    manualMode = true;
    codeEl.removeAttribute('readonly');
    codeEl.focus();
    btnEdit.textContent = '🔗 aus Blöcken';
    setStatus('Manueller Modus – Blöcke überschreiben den Code nicht mehr');
  } else {
    if (!confirm('Zurück zu den Blöcken? Deine manuellen Änderungen am Code gehen verloren.')) return;
    manualMode = false;
    codeEl.setAttribute('readonly', '');
    btnEdit.textContent = '✏️ bearbeiten';
    refreshCodeFromBlocks();
    setStatus('Bereit');
  }
});

function setStatus(t) { statusEl.textContent = t; }

function logLine(text, cls) {
  const span = document.createElement('span');
  if (cls) span.className = cls;
  span.textContent = text;
  consoleEl.appendChild(span);
  consoleEl.scrollTop = consoleEl.scrollHeight;
}

document.getElementById('btnClear').addEventListener('click', () => { consoleEl.textContent = ''; });

// ── Ausführen ────────────────────────────────────────────────────────────
async function runProgram() {
  const code = codeEl.value;
  if (!code.trim()) { setStatus('Kein Code vorhanden'); return; }
  setStatus('Übertrage …');
  consoleEl.textContent = '';
  outputCursor = 0;
  try {
    const res = await fetch('/api/run', {
      method: 'POST',
      headers: { 'Content-Type': 'text/plain' },
      body: code
    });
    if (res.ok) {
      setStatus('Läuft auf dem ESP32 …');
      logLine('▶ Programm gestartet\n', 'sys');
      startPolling();
    } else {
      const msg = await res.text();
      setStatus('Fehler beim Übertragen');
      logLine('✗ ' + msg + '\n', 'err');
    }
  } catch (e) {
    setStatus('Board nicht erreichbar');
    logLine('✗ Board nicht erreichbar (' + e + ')\n', 'err');
  }
}

// ── Stopp ────────────────────────────────────────────────────────────────
async function stopProgram() {
  stopPolling();
  setStatus('Stoppe …');
  try {
    await fetch('/api/stop', { method: 'POST' });
    setStatus('Gestoppt – Board startet neu');
    logLine('■ gestoppt\n', 'sys');
  } catch (e) {
    setStatus('Board nicht erreichbar');
  }
}

// ── Konsolen-Ausgabe pollen ─────────────────────────────────────────────
function startPolling() {
  stopPolling();
  pollTimer = setInterval(fetchOutput, 600);
}
function stopPolling() {
  if (pollTimer) { clearInterval(pollTimer); pollTimer = null; }
}
async function fetchOutput() {
  try {
    const res = await fetch('/api/output?since=' + outputCursor);
    if (!res.ok) return;
    const data = await res.json();   // { lines: [...], next: N, running: bool }
    if (Array.isArray(data.lines)) {
      for (const line of data.lines) {
        const isErr = line.indexOf('Traceback') === 0 || line.indexOf('Error') >= 0;
        logLine(line, isErr ? 'err' : null);
      }
    }
    if (typeof data.next === 'number') outputCursor = data.next;
    if (!data.running) {
      stopPolling();
      setStatus('Programm beendet');
      logLine('◼ Programm beendet\n', 'sys');
    }
  } catch (e) {
    // Board evtl. beim Neustart – Polling ruhig weiterlaufen lassen
  }
}

document.getElementById('btnRun').addEventListener('click', runProgram);
document.getElementById('btnStop').addEventListener('click', stopProgram);

// ── Projekte: Speichern / Laden / Löschen / Datei-Export-Import ───────────
const modal    = document.getElementById('projModal');
const projList = document.getElementById('projList');
const fileInput = document.getElementById('fileInput');
let lastName = '';

document.getElementById('btnSave').addEventListener('click', () => {
  const name = (prompt('Projektname zum Speichern:', lastName) || '').trim();
  if (!name) return;
  const projects = getProjects();
  if (projects[name] && !confirm('„' + name + '“ überschreiben?')) return;
  projects[name] = saveState();
  setProjects(projects);
  lastName = name;
  setStatus('Gespeichert: ' + name);
});

document.getElementById('btnProjects').addEventListener('click', () => {
  renderProjects();
  modal.hidden = false;
});
document.getElementById('projClose').addEventListener('click', () => { modal.hidden = true; });
modal.addEventListener('click', (e) => { if (e.target === modal) modal.hidden = true; });

function renderProjects() {
  const projects = getProjects();
  const names = Object.keys(projects).sort();
  projList.innerHTML = '';
  if (!names.length) {
    const li = document.createElement('li');
    li.innerHTML = '<span class="empty">Noch keine Projekte gespeichert.</span>';
    projList.appendChild(li);
    return;
  }
  for (const name of names) {
    const li = document.createElement('li');
    const label = document.createElement('span');
    label.className = 'pname';
    label.textContent = name;
    const load = document.createElement('button');
    load.className = 'load'; load.textContent = 'Laden';
    load.addEventListener('click', () => {
      try { loadState(projects[name]); lastName = name; modal.hidden = true; setStatus('Geladen: ' + name); }
      catch (e) { alert('Konnte „' + name + '“ nicht laden.'); }
    });
    const del = document.createElement('button');
    del.className = 'del'; del.textContent = '🗑';
    del.addEventListener('click', () => {
      if (!confirm('„' + name + '“ löschen?')) return;
      const p = getProjects(); delete p[name]; setProjects(p); renderProjects();
    });
    li.appendChild(label); li.appendChild(load); li.appendChild(del);
    projList.appendChild(li);
  }
}

// Als Datei sichern (herunterladen) – echtes, geräteübergreifendes Backup
document.getElementById('projExport').addEventListener('click', () => {
  const blob = new Blob([saveState()], { type: 'application/json' });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = (lastName || 'projekt') + '.blocks';
  document.body.appendChild(a); a.click(); a.remove();
  URL.revokeObjectURL(url);
});

// Datei laden (importieren)
document.getElementById('projImportBtn').addEventListener('click', () => fileInput.click());
fileInput.addEventListener('change', () => {
  const file = fileInput.files && fileInput.files[0];
  if (!file) return;
  const reader = new FileReader();
  reader.onload = () => {
    try { loadState(reader.result); modal.hidden = true; setStatus('Datei geladen: ' + file.name); }
    catch (e) { alert('Datei konnte nicht gelesen werden.'); }
  };
  reader.readAsText(file);
  fileInput.value = '';
});
