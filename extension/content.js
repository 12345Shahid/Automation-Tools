// Content script for Job Co-Pilot: Zero-token DOM extractor and form injector

(() => {
  let fieldCounter = 0;

  function findFieldLabel(element) {
    // 1. Aria-labelledby (Standard for Workday, LinkedIn, Salesforce)
    const labelledby = element.getAttribute("aria-labelledby");
    if (labelledby) {
      const parts = labelledby.split(" ").map(id => document.getElementById(id)?.innerText?.trim()).filter(Boolean);
      if (parts.length > 0) return parts.join(" - ");
    }

    // 2. Fieldset legend (Crucial for LinkedIn Easy Apply & Workday radio groups)
    const fieldset = element.closest("fieldset");
    let legendText = "";
    if (fieldset) {
      const legend = fieldset.querySelector("legend");
      if (legend && legend.innerText.trim()) {
        legendText = legend.innerText.trim();
      }
    }

    // 3. Explicit HTML label association
    let directLabelText = "";
    if (element.id) {
      const explicitLabel = document.querySelector(`label[for="${element.id}"]`);
      if (explicitLabel && explicitLabel.innerText.trim()) {
        directLabelText = explicitLabel.innerText.trim();
      }
    }

    // 4. Element's own labels collection
    if (!directLabelText && element.labels && element.labels.length > 0) {
      directLabelText = element.labels[0].innerText.trim();
    }

    // 5. Aria-label or placeholder or title
    if (!directLabelText) {
      directLabelText = element.getAttribute("aria-label")?.trim() ||
                        element.placeholder?.trim() ||
                        element.title?.trim() || "";
    }

    // 6. Closest enclosing label or common form container
    if (!directLabelText) {
      const parentLabel = element.closest("label");
      if (parentLabel && parentLabel.innerText.trim()) {
        directLabelText = parentLabel.innerText.trim();
      }
    }

    if (!directLabelText) {
      const container = element.closest(".form-group, .field, .input-container, .jobs-easy-apply-form-section__grouping, [data-automation-id*='formLabel']");
      if (container) {
        const heading = container.querySelector("label, .label, legend, span, h3, h4, [data-automation-id='formLabel']");
        if (heading && heading.innerText.trim()) {
          directLabelText = heading.innerText.trim();
        }
      }
    }

    let finalLabel = directLabelText;
    if (legendText && directLabelText && !legendText.includes(directLabelText)) {
      finalLabel = `${legendText} (${directLabelText})`;
    } else if (legendText && !directLabelText) {
      finalLabel = legendText;
    } else if (!directLabelText) {
      finalLabel = element.getAttribute("data-automation-id") ||
                   element.getAttribute("data-qa") ||
                   element.getAttribute("autocomplete") ||
                   element.name || element.id || "Field";
    }

    // Detect enclosing section (e.g. "Employer" or "Education")
    const section = findEnclosingSection(element);
    if (section && !finalLabel.toLowerCase().includes(section.toLowerCase())) {
      finalLabel = `${section} - ${finalLabel}`;
    }

    return finalLabel;
  }

  function findEnclosingSection(element) {
    let curr = element.parentElement;
    let depth = 0;
    while (curr && curr !== document.body && depth < 8) {
      const headings = Array.from(curr.querySelectorAll(":scope > h1, :scope > h2, :scope > h3, :scope > h4, :scope > legend, :scope > header, :scope > .section-header, :scope > [data-automation-id*='section']"));
      for (const h of headings) {
        const txt = h.innerText.trim().split("\n")[0];
        if (txt && txt.length > 2 && txt.length < 40 && !/submit|application|review/i.test(txt)) {
          return txt;
        }
      }
      let prev = curr.previousElementSibling;
      while (prev) {
        if (/^H[1-4]$/.test(prev.tagName) || prev.classList?.contains("header") || prev.classList?.contains("section-title")) {
          const txt = prev.innerText.trim().split("\n")[0];
          if (txt && txt.length > 2 && txt.length < 40) return txt;
        }
        prev = prev.previousElementSibling;
      }
      curr = curr.parentElement;
      depth++;
    }
    return "";
  }

  function scanFormFields() {
    // Scan all interactive form elements including comboboxes and file inputs
    let inputs = Array.from(document.querySelectorAll("input, select, textarea, [role='combobox']"));

    // Also include inputs from accessible child iframes if present
    try {
      const iframes = document.querySelectorAll("iframe");
      iframes.forEach((frame) => {
        try {
          const doc = frame.contentDocument || frame.contentWindow?.document;
          if (doc) {
            inputs = inputs.concat(Array.from(doc.querySelectorAll("input, select, textarea, [role='combobox']")));
          }
        } catch (e) {
          // Cross-origin iframe: handled by all_frames script injection
        }
      });
    } catch (e) {}

    const fields = [];

    inputs.forEach((el) => {
      const type = (el.type || "").toLowerCase();
      // Ignore hidden or submit elements (except file inputs which are often styled/hidden)
      if (["hidden", "submit", "button", "image", "reset"].includes(type)) {
        return;
      }
      
      // Check visibility: allow elements even if styled with opacity: 0 (standard for custom datepickers, radios, checkboxes, and dropzones)
      const style = window.getComputedStyle(el);
      if (type !== "file" && (style.display === "none" || style.visibility === "hidden")) {
        // Allow if it has custom automation attributes or is within a form field container
        if (!el.getAttribute("data-automation-id") && !el.getAttribute("data-qa")) {
          return;
        }
      }

      // Stable identifier
      let fieldId = el.id || el.name || el.getAttribute("data-automation-id") || el.getAttribute("data-qa");
      if (!fieldId) {
        fieldId = el.getAttribute("data-copilot-id");
        if (!fieldId) {
          fieldCounter++;
          fieldId = `copilot-field-${fieldCounter}`;
          el.setAttribute("data-copilot-id", fieldId);
        }
      }

      const label = findFieldLabel(el);
      const isRequired = el.required || el.getAttribute("aria-required") === "true";

      let options = null;
      if (el.tagName.toLowerCase() === "select") {
        options = Array.from(el.options)
          .map((opt) => opt.text.trim())
          .filter((t) => t.length > 0);
      }

      // If radio or checkbox, include its value
      let radioValue = null;
      if (type === "radio" || type === "checkbox") {
        radioValue = el.value || label;
      }

      fields.push({
        id: fieldId,
        tagName: el.tagName.toLowerCase(),
        type: type || "text",
        name: el.name || "",
        label: label,
        currentValue: el.value || "",
        radioValue: radioValue,
        placeholder: el.placeholder || "",
        required: isRequired,
        options: options
      });
    });

    return {
      url: window.location.href,
      title: document.title,
      fieldCount: fields.length,
      fields: fields
    };
  }

  // React/Angular/Vue compatible value setter
  function setNativeValue(element, value) {
    const valueSetter = Object.getOwnPropertyDescriptor(element, "value")?.set;
    const prototype = Object.getPrototypeOf(element);
    const prototypeValueSetter = Object.getOwnPropertyDescriptor(prototype, "value")?.set;

    if (prototypeValueSetter && valueSetter !== prototypeValueSetter) {
      prototypeValueSetter.call(element, value);
    } else if (valueSetter) {
      valueSetter.call(element, value);
    } else {
      element.value = value;
    }
  }

  function sendLog(event, elementId, value, details) {
    console.log(`[Job Co-Pilot] ${event} -> #${elementId || ''} = ${value || ''}`, details || '');
    try {
      chrome.runtime.sendMessage({
        action: "SEND_LOG",
        payload: { event, element: elementId, value: String(value || ''), details: String(details || '') }
      });
    } catch (e) {}
  }

  function base64ToBlob(base64Data, contentType) {
    const byteCharacters = atob(base64Data);
    const byteNumbers = new Uint8Array(byteCharacters.length);
    for (let i = 0; i < byteCharacters.length; i++) {
      byteNumbers[i] = byteCharacters.charCodeAt(i);
    }
    return new Blob([byteNumbers], { type: contentType });
  }

  async function fetchResumePayload() {
    try {
      const res = await fetch("http://127.0.0.1:8000/api/resume-base64");
      if (res.ok) {
        return await res.json();
      }
    } catch (e) {}

    return new Promise((resolve) => {
      try {
        chrome.runtime.sendMessage({ action: "GET_RESUME_BASE64" }, (response) => {
          resolve(response || { success: false, error: "No response from background worker" });
        });
      } catch (err) {
        resolve({ success: false, error: err.message });
      }
    });
  }

  // Resume auto-upload via DataTransfer & synthetic Drag/Drop events (bypasses Mixed Content)
  async function attachResumeToElement(element) {
    sendLog("FETCH_RESUME_START", element.id || element.name, "Requesting PDF payload");
    const response = await fetchResumePayload();
    if (!response || !response.success || !response.data) {
      sendLog("FETCH_RESUME_FAIL", element.id, "Could not load resume", response?.error || "Unknown error");
      return false;
    }

    try {
      const filename = response.filename || "sample_resume.pdf";
      const blob = base64ToBlob(response.data, "application/pdf");
      const file = new File([blob], filename, { type: "application/pdf" });
      const dt = new DataTransfer();
      dt.items.add(file);

          let fileInput = element;
          if (element.tagName !== "INPUT" || element.type !== "file") {
            fileInput = element.querySelector('input[type="file"]') ||
                        element.closest('.dropzone, .field, .form-group, label, section')?.querySelector('input[type="file"]') ||
                        document.querySelector('input[type="file"]');
          }

          if (fileInput && fileInput.tagName === "INPUT" && fileInput.type === "file") {
            fileInput.files = dt.files;
            fileInput.dispatchEvent(new Event("focus", { bubbles: true }));
            fileInput.dispatchEvent(new Event("input", { bubbles: true }));
            fileInput.dispatchEvent(new Event("change", { bubbles: true }));
            fileInput.dispatchEvent(new Event("blur", { bubbles: true }));

            // Update any filename display element nearby if present
            const filenameBadge = fileInput.closest('.form-group, .field, .dropzone, section')?.querySelector('.filename-display, .file-name, .attached-file');
            if (filenameBadge) {
              filenameBadge.innerText = `✓ Attached: ${filename}`;
              filenameBadge.style.color = "#10b981";
            }
          }

          // Trigger drag & drop on container
          const dropTarget = element.closest('.dropzone, [data-qa*="upload"], label, .field') || element;
          dropTarget.dispatchEvent(new DragEvent("dragenter", { bubbles: true, cancelable: true, dataTransfer: dt }));
          dropTarget.dispatchEvent(new DragEvent("dragover", { bubbles: true, cancelable: true, dataTransfer: dt }));
          dropTarget.dispatchEvent(new DragEvent("drop", { bubbles: true, cancelable: true, dataTransfer: dt }));

          // Visual feedback
          element.scrollIntoView({ behavior: "smooth", block: "center" });
          element.style.outline = "2px solid #10b981";
          element.style.boxShadow = "0 0 12px rgba(16, 185, 129, 0.5)";
          setTimeout(() => {
            element.style.outline = "";
            element.style.boxShadow = "";
          }, 3500);

      sendLog("RESUME_ATTACHED_SUCCESS", fileInput?.id || element.id, filename, `Size: ${file.size} bytes`);
      return true;
    } catch (err) {
      sendLog("RESUME_ATTACH_ERROR", element.id, err.message);
      return false;
    }
  }

  // Comprehensive date parser
  function parseDateParts(val) {
    if (!val) return null;
    const months = [
      "January", "February", "March", "April", "May", "June",
      "July", "August", "September", "October", "November", "December"
    ];
    const shortMonths = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];

    let y, m, d;
    const s = String(val).trim();

    // 1. YYYY-MM-DD or YYYY/MM/DD
    let match = s.match(/^(\d{4})[-\/](\d{1,2})[-\/](\d{1,2})/);
    if (match) {
      y = parseInt(match[1], 10);
      m = parseInt(match[2], 10);
      d = parseInt(match[3], 10);
    }
    // 2. MM/DD/YYYY or MM-DD-YYYY
    if (!match) {
      match = s.match(/^(\d{1,2})[-\/](\d{1,2})[-\/](\d{4})/);
      if (match) {
        m = parseInt(match[1], 10);
        d = parseInt(match[2], 10);
        y = parseInt(match[3], 10);
      }
    }
    // 3. MM/YYYY or MM-YYYY
    if (!match) {
      match = s.match(/^(\d{1,2})[-\/](\d{4})/);
      if (match) {
        m = parseInt(match[1], 10);
        d = 1;
        y = parseInt(match[2], 10);
      }
    }
    // 4. YYYY-MM or YYYY/MM
    if (!match) {
      match = s.match(/^(\d{4})[-\/](\d{1,2})$/);
      if (match) {
        y = parseInt(match[1], 10);
        m = parseInt(match[2], 10);
        d = 1;
      }
    }
    // 5. English Month Name: "May 2019" or "Nov 17, 2026"
    if (!match) {
      let monthIdx = months.findIndex((name) => new RegExp(`\\b${name}\\b`, "i").test(s));
      if (monthIdx === -1) {
        monthIdx = shortMonths.findIndex((name) => new RegExp(`\\b${name}\\b`, "i").test(s));
      }
      if (monthIdx !== -1) {
        m = monthIdx + 1;
        const yMatch = s.match(/\b(19\d\d|20\d\d)\b/);
        y = yMatch ? parseInt(yMatch[1], 10) : new Date().getFullYear();
        const dMatch = s.match(/\b([12]\d|3[01]|0?[1-9])\b/);
        d = dMatch ? parseInt(dMatch[1], 10) : 1;
      }
    }
    // 6. Relative "2 weeks", "today", "immediate", etc.
    if (!y || !m) {
      if (/2\s*weeks|two\s*weeks|today|immediate/i.test(s)) {
        const now = new Date();
        if (/2\s*weeks|two\s*weeks/i.test(s)) {
          now.setDate(now.getDate() + 14);
        }
        y = now.getFullYear();
        m = now.getMonth() + 1;
        d = now.getDate();
      } else {
        return null;
      }
    }

    return {
      year: y,
      month: m,
      day: d,
      yearStr: String(y),
      monthPadded: String(m).padStart(2, "0"),
      monthStr: String(m),
      dayPadded: String(d).padStart(2, "0"),
      dayStr: String(d),
      monthName: months[m - 1],
      monthShort: shortMonths[m - 1],
      iso: `${y}-${String(m).padStart(2, "0")}-${String(d).padStart(2, "0")}`,
      us: `${String(m).padStart(2, "0")}/${String(d).padStart(2, "0")}/${y}`,
      eu: `${String(d).padStart(2, "0")}/${String(m).padStart(2, "0")}/${y}`,
      mmyyyy: `${String(m).padStart(2, "0")}/${y}`,
      monthYear: `${months[m - 1]} ${y}`
    };
  }

  // Handle <select> for split Month / Year / Day
  function handleSelectDateField(element, dateParts) {
    if (!dateParts) return false;
    const nameOrId = (element.name || element.id || "").toLowerCase();
    const label = findFieldLabel(element).toLowerCase();

    const isMonth = /month|mon\b|mm\b/i.test(nameOrId) || /month/i.test(label);
    const isYear = /year|yr\b|yyyy\b/i.test(nameOrId) || /year/i.test(label);
    const isDay = /day|dd\b/i.test(nameOrId) || /day/i.test(label);

    let matchedIndex = -1;

    for (let i = 0; i < element.options.length; i++) {
      const optText = element.options[i].text.toLowerCase().trim();
      const optVal = element.options[i].value.toLowerCase().trim();

      if (isMonth) {
        if (
          optText === dateParts.monthName.toLowerCase() ||
          optVal === dateParts.monthName.toLowerCase() ||
          optText === dateParts.monthShort.toLowerCase() ||
          optVal === dateParts.monthShort.toLowerCase() ||
          optText === dateParts.monthPadded ||
          optVal === dateParts.monthPadded ||
          optText === dateParts.monthStr ||
          optVal === dateParts.monthStr
        ) {
          matchedIndex = i;
          break;
        }
      } else if (isYear) {
        if (optText === dateParts.yearStr || optVal === dateParts.yearStr) {
          matchedIndex = i;
          break;
        }
      } else if (isDay) {
        if (optText === dateParts.dayStr || optVal === dateParts.dayStr || optText === dateParts.dayPadded || optVal === dateParts.dayPadded) {
          matchedIndex = i;
          break;
        }
      } else {
        // Generic match
        if (optText.includes(dateParts.yearStr) || optVal.includes(dateParts.yearStr)) {
          matchedIndex = i;
          break;
        }
      }
    }

    if (matchedIndex !== -1) {
      element.selectedIndex = matchedIndex;
      element.dispatchEvent(new Event("input", { bubbles: true }));
      element.dispatchEvent(new Event("change", { bubbles: true }));
      sendLog("SELECT_DATE_MATCH", element.id || element.name, element.options[matchedIndex].text);
      return true;
    }
    return false;
  }

  // Interacts with and closes open calendar popups (Greenhouse, Workday, Flatpickr, Pikaday, React-Datepicker)
  function tryInteractWithCalendarPopup(dateParts) {
    if (!dateParts) return false;
    const selectors = [
      '.flatpickr-calendar.open',
      '#ui-datepicker-div:not([style*="display: none"]):not([style*="display:none"])',
      '.ui-datepicker:not([style*="display: none"]):not([style*="display:none"])',
      '.pika-single:not(.is-hidden)',
      '.react-datepicker',
      '.react-datepicker-popper',
      '.datepicker.datepicker-dropdown',
      '[data-automation-id="datePickerPopup"]',
      '[role="dialog"] [role="grid"]',
      '[role="dialog"] table'
    ];

    for (const sel of selectors) {
      const popup = document.querySelector(sel);
      if (popup) {
        const dayStr = String(dateParts.day);
        const dayCells = Array.from(popup.querySelectorAll(
          'td:not(.ui-datepicker-other-month):not(.prevMonthDay):not(.nextMonthDay) a, ' +
          'button.flatpickr-day:not(.prevMonthDay):not(.nextMonthDay), ' +
          '.react-datepicker__day:not(.react-datepicker__day--outside-month), ' +
          'button[data-automation-id*="date"], ' +
          'button[role="gridcell"], ' +
          'td[role="gridcell"] button, ' +
          'button.pika-button, ' +
          'td.day:not(.old):not(.new)'
        ));

        const target = dayCells.find(el => el.innerText.trim() === dayStr) ||
                       popup.querySelector('.today, .current-day, .ui-state-active, .flatpickr-day.today') ||
                       dayCells[0];

        if (target) {
          target.click();
          sendLog("CALENDAR_POPUP_CLICK", "calendar-cell", target.innerText.trim());
          return true;
        }
      }
    }
    return false;
  }

  // Smart Date normalization and Calendar widget handling
  function handleDateField(element, rawValue) {
    const dateParts = parseDateParts(rawValue);
    if (!dateParts) return false;

    const tagName = element.tagName.toLowerCase();
    if (tagName === "select") {
      return handleSelectDateField(element, dateParts);
    }

    const type = (element.type || "").toLowerCase();
    const placeholder = (element.placeholder || "").toLowerCase();
    const nameOrId = (element.name || element.id || "").toLowerCase();
    const label = findFieldLabel(element).toLowerCase();

    let dateStr = "";

    // 1. Is this specifically a Month or Year single input?
    if (/month|mon\b|mm\b/i.test(nameOrId) || (/month/i.test(label) && !/date/i.test(nameOrId))) {
      dateStr = dateParts.monthPadded;
    } else if (/year|yr\b|yyyy\b/i.test(nameOrId) || (/year/i.test(label) && !/date/i.test(nameOrId))) {
      dateStr = dateParts.yearStr;
    } else if (type === "date") {
      dateStr = dateParts.iso;
    } else if (type === "month") {
      dateStr = `${dateParts.yearStr}-${dateParts.monthPadded}`;
    } else if (placeholder.includes("dd/mm") || placeholder.includes("dd-mm")) {
      dateStr = dateParts.eu;
    } else if (placeholder.includes("mm/yy") || placeholder.includes("mm-yy") || /graduation|grad|from|to/i.test(label)) {
      dateStr = dateParts.mmyyyy;
    } else {
      dateStr = dateParts.us; // Default to standard US format MM/DD/YYYY
    }

    // 2. Temporarily unlock readOnly if set by calendar libraries (Flatpickr/Pikaday/jQuery)
    const wasReadOnly = element.readOnly;
    if (wasReadOnly) {
      element.readOnly = false;
    }

    // 3. Set value via prototype setter & direct property
    element.value = dateStr;
    setNativeValue(element, dateStr);

    if (element._flatpickr) {
      try { element._flatpickr.setDate(dateStr, true); } catch (e) {}
    }

    // 4. Focus and dispatch full suite of events
    element.focus();
    element.dispatchEvent(new Event("focus", { bubbles: true }));
    element.dispatchEvent(new InputEvent("beforeinput", { bubbles: true, inputType: "insertText", data: dateStr }));
    element.dispatchEvent(new InputEvent("input", { bubbles: true, inputType: "insertText", data: dateStr }));
    element.dispatchEvent(new Event("change", { bubbles: true }));

    // 5. Check if calendar popup opened and click the active day
    setTimeout(() => {
      tryInteractWithCalendarPopup(dateParts);
      // Cleanly dismiss any open popup with Escape
      document.dispatchEvent(new KeyboardEvent("keydown", { key: "Escape", code: "Escape", keyCode: 27, bubbles: true }));
    }, 80);

    if (wasReadOnly) {
      element.readOnly = true;
    }

    element.dispatchEvent(new Event("blur", { bubbles: true }));
    sendLog("DATE_FILLED_SUCCESS", element.id || element.name, dateStr, `type: ${type}`);
    return true;
  }

  async function fillField(targetId, value) {
    if (value === undefined || value === null) return false;

    // Find element by id, name, data-automation-id, or copilot-id
    const element =
      document.getElementById(targetId) ||
      document.querySelector(`[name="${targetId}"]`) ||
      document.querySelector(`[data-automation-id="${targetId}"]`) ||
      document.querySelector(`[data-qa="${targetId}"]`) ||
      document.querySelector(`[data-copilot-id="${targetId}"]`);

    if (!element) return false;

    const tagName = element.tagName.toLowerCase();
    const type = (element.type || "").toLowerCase();
    const label = findFieldLabel(element).toLowerCase();

    // Visual highlight on page
    element.scrollIntoView({ behavior: "smooth", block: "center" });
    element.style.outline = "2px solid #10b981";
    element.style.boxShadow = "0 0 10px rgba(16, 185, 129, 0.4)";
    setTimeout(() => {
      element.style.outline = "";
      element.style.boxShadow = "";
    }, 3000);

    // 1. Resume File Upload
    if (type === "file" || value === "__AUTO_UPLOAD_RESUME__" || /resume|cv|curriculum/i.test(label)) {
      return await attachResumeToElement(element);
    }

    // 2. Date Pickers & Calendar Fields (including split month/year dropdowns)
    const isDateField = type === "date" || type === "month" ||
      /\b(start\s*date|end\s*date|earliest|availability|graduation|birth\s*date|birthdate)\b/i.test(label) ||
      /\b(date|month|year)\b/i.test(label) ||
      /(yyyy|mm\/dd|dd\/mm|mm\/yy)/i.test(element.placeholder || "") ||
      /\b(month|year|date)\b/i.test(element.name || element.id || "");

    if (isDateField) {
      if (tagName === "select") {
        const parts = parseDateParts(value);
        if (parts && handleSelectDateField(element, parts)) {
          return true;
        }
      } else {
        const dateHandled = handleDateField(element, value);
        if (dateHandled) return true;
      }
    }

    // 3. Dropdown / Select
    if (tagName === "select") {
      const strVal = String(value).toLowerCase().trim();
      let matched = false;
      for (let i = 0; i < element.options.length; i++) {
        const optText = element.options[i].text.toLowerCase().trim();
        const optVal = element.options[i].value.toLowerCase().trim();
        if (optText === strVal || optVal === strVal || optText.includes(strVal) || strVal.includes(optText)) {
          element.selectedIndex = i;
          matched = true;
          break;
        }
      }
      if (!matched && element.options.length > 1) {
        element.selectedIndex = 1;
      }
      element.dispatchEvent(new Event("change", { bubbles: true }));
    }
    // 4. Radio Buttons
    else if (type === "radio") {
      const strVal = String(value).toLowerCase().trim();
      const labelText = findFieldLabel(element).toLowerCase();
      const elemVal = (element.value || "").toLowerCase();
      
      const shouldCheck = strVal === "yes" || strVal === "true" || labelText.includes(strVal) || elemVal === strVal;
      if (shouldCheck) {
        element.checked = true;
        element.click();
      }
    }
    // 5. Checkboxes
    else if (type === "checkbox") {
      const boolVal = typeof value === "boolean" ? value : ["yes", "true", "1"].includes(String(value).toLowerCase().trim());
      if (element.checked !== boolVal) {
        element.click();
      }
    }
    // 6. Regular Text / Email / Phone / Number / Textarea
    else {
      setNativeValue(element, String(value));
    }

    // Dispatch full suite of framework events so React/Vue/Angular dirty-check validates
    element.dispatchEvent(new Event("focus", { bubbles: true }));
    element.dispatchEvent(new Event("input", { bubbles: true }));
    element.dispatchEvent(new Event("change", { bubbles: true }));
    element.dispatchEvent(new Event("blur", { bubbles: true }));

    return true;
  }

  async function fillAllFields(matches) {
    let successCount = 0;
    for (const [id, value] of Object.entries(matches)) {
      if (await fillField(id, value)) {
        successCount++;
      }
    }
    return successCount;
  }

  // Broadcast detected fields to background worker and sidepanel
  function broadcastFields(scan) {
    if (!scan || !scan.fields || scan.fields.length === 0) return;
    try {
      chrome.runtime.sendMessage({
        action: "PAGE_FIELDS_DETECTED",
        payload: scan
      });
    } catch (e) {}
  }

  // Expose global hooks in isolated world for multi-frame scripting
  window.__jobCopilotScan = scanFormFields;
  window.__jobCopilotFill = fillAllFields;
  window.__jobCopilotHighlight = (id) => fillField(id, null);

  // Handle messages from Side Panel
  chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {
    if (request.action === "SCAN_FIELDS") {
      const result = scanFormFields();
      broadcastFields(result);
      sendResponse(result);
    } else if (request.action === "FILL_FIELDS") {
      fillAllFields(request.matches || {}).then((count) => {
        broadcastFields(scanFormFields());
        sendResponse({ success: true, count: count });
      });
      return true; // Keep channel open for async response
    } else if (request.action === "HIGHLIGHT_FIELD") {
      fillField(request.id, null);
      sendResponse({ success: true });
    }
    return true;
  });

  // ========================================================
  // In-Page Floating Co-Pilot Widget (Shadow DOM)
  // Ensures the user always sees the Co-Pilot directly on the page!
  // ========================================================
  function injectFloatingWidget() {
    // Avoid double injection
    if (document.getElementById("job-copilot-host")) return;

    const host = document.createElement("div");
    host.id = "job-copilot-host";
    host.style.all = "initial";
    document.body.appendChild(host);

    const shadow = host.attachShadow({ mode: "open" });

    const style = document.createElement("style");
    style.textContent = `
      .copilot-floating-btn {
        position: fixed;
        bottom: 24px;
        right: 24px;
        z-index: 2147483647;
        background: linear-gradient(135deg, #10b981 0%, #059669 100%);
        color: #ffffff;
        padding: 10px 16px;
        border-radius: 30px;
        font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
        font-size: 13px;
        font-weight: 700;
        box-shadow: 0 4px 18px rgba(16, 185, 129, 0.45);
        cursor: pointer;
        display: flex;
        align-items: center;
        gap: 8px;
        transition: all 0.25s ease;
        border: 2px solid rgba(255, 255, 255, 0.25);
        user-select: none;
      }
      .copilot-floating-btn:hover {
        transform: translateY(-2px) scale(1.03);
        box-shadow: 0 6px 24px rgba(16, 185, 129, 0.6);
      }
      .copilot-card {
        position: fixed;
        bottom: 74px;
        right: 24px;
        width: 310px;
        background: #0f172a;
        color: #f8fafc;
        border: 1px solid #334155;
        border-radius: 12px;
        box-shadow: 0 10px 30px rgba(0, 0, 0, 0.5);
        z-index: 2147483647;
        font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
        padding: 16px;
        display: none;
        flex-direction: column;
        gap: 12px;
        animation: fadeIn 0.2s ease;
      }
      .copilot-card.active {
        display: flex;
      }
      .copilot-card-header {
        display: flex;
        justify-content: space-between;
        align-items: center;
        border-bottom: 1px solid #334155;
        padding-bottom: 8px;
      }
      .copilot-card-title {
        font-size: 14px;
        font-weight: 700;
        color: #34d399;
        display: flex;
        align-items: center;
        gap: 6px;
      }
      .copilot-close {
        cursor: pointer;
        font-size: 16px;
        color: #94a3b8;
      }
      .copilot-close:hover {
        color: #ffffff;
      }
      .copilot-info {
        font-size: 12px;
        color: #cbd5e1;
        line-height: 1.4;
      }
      .copilot-action-btn {
        background: #10b981;
        color: #ffffff;
        border: none;
        border-radius: 8px;
        padding: 10px;
        font-size: 13px;
        font-weight: 600;
        cursor: pointer;
        display: flex;
        align-items: center;
        justify-content: center;
        gap: 6px;
        transition: background 0.2s;
      }
      .copilot-action-btn:hover {
        background: #059669;
      }
      .copilot-action-btn:disabled {
        opacity: 0.5;
        cursor: not-allowed;
      }
      .copilot-secondary-btn {
        background: #1e293b;
        color: #94a3b8;
        border: 1px solid #334155;
        border-radius: 8px;
        padding: 7px;
        font-size: 11px;
        font-weight: 500;
        cursor: pointer;
        text-align: center;
        transition: all 0.2s;
      }
      .copilot-secondary-btn:hover {
        color: #ffffff;
        background: #334155;
      }
      .copilot-status-pill {
        font-size: 11px;
        background: #1e293b;
        color: #38bdf8;
        padding: 4px 8px;
        border-radius: 6px;
        text-align: center;
      }
      @keyframes fadeIn {
        from { opacity: 0; transform: translateY(8px); }
        to { opacity: 1; transform: translateY(0); }
      }
    `;
    shadow.appendChild(style);

    const btn = document.createElement("div");
    btn.className = "copilot-floating-btn";
    btn.innerHTML = `<span>⚡</span> Job Co-Pilot`;
    shadow.appendChild(btn);

    const card = document.createElement("div");
    card.className = "copilot-card";
    card.innerHTML = `
      <div class="copilot-card-header">
        <span class="copilot-card-title">⚡ Job Co-Pilot</span>
        <span class="copilot-close" id="btn-close">✕</span>
      </div>
      <div class="copilot-status-pill" id="scan-pill">Scanning page fields...</div>
      <div class="copilot-info" id="card-desc">
        Click below to auto-populate this job application using your candidate profile.
      </div>
      <button class="copilot-action-btn" id="btn-quick-fill">
        <span>✨</span> 1-Click Auto-Fill Form
      </button>
      <button class="copilot-secondary-btn" id="btn-open-sidebar">
        Open Full Side Panel (Job Search & Settings)
      </button>
    `;
    shadow.appendChild(card);

    btn.addEventListener("click", () => {
      card.classList.toggle("active");
      if (card.classList.contains("active")) {
        const scan = scanFormFields();
        const pill = shadow.getElementById("scan-pill");
        pill.innerText = `${scan.fieldCount} form fields detected`;
        broadcastFields(scan);
      }
    });

    shadow.getElementById("btn-close").addEventListener("click", () => {
      card.classList.remove("active");
    });

    shadow.getElementById("btn-open-sidebar").addEventListener("click", () => {
      chrome.runtime.sendMessage({ action: "OPEN_SIDE_PANEL" });
    });

    async function fetchMatchesPayload(fields) {
      // 1. Try direct fetch first (instant on localhost/test page)
      try {
        const res = await fetch("http://127.0.0.1:8000/api/match-fields", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ fields })
        });
        if (res.ok) {
          return await res.json();
        }
      } catch (e) {
        // Direct fetch failed (e.g. Mixed Content block on HTTPS job portals)
      }

      // 2. Safe fallback via background service worker
      return new Promise((resolve) => {
        try {
          chrome.runtime.sendMessage({ action: "MATCH_FIELDS", payload: { fields } }, (response) => {
            resolve(response || { success: false, error: "No response from extension background worker" });
          });
        } catch (err) {
          resolve({ success: false, error: err.message });
        }
      });
    }

    shadow.getElementById("btn-quick-fill").addEventListener("click", async () => {
      const fillBtn = shadow.getElementById("btn-quick-fill");
      const pill = shadow.getElementById("scan-pill");
      fillBtn.disabled = true;
      fillBtn.innerHTML = `<span>⏳</span> Reasoning fields...`;
      pill.innerText = "DeepSeek AI reasoning fields...";
      pill.style.color = "#38bdf8";

      try {
        const scan = scanFormFields();
        if (scan.fieldCount === 0) {
          pill.innerText = "No form fields found on this page.";
          fillBtn.disabled = false;
          fillBtn.innerHTML = `<span>✨</span> 1-Click Auto-Fill Form`;
          return;
        }

        const response = await fetchMatchesPayload(scan.fields);
        if (!response || !response.success || !response.matches) {
          pill.innerText = `Error: ${response?.error || 'Bridge server offline'}`;
          pill.style.color = "#ef4444";
          return;
        }

        const count = await fillAllFields(response.matches);
        pill.innerText = `✓ Filled ${count} fields (inc. resume & dates)!`;
        pill.style.color = "#34d399";
        broadcastFields(scanFormFields());
      } catch (err) {
        pill.innerText = `Error: ${err.message}`;
        pill.style.color = "#ef4444";
      } finally {
        fillBtn.disabled = false;
        fillBtn.innerHTML = `<span>✨</span> 1-Click Auto-Fill Form`;
      }
    });
  }

  // Inject floating button when DOM is ready
  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", () => {
      injectFloatingWidget();
      setTimeout(() => broadcastFields(scanFormFields()), 600);
    });
  } else {
    injectFloatingWidget();
    setTimeout(() => broadcastFields(scanFormFields()), 600);
  }

  console.log("Job Co-Pilot Content Script active on:", window.location.hostname);
})();

