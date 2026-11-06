// Side panel controller for Job Co-Pilot Extension

const BRIDGE_URL = "http://127.0.0.1:8000";

let detectedFields = [];
let currentMatches = {};
let candidateProfile = {
  personal: {
    first_name: "Jane",
    last_name: "Doe",
    full_name: "Jane Doe",
    email: "jane.doe@example.com",
    phone: "+1 555-019-2834"
  },
  socials: {
    linkedin: "https://www.linkedin.com/in/janedoe-sample",
    github: "https://github.com/janedoe-sample"
  },
  experience_and_preferences: {
    desired_salary_usd: "165,000",
    notice_period: "2 weeks"
  },
  work_authorization: {
    requires_sponsorship: "No"
  }
};

// UI Elements
const tabBtns = document.querySelectorAll(".tab-btn");
const tabContents = document.querySelectorAll(".tab-content");
const backendStatus = document.getElementById("backend-status");
const btnScan = document.getElementById("btn-scan");
const btnAutofill = document.getElementById("btn-autofill");
const pageTitleText = document.getElementById("page-title");
const fieldCountBadge = document.getElementById("field-count-badge");
const fieldsList = document.getElementById("fields-list");
const matchStatus = document.getElementById("match-status");

const settingLlmMode = document.getElementById("setting-llm-mode");
const directApiGroup = document.getElementById("direct-api-group");
const settingApiKey = document.getElementById("setting-api-key");
const btnSaveKey = document.getElementById("btn-save-key");

const btnSyncProfile = document.getElementById("btn-sync-profile");
const btnSaveProfile = document.getElementById("btn-save-profile");
const btnSearchJobs = document.getElementById("btn-search-jobs");
const searchResults = document.getElementById("search-results");

