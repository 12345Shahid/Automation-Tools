// Content Script for Skool Outreach Assistant
(() => {
  let isRunning = false;
  let isPaused = false;
  let campaignQueue = [];
  let currentIndex = 0;
  let countdownTimer = null;
  let currentCountdown = 0;

  let config = {
    template: "{Assalamu Alaikum|Salam} {first_name}! How are you brother?",
    minDelay: 45,
    maxDelay: 90,
    dailyLimit: 25,
    skipAdmins: true,
    dryRun: false,
    messagedUsers: {}
  };

  // 1. Spintax & Personalization Engine
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

  function personalizeMessage(template, member) {
    let msg = template;
    const firstName = member.name ? member.name.trim().split(" ")[0] : "there";
    msg = msg.replace(/\{first_name\}/gi, firstName);
    msg = msg.replace(/\{name\}/gi, member.name || firstName);
    msg = msg.replace(/\{username\}/gi, member.username || "");
    return resolveSpintax(msg);
  }

  // 2. DOM Member Scraper (Compatible with Skool.com & Local Simulation)
  function scanCommunityMembers() {
    const members = [];
    const seenIds = new Set();

    // Strategy A: Check local simulation member cards or explicit test cards
    const localCards = Array.from(document.querySelectorAll('.member-card, [data-user-id]'));
    if (localCards.length > 0) {
      localCards.forEach((node, idx) => {
        const link = node.querySelector('a[href*="/@"]') || node.querySelector('.member-name') || node;
        const href = link.getAttribute('href') || '';
        const usernameMatch = href.match(/@([a-zA-Z0-9_\-\.]+)/) || [null, node.getAttribute('data-username') || `user_${idx}`];
        const username = usernameMatch[1] || `user_${idx}`;

        const userId = node.getAttribute('data-user-id') || username;
        if (seenIds.has(userId)) return;
        seenIds.add(userId);

        const nameEl = node.querySelector('.member-name, [class*="name"], h3, h4, strong') || link;
        let fullName = nameEl?.innerText?.trim() || username;
        if (fullName.startsWith("@")) fullName = fullName.substring(1);

        const textContent = node.innerText.toLowerCase();
        const roleAttr = (node.getAttribute('data-role') || '').toLowerCase();
        const isAdmin = roleAttr.includes('admin') || roleAttr.includes('creator') ||
                        textContent.includes('creator') || textContent.includes('admin') ||
                        textContent.includes('moderator') || textContent.includes('staff');

        const chatBtn = node.querySelector('.btn-chat, button:has(svg), [aria-label*="Chat"], [title*="Chat"]') ||
                        Array.from(node.querySelectorAll('button')).find(b => /chat|message/i.test(b.innerText));

        members.push({
          id: userId,
          name: fullName,
          username: username,
          isAdmin: isAdmin,
          node: node,
          chatBtn: chatBtn
        });
      });
      return members;
    }

    // Strategy B: Real Skool.com DOM Member Extraction
    // Find all profile links on Skool, ignoring top navigation / headers
    const profileLinks = Array.from(document.querySelectorAll('a[href*="/@"]')).filter(link => {
      // Exclude navbar, header, and self profile links
      return !link.closest('header, nav, [role="navigation"], .top-nav, .search-box');
    });

    profileLinks.forEach((link, idx) => {
      const href = link.getAttribute('href') || '';
      const usernameMatch = href.match(/@([a-zA-Z0-9_\-\.]+)/);
      if (!usernameMatch) return;
      const username = usernameMatch[1];

      if (seenIds.has(username) || username === "settings" || username === "notifications") return;
      seenIds.add(username);

      // Locate row/card container
      const container = link.closest('[data-testid*="member"], [role="row"], tr, li, div:has(> button)') ||
                        link.parentElement.parentElement || link;

      // Extract display name
      let fullName = link.innerText.trim();
      if (!fullName || fullName.length < 2) {
        const nameHeader = container.querySelector('h2, h3, h4, [class*="name"], [class*="title"], strong');
        if (nameHeader && nameHeader.innerText.trim()) {
          fullName = nameHeader.innerText.trim();
        }
      }
      if (!fullName) fullName = username;
      if (fullName.startsWith("@")) fullName = fullName.substring(1);

      // Check admin status
      const containerText = container.innerText.toLowerCase();
      const isAdmin = containerText.includes('admin') || containerText.includes('creator') ||
                      containerText.includes('moderator') || containerText.includes('staff') ||
                      containerText.includes('owner');

      // Look for a direct chat button if available on the card
      const chatBtn = container.querySelector('button[aria-label*="chat" i], button[title*="chat" i], [data-testid*="chat"]') ||
                      Array.from(container.querySelectorAll('button')).find(b => /chat|message/i.test(b.innerText.trim()));

      members.push({
        id: username,
        name: fullName,
        username: username,
        isAdmin: isAdmin,
        node: link,
        chatBtn: chatBtn
      });
    });

    return members;
  }

  // Filter members eligible for outreach
  async function getEligibleMembers() {
    await syncConfigFromStorage();
    const allMembers = scanCommunityMembers();
    const messaged = config.messagedUsers || {};

    return allMembers.filter(m => {
      if (config.skipAdmins && m.isAdmin) return false;
      if (messaged[m.id] || messaged[m.username]) return false;
      return true;
    });
  }

  // 3. Humanized Typing & Chat Modal Automation
  function sleep(ms) {
    return new Promise(resolve => setTimeout(resolve, ms));
  }

  function randomBetween(min, max) {
    return Math.floor(Math.random() * (max - min + 1)) + min;
  }

  // Locates the active message input on Skool or mock page
  function findChatInput() {
    return document.querySelector(
      '#chat-input, .chat-textarea, [data-testid*="chat-input"], [contenteditable="true"][role="textbox"], .tiptap.ProseMirror, div.ProseMirror, [contenteditable="true"], textarea[placeholder*="message" i], textarea'
    );
  }

  // Sets text in both standard <textarea> and rich-text contenteditable divs
  async function insertMessageIntoChat(element, text) {
    element.focus();
    element.scrollIntoView({ behavior: 'smooth', block: 'center' });

    if (element.tagName === 'TEXTAREA' || element.tagName === 'INPUT') {
      const setter = Object.getOwnPropertyDescriptor(window.HTMLTextAreaElement.prototype, 'value')?.set;
      if (setter) {
        setter.call(element, text);
      } else {
        element.value = text;
      }
      element.dispatchEvent(new Event('input', { bubbles: true }));
      element.dispatchEvent(new Event('change', { bubbles: true }));
    } else if (element.isContentEditable || element.getAttribute('contenteditable') === 'true') {
      // Contenteditable ProseMirror/TipTap standard on Skool
      const selection = window.getSelection();
      const range = document.createRange();
      range.selectNodeContents(element);
      selection.removeAllRanges();
      selection.addRange(range);

      const inserted = document.execCommand('insertText', false, text);
      if (!inserted || !element.innerText.includes(text.substring(0, 5))) {
        element.innerText = text;
      }
      element.dispatchEvent(new InputEvent('input', { bubbles: true, inputType: 'insertText', data: text }));
      element.dispatchEvent(new Event('input', { bubbles: true }));
      element.dispatchEvent(new Event('change', { bubbles: true }));
    }
  }

  async function processMemberOutreach(member) {
    updateHUDStatus(`Connecting with ${member.name}...`, `Opening chat dialog`);

    // 1. Click member chat trigger (direct button or member profile link)
    if (member.chatBtn) {
      member.chatBtn.scrollIntoView({ behavior: 'smooth', block: 'center' });
      member.chatBtn.click();
    } else {
      member.node.scrollIntoView({ behavior: 'smooth', block: 'center' });
      member.node.click();
    }

    // 2. Wait for modal or chat drawer to mount
    await sleep(1500);

    // 3. Locate chat input
    let chatInput = findChatInput();

    // If chat input is not yet open, check if Skool opened a Profile Card modal with a "Chat" button
    if (!chatInput) {
      const modalButtons = Array.from(document.querySelectorAll('button, a[role="button"]'));
      const chatBtnInModal = modalButtons.find(b => {
        const txt = (b.innerText || b.getAttribute('aria-label') || b.title || '').trim().toLowerCase();
        return txt === 'chat' || txt === 'message' || txt.includes('chat with') || txt.includes('send message');
      });
      if (chatBtnInModal) {
        updateHUDStatus(`Opening conversation with ${member.name}...`, `Clicking profile Chat button`);
        chatBtnInModal.click();
        await sleep(1500);
        chatInput = findChatInput();
      }
    }

    if (!chatInput) {
      throw new Error(`Chat input box not found for ${member.name}`);
    }

    // 4. Personalize message template
    const personalizedText = personalizeMessage(config.template, member);
    updateHUDStatus(`Drafting message for ${member.name}...`, personalizedText);

    // 5. Simulate realistic human typing
    await insertMessageIntoChat(chatInput, personalizedText);
    await sleep(randomBetween(1500, 2500)); // Natural human pause before sending

    // 6. Handle Send or Dry Run
    if (config.dryRun) {
      updateHUDStatus(`[DRY-RUN] Previewing message for ${member.name}`, `Skipped clicking Send (Safe Mode active)`);
      await sleep(2500);
    } else {
      const sendBtn = document.querySelector(
        '#chat-send-btn, button[type="submit"], [aria-label*="Send" i], button:has(svg[data-testid*="send"])'
      ) || Array.from(document.querySelectorAll('button')).find(b => /^send$/i.test(b.innerText.trim()));

      if (sendBtn) {
        sendBtn.click();
      } else {
        // Press Enter key to send
        chatInput.dispatchEvent(new KeyboardEvent('keydown', { key: 'Enter', code: 'Enter', keyCode: 13, which: 13, bubbles: true }));
      }
      updateHUDStatus(`✓ Sent message to ${member.name}`, `Recording to outreach history`);
      await sleep(1000);
    }

    // 7. Close chat drawer / modal
    const closeBtn = document.querySelector(
      '#drawer-close-btn, .chat-close-btn, button[aria-label="Close" i], [data-testid*="close"], button:has(svg[data-testid*="close"])'
    );
    if (closeBtn) {
      closeBtn.click();
    } else {
      document.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape', code: 'Escape', keyCode: 27, bubbles: true }));
    }
    await sleep(400);
    // Extra escape press to dismiss any remaining backdrop modal
    document.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape', code: 'Escape', keyCode: 27, bubbles: true }));

    // 8. Record in history
    chrome.runtime.sendMessage({
      action: "RECORD_MESSAGED_USER",
      user: { id: member.id, name: member.name, username: member.username }
    });

    // Update in-memory config
    config.messagedUsers = config.messagedUsers || {};
    config.messagedUsers[member.id] = { name: member.name, username: member.username, date: new Date().toISOString() };
  }

  // 4. Campaign Loop Controller
  async function startOutreachCampaign() {
    if (isRunning) return;
    isRunning = true;
    isPaused = false;

    updateHUDButtonState();
    campaignQueue = await getEligibleMembers();
    currentIndex = 0;

    if (campaignQueue.length === 0) {
      updateHUDStatus("No eligible members found", "All members on this page have already been messaged or are admins.");
      stopOutreachCampaign();
      return;
    }

    updateHUDStatus(`Campaign Started`, `${campaignQueue.length} eligible candidates in queue`);

    while (isRunning && currentIndex < campaignQueue.length && currentIndex < config.dailyLimit) {
      if (isPaused) {
        updateHUDStatus("Campaign Paused", "Click Resume to continue");
        await sleep(1000);
        continue;
      }

      const member = campaignQueue[currentIndex];
      try {
        await processMemberOutreach(member);
        currentIndex++;

        if (currentIndex < campaignQueue.length && currentIndex < config.dailyLimit && isRunning) {
          // Calculate humanized random delay
          const delaySec = randomBetween(config.minDelay, config.maxDelay);
          await runCountdown(delaySec, `Next member: ${campaignQueue[currentIndex]?.name}`);
        }
      } catch (err) {
        console.error("Outreach error on member:", member, err);
        updateHUDStatus(`Skipping ${member.name}`, err.message);
        currentIndex++;
        await sleep(3000);
      }
    }

    if (currentIndex >= config.dailyLimit) {
      updateHUDStatus(`Daily Session Limit Reached (${config.dailyLimit})`, "Outreach paused to preserve account safety.");
    } else if (currentIndex >= campaignQueue.length) {
      updateHUDStatus(`✓ Completed Outreach Queue`, `Finished messaging all ${campaignQueue.length} eligible members!`);
    }

    stopOutreachCampaign();
  }

  function pauseOutreachCampaign() {
    isPaused = true;
    updateHUDButtonState();
    updateHUDStatus("Paused", "Outreach paused. Click Resume to continue.");
  }

  function resumeOutreachCampaign() {
    isPaused = false;
    updateHUDButtonState();
    updateHUDStatus("Resuming...", "Continuing campaign queue");
  }

  function stopOutreachCampaign() {
    isRunning = false;
    isPaused = false;
    clearInterval(countdownTimer);
    updateHUDButtonState();
  }

  function runCountdown(seconds, nextInfo) {
    return new Promise(resolve => {
      currentCountdown = seconds;
      updateHUDStatus(`Waiting ${currentCountdown}s (Random Safety Delay)`, nextInfo);

      clearInterval(countdownTimer);
      countdownTimer = setInterval(() => {
        if (!isRunning) {
          clearInterval(countdownTimer);
          resolve();
          return;
        }
        if (isPaused) return; // Keep waiting without counting down

        currentCountdown--;
        if (currentCountdown <= 0) {
          clearInterval(countdownTimer);
          resolve();
        } else {
          updateHUDStatus(`Waiting ${currentCountdown}s (Random Safety Delay)`, nextInfo);
        }
      }, 1000);
    });
  }

  // 5. In-Page Floating HUD (Heads-Up Display)
  function createFloatingHUD() {
    if (document.getElementById("skool-outreach-hud")) return;

    const hud = document.createElement("div");
    hud.id = "skool-outreach-hud";
    hud.style.cssText = `
      position: fixed;
      bottom: 24px;
      right: 24px;
      z-index: 2147483647;
      background: #11141c;
      color: #f3f4f6;
      border: 1px solid #2a2e3d;
      border-radius: 14px;
      box-shadow: 0 10px 30px rgba(0,0,0,0.6);
      width: 330px;
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
      padding: 14px 16px;
      display: flex;
      flex-direction: column;
      gap: 10px;
      animation: fadeIn 0.25s ease;
    `;

    hud.innerHTML = `
      <div style="display: flex; justify-content: space-between; align-items: center; border-bottom: 1px solid #232734; padding-bottom: 8px;">
        <div style="display: flex; align-items: center; gap: 8px; font-weight: 700; font-size: 13px; color: #fbbf24;">
          <span>⚡</span> Skool Outreach Assistant
        </div>
        <button id="hud-minimize-btn" style="background:none; border:none; color:#9ca3af; cursor:pointer; font-size:14px;">−</button>
      </div>

      <div id="hud-content-body" style="display: flex; flex-direction: column; gap: 8px;">
        <div id="hud-status-title" style="font-size: 12px; font-weight: 600; color: #38bdf8;">
          Ready to scan members
        </div>
        <div id="hud-status-detail" style="font-size: 11px; color: #9ca3af; line-height: 1.4; max-height: 48px; overflow: hidden; text-overflow: ellipsis;">
          Open the community Members tab and click Start.
        </div>

        <div style="display: flex; gap: 8px; margin-top: 4px;">
          <button id="hud-start-btn" style="flex: 1; background: #f59e0b; color: #0f172a; border: none; padding: 8px 12px; border-radius: 8px; font-size: 12px; font-weight: 700; cursor: pointer;">
            ▶ Start Campaign
          </button>
          <button id="hud-pause-btn" style="display: none; background: #374151; color: #f3f4f6; border: none; padding: 8px 12px; border-radius: 8px; font-size: 12px; font-weight: 600; cursor: pointer;">
            ⏸ Pause
          </button>
          <button id="hud-stop-btn" style="display: none; background: #ef4444; color: white; border: none; padding: 8px 12px; border-radius: 8px; font-size: 12px; font-weight: 600; cursor: pointer;">
            ⏹ Stop
          </button>
        </div>
      </div>
    `;

    document.body.appendChild(hud);

    // Button event listeners
    const startBtn = hud.querySelector("#hud-start-btn");
    const pauseBtn = hud.querySelector("#hud-pause-btn");
    const stopBtn = hud.querySelector("#hud-stop-btn");
    const minimizeBtn = hud.querySelector("#hud-minimize-btn");
    const body = hud.querySelector("#hud-content-body");

    startBtn.addEventListener("click", () => {
      if (!isRunning) startOutreachCampaign();
    });

    pauseBtn.addEventListener("click", () => {
      if (isPaused) {
        resumeOutreachCampaign();
      } else {
        pauseOutreachCampaign();
      }
    });

    stopBtn.addEventListener("click", () => {
      stopOutreachCampaign();
      updateHUDStatus("Campaign Stopped", "Ready to start again when you are.");
    });

    minimizeBtn.addEventListener("click", () => {
      const isMin = body.style.display === "none";
      body.style.display = isMin ? "flex" : "none";
      minimizeBtn.innerText = isMin ? "−" : "+";
    });
  }

  function updateHUDStatus(title, detail) {
    const titleEl = document.getElementById("hud-status-title");
    const detailEl = document.getElementById("hud-status-detail");
    if (titleEl) titleEl.innerText = title;
    if (detailEl) detailEl.innerText = detail || "";
  }

  function updateHUDButtonState() {
    const startBtn = document.getElementById("hud-start-btn");
    const pauseBtn = document.getElementById("hud-pause-btn");
    const stopBtn = document.getElementById("hud-stop-btn");

    if (!startBtn || !pauseBtn || !stopBtn) return;

    if (isRunning) {
      startBtn.style.display = "none";
      pauseBtn.style.display = "block";
      stopBtn.style.display = "block";
      pauseBtn.innerText = isPaused ? "▶ Resume" : "⏸ Pause";
    } else {
      startBtn.style.display = "block";
      pauseBtn.style.display = "none";
      stopBtn.style.display = "none";
    }
  }

  async function syncConfigFromStorage() {
    return new Promise(resolve => {
      chrome.storage.local.get("skoolConfig", res => {
        if (res.skoolConfig) {
          config = { ...config, ...res.skoolConfig };
        }
        resolve(config);
      });
    });
  }

  // Handle messages from Popup
  chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {
    if (request.action === "SCAN_MEMBERS") {
      getEligibleMembers().then(eligible => {
        const all = scanCommunityMembers();
        sendResponse({
          totalOnPage: all.length,
          eligibleCount: eligible.length,
          adminCount: all.filter(m => m.isAdmin).length,
          messagedCount: all.length - eligible.length - all.filter(m => m.isAdmin).length
        });
      });
      return true;
    }

    if (request.action === "START_CAMPAIGN") {
      startOutreachCampaign();
      sendResponse({ status: "started" });
      return true;
    }

    if (request.action === "PAUSE_CAMPAIGN") {
      pauseOutreachCampaign();
      sendResponse({ status: "paused" });
      return true;
    }

    if (request.action === "RESUME_CAMPAIGN") {
      resumeOutreachCampaign();
      sendResponse({ status: "resumed" });
      return true;
    }

    if (request.action === "STOP_CAMPAIGN") {
      stopOutreachCampaign();
      sendResponse({ status: "stopped" });
      return true;
    }

    return true;
  });

  // Inject HUD when DOM is loaded
  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", () => {
      syncConfigFromStorage().then(createFloatingHUD);
    });
  } else {
    syncConfigFromStorage().then(createFloatingHUD);
  }
})();
