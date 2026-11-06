// Background service worker for Job Co-Pilot Extension

// Configure side panel to open on toolbar icon click
chrome.sidePanel
  .setPanelBehavior({ openPanelOnActionClick: true })
  .catch((error) => console.error("Error setting side panel behavior:", error));

// Open side panel on action button click as a safety fallback
chrome.action.onClicked.addListener(async (tab) => {
  if (!tab || !tab.id) return;
  if (tab.url && tab.url.startsWith("chrome://")) {
    chrome.tabs.create({ url: "http://127.0.0.1:8000/test" });
    return;
  }
  try {
    await chrome.sidePanel.open({ windowId: tab.windowId });
  } catch (e) {
    chrome.tabs.create({ url: chrome.runtime.getURL("sidepanel/index.html") });
  }
});

// Tab scan cache: tabId -> { [frameId]: scanPayload }
const tabScans = {};

chrome.tabs.onRemoved.addListener((tabId) => {
  delete tabScans[tabId];
});

chrome.tabs.onUpdated.addListener((tabId, changeInfo) => {
  if (changeInfo.status === "loading") {
    delete tabScans[tabId];
  }
});

// Central message broker between content scripts and local server
chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {
  if (request.action === "PAGE_FIELDS_DETECTED" && sender.tab) {
    const tabId = sender.tab.id;
    const frameId = sender.frameId || 0;
    if (!tabScans[tabId]) tabScans[tabId] = {};
    tabScans[tabId][frameId] = request.payload;
    sendResponse({ status: "cached" });
    return true;
  }

  if (request.action === "GET_CACHED_TAB_SCAN") {
    const tabId = request.tabId;
    const framesMap = tabScans[tabId] || {};
    let allFields = [];
    let bestTitle = "";
    for (const [frameId, frameScan] of Object.entries(framesMap)) {
      if (frameScan && frameScan.fields && frameScan.fields.length > 0) {
        frameScan.fields.forEach((f) => {
          f._frameId = Number(frameId);
        });
        allFields.push(...frameScan.fields);
        if (frameScan.title && !bestTitle) bestTitle = frameScan.title;
      }
    }
    sendResponse({ fields: allFields, title: bestTitle });
    return true;
  }
  if (request.action === "OPEN_SIDE_PANEL" && sender.tab) {
    chrome.sidePanel.open({ windowId: sender.tab.windowId }).catch(() => {
      chrome.tabs.create({ url: chrome.runtime.getURL("sidepanel/index.html") });
    });
    sendResponse({ success: true });
    return true;
  }

  // Safe background fetch for resume base64 (bypasses Mixed Content / HTTPS restrictions)
  if (request.action === "GET_RESUME_BASE64") {
    fetch("http://127.0.0.1:8000/api/resume-base64")
      .then((r) => r.json())
      .then((data) => sendResponse(data))
      .catch((err) => {
        console.error("Background failed to fetch resume:", err);
        sendResponse({ success: false, error: err.message });
      });
    return true; // Keep message channel open for async response
  }

  // Safe background fetch for field matching (bypasses Mixed Content / HTTPS restrictions)
  if (request.action === "MATCH_FIELDS") {
    fetch("http://127.0.0.1:8000/api/match-fields", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(request.payload || {})
    })
      .then((r) => r.json())
      .then((data) => sendResponse(data))
      .catch((err) => {
        console.error("Background failed to match fields:", err);
        sendResponse({ success: false, error: err.message });
      });
    return true; // Keep message channel open for async response
  }

  // Send diagnostic log to local Python server for real-time terminal monitoring
  if (request.action === "SEND_LOG") {
    fetch("http://127.0.0.1:8000/api/test-log", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(request.payload || {})
    }).catch(() => {});
    sendResponse({ status: "ok" });
    return true;
  }

  return true;
});

chrome.runtime.onInstalled.addListener(() => {
  console.log("Job Co-Pilot Extension installed.");
});
