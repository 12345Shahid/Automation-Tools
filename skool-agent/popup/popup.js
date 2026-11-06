// Popup Controller for Skool Outreach Assistant

let currentConfig = {};
let isRunning = false;
let isPaused = false;

// UI Elements
const msgTemplate = document.getElementById("msg-template");
const btnPreviewSpintax = document.getElementById("btn-preview-spintax");
const previewBox = document.getElementById("spintax-preview-box");
const previewText = document.getElementById("spintax-preview-text");

const minDelayInput = document.getElementById("setting-min-delay");
const maxDelayInput = document.getElementById("setting-max-delay");
const limitInput = document.getElementById("setting-limit");
const skipAdminsCheck = document.getElementById("setting-skip-admins");
const dryRunCheck = document.getElementById("setting-dry-run");

const statTotal = document.getElementById("stat-total");
const statEligible = document.getElementById("stat-eligible");
const statAdmins = document.getElementById("stat-admins");
const statHistory = document.getElementById("stat-history");
const statusPill = document.getElementById("status-pill");

const btnStart = document.getElementById("btn-start");
const btnPause = document.getElementById("btn-pause");
const btnStop = document.getElementById("btn-stop");
const runningControls = document.getElementById("running-controls");
const btnClearHistory = document.getElementById("btn-clear-history");
const toast = document.getElementById("toast");

document.addEventListener("DOMContentLoaded", async () => {
  await loadConfig();
  setupEventListeners();
  scanActiveTabMembers();
});

// Load stored settings
async function loadConfig() {
  const data = await chrome.storage.local.get("skoolConfig");
  if (data.skoolConfig) {
    currentConfig = data.skoolConfig;
    msgTemplate.value = currentConfig.template || "{Assalamu Alaikum|Salam} {first_name}! How are you brother?";
    minDelayInput.value = currentConfig.minDelay || 45;
    maxDelayInput.value = currentConfig.maxDelay || 90;
    limitInput.value = currentConfig.dailyLimit || 25;
    skipAdminsCheck.checked = currentConfig.skipAdmins !== false;
    dryRunCheck.checked = !!currentConfig.dryRun;

    const historyCount = Object.keys(currentConfig.messagedUsers || {}).length;
    statHistory.innerText = historyCount;
  }
}

// Auto-save settings on change
function saveConfig() {
  currentConfig.template = msgTemplate.value;
  currentConfig.minDelay = parseInt(minDelayInput.value) || 45;
  currentConfig.maxDelay = parseInt(maxDelayInput.value) || 90;
  currentConfig.dailyLimit = parseInt(limitInput.value) || 25;
  currentConfig.skipAdmins = skipAdminsCheck.checked;
  currentConfig.dryRun = dryRunCheck.checked;

  chrome.storage.local.set({ skoolConfig: currentConfig });
}

function showToast(msg) {
  toast.innerText = msg;
  toast.classList.remove("hidden");
  setTimeout(() => toast.classList.add("hidden"), 2500);
}

// Spintax Preview Generator
function resolveSpintax(text) {
  const spintaxRegex = /\{([^{}]+)\}/g;
  let iterations = 0;
  while (spintaxRegex.test(text) && iterations < 10) {
    text = text.replace(spintaxRegex, (_, choices) => {
      const parts = choices.split("|");
      return parts[Math.floor(Math.random() * parts.length)];
    });
    iterations++;
  }
  return text;
}

btnPreviewSpintax.addEventListener("click", () => {
  let sample = msgTemplate.value;
  sample = sample.replace(/\{first_name\}/gi, "David");
  sample = sample.replace(/\{name\}/gi, "David Chen");
  sample = sample.replace(/\{username\}/gi, "david_chen");
  const variation = resolveSpintax(sample);

  previewText.innerText = variation;
  previewBox.classList.remove("hidden");
});

// Tag Pills (Insert at cursor position)
document.querySelectorAll(".tag-pill").forEach((pill) => {
  pill.addEventListener("click", () => {
    const tag = pill.getAttribute("data-tag");
    const start = msgTemplate.selectionStart;
    const end = msgTemplate.selectionEnd;
    const text = msgTemplate.value;
    msgTemplate.value = text.substring(0, start) + tag + text.substring(end);
    msgTemplate.selectionStart = msgTemplate.selectionEnd = start + tag.length;
    msgTemplate.focus();
    saveConfig();
  });
});

// Setup input listeners
function setupEventListeners() {
  [msgTemplate, minDelayInput, maxDelayInput, limitInput, skipAdminsCheck, dryRunCheck].forEach((el) => {
    el.addEventListener("input", saveConfig);
    el.addEventListener("change", saveConfig);
  });

  // Action buttons
  btnStart.addEventListener("click", async () => {
    saveConfig();
    const tab = await getActiveTab();
    if (tab?.id) {
      chrome.tabs.sendMessage(tab.id, { action: "START_CAMPAIGN" }, (res) => {
        if (chrome.runtime.lastError) {
          showToast("Please open a Skool Members page first!");
          return;
        }
        setRunningState(true, false);
        showToast("Campaign started!");
      });
    }
  });

  btnPause.addEventListener("click", async () => {
    const tab = await getActiveTab();
    if (tab?.id) {
      const action = isPaused ? "RESUME_CAMPAIGN" : "PAUSE_CAMPAIGN";
      chrome.tabs.sendMessage(tab.id, { action }, () => {
        setRunningState(true, !isPaused);
      });
    }
  });

  btnStop.addEventListener("click", async () => {
    const tab = await getActiveTab();
    if (tab?.id) {
      chrome.tabs.sendMessage(tab.id, { action: "STOP_CAMPAIGN" }, () => {
        setRunningState(false, false);
        showToast("Campaign stopped.");
      });
    }
  });

  btnClearHistory.addEventListener("click", () => {
    if (confirm("Reset messaged history? This will allow messaging all members again.")) {
      chrome.runtime.sendMessage({ action: "CLEAR_HISTORY" }, () => {
        statHistory.innerText = "0";
        showToast("Outreach history cleared!");
        scanActiveTabMembers();
      });
    }
  });
}

function setRunningState(running, paused) {
  isRunning = running;
  isPaused = paused;

  if (running) {
    btnStart.classList.add("hidden");
    runningControls.classList.remove("hidden");
    btnPause.innerText = paused ? "▶ Resume" : "⏸ Pause";
    statusPill.innerText = paused ? "Paused" : "Running";
    statusPill.className = paused ? "pill pill-paused" : "pill pill-running";
  } else {
    btnStart.classList.remove("hidden");
    runningControls.classList.add("hidden");
    statusPill.innerText = "Ready";
    statusPill.className = "pill pill-idle";
  }
}

// Live Page Scanner
async function scanActiveTabMembers() {
  const tab = await getActiveTab();
  if (!tab?.id) return;

  chrome.tabs.sendMessage(tab.id, { action: "SCAN_MEMBERS" }, (res) => {
    if (chrome.runtime.lastError || !res) return;

    statTotal.innerText = res.totalOnPage || 0;
    statEligible.innerText = res.eligibleCount || 0;
    statAdmins.innerText = res.adminCount || 0;
  });
}

async function getActiveTab() {
  let [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
  if (!tab || !tab.id) {
    const tabs = await chrome.tabs.query({ active: true, lastFocusedWindow: true });
    tab = tabs?.[0];
  }
  return tab;
}