// Initialize
// Helper: get the current active browser tab reliably
async function getActiveTab() {
  let [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
  if (!tab || !tab.id) {
    const tabs = await chrome.tabs.query({ active: true, lastFocusedWindow: true });
    tab = tabs?.[0];
  }
  return tab;
}

// Initialize
document.addEventListener("DOMContentLoaded", async () => {
  setupTabs();
  loadSavedSettings();
  checkBackendHealth();
  setInterval(checkBackendHealth, 10000);

  // Automatically scan the active tab right away when the side panel is opened!
  setTimeout(() => {
    scanActiveTab();
  }, 100);
});

// Auto-scan whenever user switches tabs or a tab finishes loading
chrome.tabs.onActivated.addListener(() => {
  scanActiveTab();
});

chrome.tabs.onUpdated.addListener((tabId, changeInfo, tab) => {
  if (changeInfo.status === "complete" && tab.active) {
    scanActiveTab();
  }
});

// Listen for live proactive field broadcasts from content scripts in any frame
chrome.runtime.onMessage.addListener((msg, sender) => {
  if (msg.action === "PAGE_FIELDS_DETECTED" && msg.payload && msg.payload.fields?.length > 0) {
    getActiveTab().then((currentTab) => {
      if (currentTab && sender.tab && currentTab.id === sender.tab.id) {
        const frameFields = msg.payload.fields.map((f) => ({ ...f, _frameId: sender.frameId || 0 }));
        handleScanSuccess(frameFields, msg.payload.title || currentTab.title);
      }
    });
  }
});

// Tab Switching
function setupTabs() {
  tabBtns.forEach((btn) => {
    btn.addEventListener("click", () => {
      tabBtns.forEach((b) => b.classList.remove("active"));
      tabContents.forEach((c) => c.classList.remove("active"));

      btn.classList.add("active");
      const target = document.getElementById(btn.getAttribute("data-tab"));
      if (target) target.classList.add("active");
    });
  });
}

function showToast(msg) {
  const toast = document.getElementById("toast");
  toast.innerText = msg;
  toast.classList.remove("hidden");
  setTimeout(() => toast.classList.add("hidden"), 3000);
}

// Backend Health
async function checkBackendHealth() {
  try {
    const res = await fetch(`${BRIDGE_URL}/api/health`, { method: "GET" });
    if (res.ok) {
      backendStatus.innerText = "Bridge: Online";
      backendStatus.className = "status-badge status-online";
      return true;
    }
  } catch (e) {
    // offline
  }
  backendStatus.innerText = "Bridge: Offline";
  backendStatus.className = "status-badge status-offline";
  return false;
}

// Settings & Profile
async function loadSavedSettings() {
  const data = await chrome.storage.local.get(["llmMode", "apiKey", "candidateProfile"]);
  if (data.llmMode) settingLlmMode.value = data.llmMode;
  if (data.apiKey) settingApiKey.value = data.apiKey;
  if (data.candidateProfile) {
    candidateProfile = data.candidateProfile;
    populateProfileForm(candidateProfile);
  } else {
    syncProfileFromBackend();
  }

  handleLlmModeChange();
}

settingLlmMode.addEventListener("change", handleLlmModeChange);

function handleLlmModeChange() {
  const mode = settingLlmMode.value;
  chrome.storage.local.set({ llmMode: mode });
  if (mode === "bridge") {
    directApiGroup.style.display = "none";
  } else {
    directApiGroup.style.display = "flex";
  }
}

btnSaveKey.addEventListener("click", () => {
  const key = settingApiKey.value.trim();
  chrome.storage.local.set({ apiKey: key }, () => {
    showToast("API key saved!");
  });
});

async function syncProfileFromBackend() {
  try {
    const res = await fetch(`${BRIDGE_URL}/api/profile`);
    if (res.ok) {
      const data = await res.json();
      if (data.profile) {
        candidateProfile = data.profile;
        populateProfileForm(candidateProfile);
        chrome.storage.local.set({ candidateProfile: candidateProfile });
        showToast("Profile synced from local backend!");
      }
    }
  } catch (e) {
    console.log("Could not sync from backend, using stored profile.");
  }
}

btnSyncProfile.addEventListener("click", syncProfileFromBackend);

function populateProfileForm(p) {
  document.getElementById("prof-name").value = p.personal?.full_name || `${p.personal?.first_name || ''} ${p.personal?.last_name || ''}`.trim();
  document.getElementById("prof-email").value = p.personal?.email || "";
  document.getElementById("prof-phone").value = p.personal?.phone || "";
  document.getElementById("prof-linkedin").value = p.socials?.linkedin || "";
  document.getElementById("prof-github").value = p.socials?.github || "";
  document.getElementById("prof-salary").value = p.experience_and_preferences?.desired_salary_usd || "";
  document.getElementById("prof-notice").value = p.experience_and_preferences?.notice_period || "";
  document.getElementById("prof-sponsorship").value = p.work_authorization?.requires_sponsorship || "No";
}

btnSaveProfile.addEventListener("click", async () => {
  const nameParts = document.getElementById("prof-name").value.trim().split(" ");
  candidateProfile.personal = candidateProfile.personal || {};
  candidateProfile.personal.full_name = document.getElementById("prof-name").value.trim();
  candidateProfile.personal.first_name = nameParts[0] || "";
  candidateProfile.personal.last_name = nameParts.slice(1).join(" ") || "";
  candidateProfile.personal.email = document.getElementById("prof-email").value.trim();
  candidateProfile.personal.phone = document.getElementById("prof-phone").value.trim();

  candidateProfile.socials = candidateProfile.socials || {};
  candidateProfile.socials.linkedin = document.getElementById("prof-linkedin").value.trim();
  candidateProfile.socials.github = document.getElementById("prof-github").value.trim();

  candidateProfile.experience_and_preferences = candidateProfile.experience_and_preferences || {};
  candidateProfile.experience_and_preferences.desired_salary_usd = document.getElementById("prof-salary").value.trim();
  candidateProfile.experience_and_preferences.notice_period = document.getElementById("prof-notice").value.trim();

  candidateProfile.work_authorization = candidateProfile.work_authorization || {};
  candidateProfile.work_authorization.requires_sponsorship = document.getElementById("prof-sponsorship").value;

  await chrome.storage.local.set({ candidateProfile: candidateProfile });

  // If bridge server is up, update backend file too
  fetch(`${BRIDGE_URL}/api/profile`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(candidateProfile)
  }).catch(() => {});

  showToast("Candidate profile saved!");
});

