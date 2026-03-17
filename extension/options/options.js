/**
 * Options page script for AI Image Detector extension.
 */

const DEFAULT_SETTINGS = {
  backendUrl: 'http://localhost:8000',
  apiKey: '',
  autoScan: true,
  scanMinImageSize: 100,
  showOverlays: true
};

document.addEventListener('DOMContentLoaded', async () => {
  await loadSettings();

  document.getElementById('saveBtn').addEventListener('click', saveSettings);
  document.getElementById('resetBtn').addEventListener('click', resetSettings);
  document.getElementById('testConnection').addEventListener('click', testConnection);
});

async function loadSettings() {
  try {
    const settings = await chrome.storage.sync.get(Object.keys(DEFAULT_SETTINGS));

    document.getElementById('backendUrl').value =
      settings.backendUrl || DEFAULT_SETTINGS.backendUrl;
    document.getElementById('apiKey').value =
      settings.apiKey || DEFAULT_SETTINGS.apiKey;
    document.getElementById('autoScan').checked =
      settings.autoScan !== undefined ? settings.autoScan : DEFAULT_SETTINGS.autoScan;
    document.getElementById('scanMinImageSize').value =
      settings.scanMinImageSize || DEFAULT_SETTINGS.scanMinImageSize;
    document.getElementById('showOverlays').checked =
      settings.showOverlays !== undefined ? settings.showOverlays : DEFAULT_SETTINGS.showOverlays;
  } catch (error) {
    console.error('Failed to load settings:', error);
    showStatus('Failed to load settings', 'error');
  }
}

async function saveSettings() {
  const settings = {
    backendUrl: document.getElementById('backendUrl').value.trim() || DEFAULT_SETTINGS.backendUrl,
    apiKey: document.getElementById('apiKey').value.trim(),
    autoScan: document.getElementById('autoScan').checked,
    scanMinImageSize: parseInt(document.getElementById('scanMinImageSize').value) || DEFAULT_SETTINGS.scanMinImageSize,
    showOverlays: document.getElementById('showOverlays').checked
  };

  try {
    await chrome.storage.sync.set(settings);
    showStatus('Settings saved successfully!', 'success');

    // Notify content scripts of settings change
    const tabs = await chrome.tabs.query({});
    for (const tab of tabs) {
      try {
        await chrome.tabs.sendMessage(tab.id, { action: 'settingsUpdated' });
      } catch (e) {
        // Ignore errors for tabs without content script
      }
    }
  } catch (error) {
    console.error('Failed to save settings:', error);
    showStatus('Failed to save settings', 'error');
  }
}

async function resetSettings() {
  document.getElementById('backendUrl').value = DEFAULT_SETTINGS.backendUrl;
  document.getElementById('apiKey').value = DEFAULT_SETTINGS.apiKey;
  document.getElementById('autoScan').checked = DEFAULT_SETTINGS.autoScan;
  document.getElementById('scanMinImageSize').value = DEFAULT_SETTINGS.scanMinImageSize;
  document.getElementById('showOverlays').checked = DEFAULT_SETTINGS.showOverlays;

  await saveSettings();
}

async function testConnection() {
  const btn = document.getElementById('testConnection');
  const status = document.getElementById('connectionStatus');
  const backendUrl = document.getElementById('backendUrl').value.trim();

  btn.disabled = true;
  btn.textContent = 'Testing...';
  status.className = 'connection-status';
  status.textContent = 'Testing...';

  try {
    const response = await fetch(`${backendUrl}/health`, {
      method: 'GET',
      headers: { 'Accept': 'application/json' }
    });

    if (response.ok) {
      const health = await response.json();
      status.className = 'connection-status connected';
      status.textContent = `Connected (${health.device}, v${health.version})`;
    } else {
      throw new Error(`HTTP ${response.status}`);
    }
  } catch (error) {
    status.className = 'connection-status disconnected';
    status.textContent = `Failed: ${error.message}`;
  } finally {
    btn.disabled = false;
    btn.textContent = 'Test Connection';
  }
}

function showStatus(message, type) {
  const statusEl = document.getElementById('statusMessage');
  statusEl.textContent = message;
  statusEl.className = `status-message ${type}`;

  // Auto-hide success messages
  if (type === 'success') {
    setTimeout(() => {
      statusEl.className = 'status-message';
    }, 3000);
  }
}
