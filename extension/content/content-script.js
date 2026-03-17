/**
 * Content script for AI Image Detector.
 * Detects images on web pages and adds visual overlays showing AI detection results.
 */

(function() {
  'use strict';

  // Prevent multiple injections
  if (window.__aiDetectorInitialized) return;
  window.__aiDetectorInitialized = true;

  // Settings cache
  let settings = {
    backendUrl: 'http://localhost:8000',
    apiKey: '',
    autoScan: true,
    scanMinImageSize: 100,
    showOverlays: true
  };

  // Track analyzed images to avoid re-analysis
  const analyzedImages = new WeakSet();
  const analysisInProgress = new WeakSet();

  // Load settings
  async function loadSettings() {
    try {
      const result = await chrome.runtime.sendMessage({ action: 'getSettings' });
      settings = { ...settings, ...result };
    } catch (error) {
      console.warn('AI Detector: Failed to load settings:', error);
    }
  }

  /**
   * Convert image element to base64.
   */
  async function imageToBase64(img) {
    // Try to fetch the image directly for better quality
    if (img.src && img.src.startsWith('http')) {
      try {
        const response = await fetch(img.src);
        const blob = await response.blob();
        return new Promise((resolve, reject) => {
          const reader = new FileReader();
          reader.onloadend = () => resolve(reader.result.split(',')[1]);
          reader.onerror = reject;
          reader.readAsDataURL(blob);
        });
      } catch (error) {
        // Fall back to canvas method
      }
    }

    // Canvas fallback
    const canvas = document.createElement('canvas');
    canvas.width = img.naturalWidth || img.width;
    canvas.height = img.naturalHeight || img.height;
    const ctx = canvas.getContext('2d');
    ctx.drawImage(img, 0, 0);

    try {
      const dataUrl = canvas.toDataURL('image/png');
      return dataUrl.split(',')[1];
    } catch (error) {
      throw new Error('Failed to convert image to base64 (CORS restriction)');
    }
  }

  /**
   * Create overlay indicator for an image.
   */
  function createOverlay(img, result) {
    // Remove existing overlay if any
    const existingOverlay = img.parentElement?.querySelector('.ai-detector-overlay');
    if (existingOverlay) {
      existingOverlay.remove();
    }

    if (!settings.showOverlays) return;

    // Ensure parent has relative positioning
    const parent = img.parentElement;
    if (parent && getComputedStyle(parent).position === 'static') {
      parent.style.position = 'relative';
    }

    // Create overlay element
    const overlay = document.createElement('div');
    overlay.className = 'ai-detector-overlay';

    // Determine indicator based on result
    let indicator, bgColor, title;
    if (result.is_ai) {
      indicator = '\u2717'; // X mark
      bgColor = 'rgba(220, 53, 69, 0.9)'; // Red
      title = `AI Generated (${(result.confidence * 100).toFixed(0)}% confidence)`;
    } else if (result.verdict === 'Uncertain') {
      indicator = '?';
      bgColor = 'rgba(255, 193, 7, 0.9)'; // Yellow
      title = `Uncertain (${(result.confidence * 100).toFixed(0)}% confidence)`;
    } else {
      indicator = '\u2713'; // Checkmark
      bgColor = 'rgba(40, 167, 69, 0.9)'; // Green
      title = `Likely Real (${(result.confidence * 100).toFixed(0)}% confidence)`;
    }

    overlay.innerHTML = indicator;
    overlay.style.cssText = `
      position: absolute;
      top: 8px;
      right: 8px;
      width: 28px;
      height: 28px;
      background: ${bgColor};
      color: white;
      border-radius: 50%;
      display: flex;
      align-items: center;
      justify-content: center;
      font-size: 16px;
      font-weight: bold;
      z-index: 10000;
      cursor: pointer;
      box-shadow: 0 2px 6px rgba(0,0,0,0.3);
      font-family: Arial, sans-serif;
      pointer-events: auto;
    `;
    overlay.title = title;

    // Add click handler to show details
    overlay.addEventListener('click', (e) => {
      e.stopPropagation();
      e.preventDefault();
      showResultPopup(img, result);
    });

    parent.appendChild(overlay);
  }

  /**
   * Show detailed result popup.
   */
  function showResultPopup(img, result) {
    // Remove existing popup
    const existingPopup = document.querySelector('.ai-detector-popup');
    if (existingPopup) {
      existingPopup.remove();
    }

    const popup = document.createElement('div');
    popup.className = 'ai-detector-popup';
    popup.innerHTML = `
      <div class="ai-detector-popup-header">
        <strong>AI Image Analysis</strong>
        <button class="ai-detector-popup-close">\u00d7</button>
      </div>
      <div class="ai-detector-popup-content">
        <div class="ai-detector-popup-row">
          <span>Verdict:</span>
          <span class="${result.is_ai ? 'ai-detected' : 'real-detected'}">${result.verdict}</span>
        </div>
        <div class="ai-detector-popup-row">
          <span>Confidence:</span>
          <span>${(result.confidence * 100).toFixed(1)}%</span>
        </div>
        <div class="ai-detector-popup-row">
          <span>AI Probability:</span>
          <span>${(result.fake_probability * 100).toFixed(1)}%</span>
        </div>
        <div class="ai-detector-popup-row">
          <span>Real Probability:</span>
          <span>${(result.real_probability * 100).toFixed(1)}%</span>
        </div>
        ${result.cached ? '<div class="ai-detector-popup-cached">Cached result</div>' : ''}
      </div>
    `;

    // Position popup near the image
    const rect = img.getBoundingClientRect();
    popup.style.cssText = `
      position: fixed;
      top: ${Math.min(rect.top + 40, window.innerHeight - 200)}px;
      left: ${Math.min(rect.right + 10, window.innerWidth - 220)}px;
      width: 200px;
      background: white;
      border-radius: 8px;
      box-shadow: 0 4px 20px rgba(0,0,0,0.2);
      z-index: 10001;
      font-family: Arial, sans-serif;
      font-size: 13px;
    `;

    document.body.appendChild(popup);

    // Close handlers
    popup.querySelector('.ai-detector-popup-close').addEventListener('click', () => {
      popup.remove();
    });

    document.addEventListener('click', function closePopup(e) {
      if (!popup.contains(e.target)) {
        popup.remove();
        document.removeEventListener('click', closePopup);
      }
    }, { once: false });
  }

  /**
   * Analyze a single image.
   */
  async function analyzeImage(img, imageUrl = null) {
    if (analyzedImages.has(img) || analysisInProgress.has(img)) {
      return;
    }

    // Check minimum size
    const width = img.naturalWidth || img.width;
    const height = img.naturalHeight || img.height;
    if (width < settings.scanMinImageSize || height < settings.scanMinImageSize) {
      return;
    }

    analysisInProgress.add(img);

    try {
      const base64 = await imageToBase64(img);

      const headers = { 'Content-Type': 'application/json' };
      if (settings.apiKey) {
        headers['X-API-Key'] = settings.apiKey;
      }

      const response = await fetch(`${settings.backendUrl}/analyze`, {
        method: 'POST',
        headers,
        body: JSON.stringify({
          image_base64: base64,
          source_url: window.location.href,
          image_url: imageUrl || img.src
        })
      });

      if (!response.ok) {
        if (response.status === 429) {
          console.warn('AI Detector: Rate limited');
          return;
        }
        throw new Error(`API error: ${response.status}`);
      }

      const result = await response.json();

      analyzedImages.add(img);
      createOverlay(img, result);

      // Report detection to background
      chrome.runtime.sendMessage({
        action: 'reportDetection',
        detection: {
          imageUrl: imageUrl || img.src,
          result: result
        }
      });

    } catch (error) {
      console.warn('AI Detector: Analysis failed:', error.message);
    } finally {
      analysisInProgress.delete(img);
    }
  }

  /**
   * Scan page for images to analyze.
   */
  function scanImages() {
    if (!settings.autoScan) return;

    const images = document.querySelectorAll('img');
    images.forEach(img => {
      // Skip if already analyzed or too small
      if (analyzedImages.has(img) || analysisInProgress.has(img)) return;

      // Check if image is loaded
      if (img.complete && img.naturalWidth > 0) {
        analyzeImage(img);
      } else {
        img.addEventListener('load', () => analyzeImage(img), { once: true });
      }
    });
  }

  /**
   * Set up MutationObserver for dynamic images.
   */
  function observeDOM() {
    const observer = new MutationObserver((mutations) => {
      for (const mutation of mutations) {
        for (const node of mutation.addedNodes) {
          if (node.nodeType !== Node.ELEMENT_NODE) continue;

          // Check if the added node is an image
          if (node.tagName === 'IMG') {
            if (node.complete && node.naturalWidth > 0) {
              analyzeImage(node);
            } else {
              node.addEventListener('load', () => analyzeImage(node), { once: true });
            }
          }

          // Check for images within added nodes
          const images = node.querySelectorAll?.('img') || [];
          images.forEach(img => {
            if (img.complete && img.naturalWidth > 0) {
              analyzeImage(img);
            } else {
              img.addEventListener('load', () => analyzeImage(img), { once: true });
            }
          });
        }
      }
    });

    observer.observe(document.body, {
      childList: true,
      subtree: true
    });
  }

  // Listen for messages from background/popup
  chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
    if (message.action === 'analyzeImage' && message.imageUrl) {
      const img = document.querySelector(`img[src="${message.imageUrl}"]`);
      if (img) {
        analyzedImages.delete(img);
        analyzeImage(img, message.imageUrl);
      }
      sendResponse({ success: true });
    } else if (message.action === 'rescan') {
      // Clear analyzed images and rescan
      scanImages();
      sendResponse({ success: true });
    } else if (message.action === 'settingsUpdated') {
      loadSettings();
      sendResponse({ success: true });
    }
    return true;
  });

  // Initialize
  async function init() {
    await loadSettings();

    if (document.readyState === 'loading') {
      document.addEventListener('DOMContentLoaded', () => {
        scanImages();
        observeDOM();
      });
    } else {
      scanImages();
      observeDOM();
    }
  }

  init();
})();