// Multi-Frame DOM Scanning
btnScan.addEventListener("click", () => {
  scanActiveTab(true);
});

async function scanActiveTab(userInitiated = false) {
  btnScan.disabled = true;
  btnScan.innerText = "Scanning...";
  if (detectedFields.length === 0) {
    fieldsList.innerHTML = `<div class="empty-state">Inspecting DOM elements across all page frames...</div>`;
  }

  try {
    const tab = await getActiveTab();
    if (!tab || !tab.id) {
      btnScan.disabled = false;
      btnScan.innerText = "Scan DOM";
      if (userInitiated) showToast("No active tab found.");
      return;
    }

    if (tab.title) {
      pageTitleText.innerText = tab.title;
    }

    // 1. Instant check against background cache for immediate render (0ms)
    try {
      const cached = await chrome.runtime.sendMessage({ action: "GET_CACHED_TAB_SCAN", tabId: tab.id });
      if (cached && cached.fields && cached.fields.length > 0) {
        handleScanSuccess(cached.fields, cached.title || tab.title);
      }
    } catch (e) {}

    // 2. Ensure content.js is injected in all frames of this tab
    try {
      await chrome.scripting.executeScript({
        target: { tabId: tab.id, allFrames: true },
        files: ["content.js"]
      });
    } catch (e) {
      // Chrome internal/restricted URLs
    }

    // 3. Query all frames via isolated world function execution
    let multiFrameResults = [];
    try {
      multiFrameResults = await chrome.scripting.executeScript({
        target: { tabId: tab.id, allFrames: true },
        func: () => {
          if (typeof window.__jobCopilotScan === "function") {
            return window.__jobCopilotScan();
          }
          return null;
        }
      });
    } catch (scriptErr) {
      console.warn("Direct multi-frame scripting error:", scriptErr);
    }

    let aggregatedFields = [];
    let framePageTitle = tab.title;

    if (Array.isArray(multiFrameResults)) {
      multiFrameResults.forEach((frameObj) => {
        const frameScan = frameObj.result;
        if (frameScan && Array.isArray(frameScan.fields) && frameScan.fields.length > 0) {
          frameScan.fields.forEach((f) => {
            f._frameId = frameObj.frameId;
          });
          aggregatedFields.push(...frameScan.fields);
          if (frameScan.title && !framePageTitle) {
            framePageTitle = frameScan.title;
          }
        }
      });
    }

    // 4. Fallback: also try chrome.tabs.sendMessage if executeScript returned no fields
    if (aggregatedFields.length === 0) {
      try {
        const directMsgRes = await new Promise((resolve) => {
          chrome.tabs.sendMessage(tab.id, { action: "SCAN_FIELDS" }, (r) => {
            resolve(chrome.runtime.lastError ? null : r);
          });
        });
        if (directMsgRes && directMsgRes.fields && directMsgRes.fields.length > 0) {
          aggregatedFields = directMsgRes.fields;
          if (directMsgRes.title) framePageTitle = directMsgRes.title;
        }
      } catch (e) {}
    }

    handleScanSuccess(aggregatedFields, framePageTitle);
    if (userInitiated) {
      showToast(`Found ${aggregatedFields.length} fillable fields!`);
    }
  } catch (err) {
    btnScan.disabled = false;
    btnScan.innerText = "Scan DOM";
    if (userInitiated) showToast(`Scan error: ${err.message}`);
  }
}

function handleScanSuccess(fields, title) {
  btnScan.disabled = false;
  btnScan.innerText = "Scan DOM";

  if (title) pageTitleText.innerText = title;
  detectedFields = fields || [];
  fieldCountBadge.innerText = `${detectedFields.length} fields detected`;
  fieldCountBadge.className = detectedFields.length > 0 ? "badge tag-blue" : "badge badge-muted";

  renderFieldsList(detectedFields);
  btnAutofill.disabled = detectedFields.length === 0;
}

