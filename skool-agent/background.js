// Background Service Worker for Skool Outreach Assistant

// Default configuration settings
const DEFAULT_CONFIG = {
  template: "{Assalamu Alaikum|Salam} {first_name}! How are you brother?",
  minDelay: 45,
  maxDelay: 90,
  dailyLimit: 25,
  skipAdmins: true,
  dryRun: false,
  messagedUsers: {} // userId -> { name, username, date }
};

// Initialize default storage on install
chrome.runtime.onInstalled.addListener(async () => {
  const current = await chrome.storage.local.get("skoolConfig");
  if (!current.skoolConfig) {
    await chrome.storage.local.set({ skoolConfig: DEFAULT_CONFIG });
  }
  console.log("Skool Outreach Assistant installed.");
});

// Message hub between popup and content scripts
chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {
  if (request.action === "GET_CAMPAIGN_STATE") {
    chrome.storage.local.get(["skoolConfig", "skoolState"], (res) => {
      sendResponse({
        config: res.skoolConfig || DEFAULT_CONFIG,
        state: res.skoolState || { isRunning: false, isPaused: false, countSent: 0 }
      });
    });
    return true;
  }

  if (request.action === "RECORD_MESSAGED_USER") {
    chrome.storage.local.get("skoolConfig", (res) => {
      const config = res.skoolConfig || DEFAULT_CONFIG;
      config.messagedUsers = config.messagedUsers || {};
      config.messagedUsers[request.user.id] = {
        name: request.user.name,
        username: request.user.username,
        date: new Date().toISOString()
      };
      chrome.storage.local.set({ skoolConfig: config }, () => {
        sendResponse({ success: true, total: Object.keys(config.messagedUsers).length });
      });
    });
    return true;
  }

  if (request.action === "CLEAR_HISTORY") {
    chrome.storage.local.get("skoolConfig", (res) => {
      const config = res.skoolConfig || DEFAULT_CONFIG;
      config.messagedUsers = {};
      chrome.storage.local.set({ skoolConfig: config }, () => {
        sendResponse({ success: true });
      });
    });
    return true;
  }

  return true;
});
