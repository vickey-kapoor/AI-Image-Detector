/**
 * API client for communicating with the AI Image Detector backend.
 */

const DEFAULT_BACKEND_URL = 'http://localhost:8000';

class AIDetectorAPI {
  constructor() {
    this.backendUrl = DEFAULT_BACKEND_URL;
    this.apiKey = '';
    this._loadSettings();
  }

  async _loadSettings() {
    try {
      const result = await chrome.storage.sync.get(['backendUrl', 'apiKey']);
      if (result.backendUrl) {
        this.backendUrl = result.backendUrl;
      }
      if (result.apiKey) {
        this.apiKey = result.apiKey;
      }
    } catch (error) {
      console.warn('Failed to load settings:', error);
    }
  }

  _getHeaders() {
    const headers = { 'Content-Type': 'application/json' };
    if (this.apiKey) {
      headers['X-API-Key'] = this.apiKey;
    }
    return headers;
  }

  /**
   * Convert an image URL to base64.
   * @param {string} imageUrl - URL of the image
   * @returns {Promise<string>} Base64-encoded image data
   */
  async imageUrlToBase64(imageUrl) {
    const response = await fetch(imageUrl);
    const blob = await response.blob();

    return new Promise((resolve, reject) => {
      const reader = new FileReader();
      reader.onloadend = () => {
        // Remove data URL prefix to get raw base64
        const base64 = reader.result.split(',')[1];
        resolve(base64);
      };
      reader.onerror = reject;
      reader.readAsDataURL(blob);
    });
  }

  /**
   * Analyze an image for AI generation detection.
   * @param {string} imageBase64 - Base64-encoded image data
   * @param {string} sourceUrl - URL of the page containing the image
   * @param {string} [imageUrl] - Optional URL of the image itself
   * @returns {Promise<Object>} Analysis result
   */
  async analyzeImage(imageBase64, sourceUrl, imageUrl = null) {
    const response = await fetch(`${this.backendUrl}/analyze`, {
      method: 'POST',
      headers: this._getHeaders(),
      body: JSON.stringify({
        image_base64: imageBase64,
        source_url: sourceUrl,
        image_url: imageUrl
      })
    });

    if (!response.ok) {
      if (response.status === 429) {
        throw new Error('Rate limit exceeded. Please wait before analyzing more images.');
      }
      throw new Error(`API error: ${response.status}`);
    }

    return response.json();
  }

  /**
   * Check backend health status.
   * @returns {Promise<Object>} Health status
   */
  async checkHealth() {
    try {
      const response = await fetch(`${this.backendUrl}/health`);
      if (!response.ok) {
        throw new Error(`Health check failed: ${response.status}`);
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

  /**
   * Get API statistics.
   * @returns {Promise<Object>} Statistics
   */
  async getStats() {
    const response = await fetch(`${this.backendUrl}/stats`);
    if (!response.ok) {
      throw new Error(`Stats request failed: ${response.status}`);
    }
    return response.json();
  }

  /**
   * Update the backend URL.
   * @param {string} url - New backend URL
   */
  setBackendUrl(url) {
    this.backendUrl = url;
  }

  setApiKey(key) {
    this.apiKey = key;
  }
}

// Create global instance
const aiDetectorAPI = new AIDetectorAPI();