function renderFieldsList(fields) {
  if (!fields.length) {
    fieldsList.innerHTML = `<div class="empty-state">No fillable form fields found on this page.</div>`;
    return;
  }

  fieldsList.innerHTML = "";
  fields.forEach((f) => {
    const item = document.createElement("div");
    item.className = "field-item";
    item.innerHTML = `
      <div class="field-header">
        <span class="field-label">${escapeHtml(f.label)} ${f.required ? '<span style="color:#ef4444;">*</span>' : ''}</span>
        <span class="field-type">${f.type || f.tagName}</span>
      </div>
      <input type="text" class="field-val-input" data-id="${f.id}" placeholder="AI proposed answer..." value="${escapeHtml(currentMatches[f.id] || f.currentValue || '')}">
    `;
    // Clicking label highlights element in whichever frame it lives
    item.querySelector(".field-label").addEventListener("click", async () => {
      const tab = await getActiveTab();
      if (!tab?.id) return;
      try {
        await chrome.scripting.executeScript({
          target: { tabId: tab.id, allFrames: true },
          func: (fieldId) => {
            if (typeof window.__jobCopilotHighlight === "function") {
              window.__jobCopilotHighlight(fieldId);
            }
          },
          args: [f.id]
        });
      } catch (e) {
        chrome.tabs.sendMessage(tab.id, { action: "HIGHLIGHT_FIELD", id: f.id });
      }
    });
    fieldsList.appendChild(item);
  });
}

// AI Form Autofill
btnAutofill.addEventListener("click", async () => {
  if (!detectedFields.length) return;

  btnAutofill.disabled = true;
  btnAutofill.innerHTML = `<span>⏳</span> Reasoning Form Answers...`;
  matchStatus.innerText = "Reasoning...";

  try {
    const mode = settingLlmMode.value;
    let matches = {};

    if (mode === "bridge") {
      matches = await matchFieldsViaBridge(detectedFields);
    } else if (mode === "direct-gemini") {
      matches = await matchFieldsViaGemini(detectedFields);
    } else if (mode === "direct-openai") {
      matches = await matchFieldsViaOpenAI(detectedFields);
    }

    currentMatches = matches;
    // Update input boxes in preview list
    document.querySelectorAll(".field-val-input").forEach((inp) => {
      const id = inp.getAttribute("data-id");
      if (matches[id] !== undefined) {
        inp.value = matches[id];
      }
    });

    // Send fill command across all frames
    const tab = await getActiveTab();
    if (tab?.id) {
      let totalFilled = 0;
      try {
        const fillResults = await chrome.scripting.executeScript({
          target: { tabId: tab.id, allFrames: true },
          func: async (matchDict) => {
            if (typeof window.__jobCopilotFill === "function") {
              return await window.__jobCopilotFill(matchDict);
            }
            return 0;
          },
          args: [matches]
        });

        if (Array.isArray(fillResults)) {
          fillResults.forEach((fr) => {
            if (typeof fr.result === "number") totalFilled += fr.result;
          });
        }
      } catch (e) {
        console.warn("Scripting fill error, trying message fallback:", e);
      }

      // Also send message fallback
      chrome.tabs.sendMessage(tab.id, { action: "FILL_FIELDS", matches: matches }, (res) => {
        const count = res?.count || totalFilled || Object.keys(matches).length;
        showToast(`✨ Auto-filled ${count} fields! Review before submitting.`);
        matchStatus.innerText = `Filled ${count} fields`;
      });
    }
  } catch (err) {
    showToast(`Autofill failed: ${err.message}`);
    matchStatus.innerText = "Failed";
  } finally {
    btnAutofill.disabled = false;
    btnAutofill.innerHTML = `<span>✨</span> Auto-Fill with AI`;
  }
});

async function matchFieldsViaBridge(fields) {
  const res = await fetch(`${BRIDGE_URL}/api/match-fields`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ fields: fields, profile_override: candidateProfile })
  });
  if (!res.ok) {
    throw new Error("Bridge server returned error. Ensure `python server.py` is running.");
  }
  const data = await res.json();
  return data.matches || {};
}

