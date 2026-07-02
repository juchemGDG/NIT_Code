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
workspace.addChangeListener(refreshCodeFromBlocks);
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
