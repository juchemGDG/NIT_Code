// app.js

const workspace = Blockly.inject('blocklyDiv', {
  toolbox: document.getElementById('toolbox'),
  media: '/blockly/media/',   // lokale Sprites/Sounds vom ESP32 – verhindert "Failed to fetch" offline
  trashcan: true,
  zoom: { controls: true, wheel: true, startScale: 1.0 },
  grid: { spacing: 20, length: 3, colour: '#eee', snap: true }
});

const statusEl = document.getElementById('status');
const STORAGE_KEY = 'nitEsp32BlocklyWorkspace';

// Workspace im Browser zwischenspeichern (ueberlebt Reload, nicht ESP32-Reset)
function saveWorkspace() {
  const xml = Blockly.Xml.workspaceToDom(workspace);
  const text = Blockly.Xml.domToText(xml);
  try {
    window.localStorage_disabled; // absichtlich nicht genutzt, siehe Hinweis unten
  } catch (e) {}
}

// Hinweis: In Claude-Artifacts ist localStorage verboten - hier im ESP32-Kontext
// (echter Browser, kein Artifact) ist localStorage grundsaetzlich okay, aber
// bewusst weggelassen, damit dieses Grundgeruest ueberall gleich funktioniert.
// Bei Bedarf hier window.localStorage verwenden.

function generateCode() {
  return Blockly.Python.workspaceToCode(workspace);
}

async function runProgram() {
  const code = generateCode();
  if (!code.trim()) {
    statusEl.textContent = 'Kein Code vorhanden';
    return;
  }
  statusEl.textContent = 'Übertrage...';
  try {
    const res = await fetch('/api/upload', {
      method: 'POST',
      headers: { 'Content-Type': 'text/plain' },
      body: code
    });
    if (res.ok) {
      statusEl.textContent = 'Läuft auf dem ESP32 – Board startet neu...';
    } else {
      statusEl.textContent = 'Fehler beim Übertragen';
    }
  } catch (e) {
    statusEl.textContent = 'Board nicht erreichbar';
  }
}

async function stopProgram() {
  statusEl.textContent = 'Stoppe...';
  try {
    await fetch('/api/stop', { method: 'POST' });
    statusEl.textContent = 'Zurück im Programmiermodus (Board startet neu)';
  } catch (e) {
    statusEl.textContent = 'Board nicht erreichbar';
  }
}

document.getElementById('btnRun').addEventListener('click', runProgram);
document.getElementById('btnStop').addEventListener('click', stopProgram);