async function matchFieldsViaGemini(fields) {
  const storage = await chrome.storage.local.get("apiKey");
  const key = storage.apiKey;
  if (!key) throw new Error("Gemini API key is missing. Set it in the Profile tab.");

  const prompt = `Map these form fields to candidate data:
PROFILE: ${JSON.stringify(candidateProfile)}
FIELDS: ${JSON.stringify(fields)}
Return ONLY JSON format: { "matches": { "field_id": "value" } }`;

  const url = `https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key=${key}`;
  const res = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      contents: [{ parts: [{ text: prompt }] }],
      generationConfig: { responseMimeType: "application/json" }
    })
  });
  const data = await res.json();
  const text = data.candidates?.[0]?.content?.parts?.[0]?.text;
  const parsed = JSON.parse(text || "{}");
  return parsed.matches || {};
}

async function matchFieldsViaOpenAI(fields) {
  const storage = await chrome.storage.local.get("apiKey");
  const key = storage.apiKey;
  if (!key) throw new Error("OpenAI API key is missing. Set it in the Profile tab.");

  const prompt = `Map these form fields to candidate data:
PROFILE: ${JSON.stringify(candidateProfile)}
FIELDS: ${JSON.stringify(fields)}
Return ONLY JSON format: { "matches": { "field_id": "value" } }`;

  const res = await fetch("https://api.openai.com/v1/chat/completions", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${key}`
    },
    body: JSON.stringify({
      model: "gpt-4o-mini",
      messages: [{ role: "user", content: prompt }],
      response_format: { type: "json_object" }
    })
  });
  const data = await res.json();
  const content = data.choices?.[0]?.message?.content;
  const parsed = JSON.parse(content || "{}");
  return parsed.matches || {};
}

// Job Discovery Tab
btnSearchJobs.addEventListener("click", async () => {
  btnSearchJobs.disabled = true;
  btnSearchJobs.innerHTML = `<span>⏳</span> Scraping live jobs...`;
  searchResults.innerHTML = `<div class="empty-state">Searching LinkedIn, Indeed, Glassdoor...</div>`;

  const query = document.getElementById("search-query").value.trim();
  const location = document.getElementById("search-location").value.trim();
  const limit = parseInt(document.getElementById("search-limit").value) || 5;
  const country = document.getElementById("search-country")?.value || "usa";
  const job_type = document.getElementById("search-job-type")?.value || "fulltime";

  const sites = [];
  if (document.getElementById("site-linkedin").checked) sites.push("linkedin");
  if (document.getElementById("site-indeed").checked) sites.push("indeed");
  if (document.getElementById("site-glassdoor").checked) sites.push("glassdoor");

  try {
    const res = await fetch(`${BRIDGE_URL}/api/jobs/search`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ query, location, country, job_type, limit, sites })
    });

    if (!res.ok) throw new Error("Please ensure python server.py is running for JobSpy search.");

    const data = await res.json();
    renderSearchResults(data.jobs || []);
  } catch (err) {
    searchResults.innerHTML = `<div class="empty-state" style="color:#ef4444;">Error: ${err.message}</div>`;
  } finally {
    btnSearchJobs.disabled = false;
    btnSearchJobs.innerHTML = `<span>🔍</span> Search Jobs`;
  }
});

function renderSearchResults(jobs) {
  if (!jobs.length) {
    searchResults.innerHTML = `<div class="empty-state">No jobs found. Try different keywords.</div>`;
    return;
  }

  searchResults.innerHTML = "";
  jobs.forEach((job) => {
    const card = document.createElement("div");
    card.className = "job-card";
    const typeLabel = job.job_type && job.job_type.toLowerCase() === "fulltime" ? "Full-time" : (job.job_type || "Full-time");
    card.innerHTML = `
      <a class="job-title" href="${job.job_url}" target="_blank">${escapeHtml(job.title)}</a>
      <div class="job-company">${escapeHtml(job.company)}</div>
      <div class="job-meta">
        <span>📍 ${escapeHtml(job.location)}</span>
        <span class="tag tag-green">${escapeHtml(typeLabel)}</span>
        <span class="tag tag-blue">${escapeHtml(job.site)}</span>
      </div>
    `;
    searchResults.appendChild(card);
  });
}

function escapeHtml(text) {
  if (!text) return "";
  return String(text)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#039;");
}
