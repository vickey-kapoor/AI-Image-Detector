/**
 * Background service worker for AI Image Detector extension.
 * Handles context menus and message passing between components.
 */

const DEFAULT_BACKEND_URL = 'http://localhost:8000';

// Store recent detections
let recentDetections = [];
const MAX_RECENT_DETECTIONS = 50;

// Initialize extension
chrome.runtime.onInstalled.addListener(async (details) => {
  console.log('AI Image Detector installed:', details.reason);

  // Set default settings
  const defaults = {
    backendUrl: DEFAULT_BACKEND_URL,
    apiKey: '',
    autoScan: true,
    scanMinImageSize: 100,
    showOverlays: true
  };

  const existing = await chrome.storage.sync.get(Object.keys(defaults));
  const toSet = {};

  for (const [key, value] of Object.entries(defaults)) {
    if (existing[key] === undefined) {
      toSet[key] = value;
    }
  }

  if (Object.keys(toSet).length > 0) {
    await chrome.storage.sync.set(toSet);
  }

  // Create context menu
  createContextMenu();
});

// Create context menu for analyzing images
function createContextMenu() {
  chrome.contextMenus.create({
    id: 'analyzeImage',
    title: 'Analyze this image for AI',
    contexts: ['image']
  });
}

// Handle context menu clicks
chrome.contextMenus.onClicked.addListener(async (info, tab) => {
  if (info.menuItemId === 'analyzeImage' && info.srcUrl) {
    try {
      // Send message to content script to analyze this specific image
      await chrome.tabs.sendMessage(tab.id, {
        action: 'analyzeImage',
        imageUrl: info.srcUrl,
        pageUrl: info.pageUrl
      });
    } catch (error) {
      console.error('Failed to send analyze message:', error);
    }
  }
});

// Handle messages from content scripts and popup
chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
  handleMessage(message, sender).then(sendResponse);
  return true; // Keep channel open for async response
});

async function handleMessage(message, sender) {
  switch (message.action) {
    case 'getSettings':
      return chrome.storage.sync.get([
        'backendUrl',
        'apiKey',
        'autoScan',
        'scanMinImageSize',
        'showOverlays'
      ]);

    case 'saveSettings':
      await chrome.storage.sync.set(message.settings);
      return { success: true };

    case 'checkHealth':
      return checkBackendHealth();

    case 'getStats':
      return getBackendStats();

    case 'reportDetection':
      addDetection(message.detection, sender.tab);
      return { success: true };

    case 'getRecentDetections':
      return { detections: recentDetections };

    case 'clearDetections':
      recentDetections = [];
      return { success: true };

    default:
      console.warn('Unknown message action:', message.action);
      return { error: 'Unknown action' };
  }
}

async function getBackendUrl() {
  const result = await chrome.storage.sync.get(['backendUrl']);
  return result.backendUrl || DEFAULT_BACKEND_URL;
}

async function checkBackendHealth() {
  try {
    const backendUrl = await getBackendUrl();
    const response = await fetch(`${backendUrl}/health`);

    if (!response.ok) {
      throw new Error(`HTTP ${response.status}`);
    }

    return response.json();
  } catch (error) {
    return {
      status: 'offline',
      model_loaded: false,
      device: 'unknown',
      version: 'unknown',
      error: error.message
    };
  }
}

async function getBackendStats() {
  try {
    const backendUrl = await getBackendUrl();
    const response = await fetch(`${backendUrl}/stats`);

    if (!response.ok) {
      throw new Error(`HTTP ${response.status}`);
    }

    return response.json();
  } catch (error) {
    return {
      total_analyses: 0,
      ai_detections: 0,
      cache_hits: 0,
      cache_hit_rate: 0,
      error: error.message
    };
  }
}

function addDetection(detection, tab) {
  const entry = {
    ...detection,
    tabId: tab?.id,
    tabTitle: tab?.title,
    tabUrl: tab?.url,
    timestamp: new Date().toISOString()
  };

  recentDetections.unshift(entry);

  // Limit stored detections
  if (recentDetections.length > MAX_RECENT_DETECTIONS) {
    recentDetections = recentDetections.slice(0, MAX_RECENT_DETECTIONS);
  }
}

// Re-create context menu when service worker wakes up
chrome.runtime.onStartup.addListener(() => {
  createContextMenu();
});
