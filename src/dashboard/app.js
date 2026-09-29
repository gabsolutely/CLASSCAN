// ── State ───────────────────────────────────────────────────────────────
const ZONES     = ["Q1", "Q2", "Q3", "Q4"];
const MAX_SEATS = 10;  // per zone — must match Pi config.py

let polling     = false;
let pollTimer   = null;
let lastCount   = null;

// ── Init zone grid ──────────────────────────────────────────────────────
function initZoneGrid() {
  const grid = document.getElementById("zone-grid");
  if (!grid) return;
  grid.innerHTML = "";
  ZONES.forEach(z => {
    grid.innerHTML += `
      <div class="zone-cell" id="zone-${z}">
        <div class="zone-name">${z}</div>
        <div class="zone-count" id="zone-count-${z}">—</div>
        <div class="zone-bar"><div class="zone-bar-fill" id="zone-bar-${z}"></div></div>
      </div>`;
  });
}

// ── Logging ─────────────────────────────────────────────────────────────
function log(msg, type = "") {
  const scroll = document.getElementById("log-scroll");
  if (!scroll) return;
  const ts     = new Date().toLocaleTimeString("en-US", { hour12: false });
  const entry  = document.createElement("div");
  entry.className = `log-entry ${type}`;
  entry.innerHTML = `<span class="ts">${ts}</span>${msg}`;
  scroll.appendChild(entry);
  scroll.scrollTop = scroll.scrollHeight;
  // Cap log at 200 entries
  while (scroll.children.length > 200) {
    scroll.removeChild(scroll.firstChild);
  }
}

// ── Status pill ─────────────────────────────────────────────────────────
function setStatus(state, label) {
  const pill = document.getElementById("status-pill");
  const text = document.getElementById("status-text");
  if (pill && text) {
    pill.className = `status-pill ${state}`;
    text.textContent = label;
  }
}

// ── Count update ────────────────────────────────────────────────────────
function updateCount(n) {
  const el = document.getElementById("count-display");
  if (!el) return;

  if (n !== lastCount) {
    el.textContent = n;
    el.classList.remove("count-pop");
    void el.offsetWidth;  // trigger DOM reflow for animation restart
    el.classList.add("count-pop");
    log(`Headcount updated → ${n}`, "ok");
    lastCount = n;
  }

  const footerTs = document.getElementById("footer-ts");
  if (footerTs) {
    footerTs.textContent = "Last update: " + new Date().toLocaleTimeString();
  }
}

// ── Snapshot update ─────────────────────────────────────────────────────
function updateSnapshot(b64, timestamp) {
  const img = document.getElementById("snapshot-img");
  const ph  = document.getElementById("snapshot-placeholder");
  if (!img || !ph) return;

  img.src = "data:image/jpeg;base64," + b64;
  img.style.display = "block";
  ph.style.display  = "none";

  const timeEl = document.getElementById("snapshot-time");
  const dimsEl = document.getElementById("snapshot-dims");
  if (timeEl) timeEl.textContent = timestamp;
  if (dimsEl) dimsEl.textContent = "JPEG";
}

// ── Motion indicator ─────────────────────────────────────────────────────
function updateMotion(active) {
  const badge = document.getElementById("motion-badge");
  if (!badge) return;
  badge.style.display = active ? "inline-flex" : "none";
}

// ── Watchdog / System Health ─────────────────────────────────────────────
function updateWatchdog(wd) {
  if (!wd) return;

  const components = [
    { key: "camera", id: "camera" },
    { key: "ai",     id: "ai"     },
    { key: "serial", id: "serial" },
  ];

  components.forEach(({ key, id }) => {
    const ok     = wd[key];
    const dotEl  = document.getElementById(`wd-dot-${id}`);
    const statEl = document.getElementById(`wd-status-${id}`);
    const itemEl = document.getElementById(`wd-${id}`);
    if (!dotEl || !statEl || !itemEl) return;

    dotEl.className    = `wd-dot ${ok ? "ok" : "error"}`;
    statEl.textContent = ok ? "OK" : "ERROR";
    itemEl.className   = `wd-item ${ok ? "wd-ok" : "wd-error"}`;
  });

  // Render alert messages
  const alertsEl = document.getElementById("wd-alerts");
  if (!alertsEl) return;
  alertsEl.innerHTML = "";
  (wd.alerts || []).forEach(msg => {
    const div = document.createElement("div");
    div.className = "wd-alert-msg";
    div.innerHTML = `<span class="wd-alert-icon">⚠️</span>${msg}`;
    alertsEl.appendChild(div);
  });
}

// ── Zone update ─────────────────────────────────────────────────────────
function updateZones(zones) {
  if (!zones) return;
  Object.entries(zones).forEach(([name, count]) => {
    const countEl = document.getElementById(`zone-count-${name}`);
    const barEl   = document.getElementById(`zone-bar-${name}`);
    if (countEl) {
      countEl.textContent = count;
    }
    if (barEl) {
      barEl.style.width = Math.min(100, (count / MAX_SEATS) * 100) + "%";
    }
  });
}

// ── Polling loop ────────────────────────────────────────────────────────
async function poll() {
  const urlInput = document.getElementById("pi-url");
  if (!urlInput) return;

  const url = urlInput.value.replace(/\/$/, "");
  try {
    const res = await fetch(`${url}/status`, { signal: AbortSignal.timeout(3000) });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const data = await res.json();
    setStatus("connected", "Connected");

    if (data.count !== undefined) updateCount(data.count);
    if (data.zones)               updateZones(data.zones);
    updateMotion(!!data.motion);
    if (data.watchdog)            updateWatchdog(data.watchdog);

    // If live MJPEG stream is active, update metadata; if stream broke/empty, fallback to base64 snapshot
    const img = document.getElementById("snapshot-img");
    if (!img || !img.src || img.src.startsWith("data:") || img.naturalWidth === 0) {
      if (data.snapshot) updateSnapshot(data.snapshot, data.timestamp || "—");
    } else {
      const timeEl = document.getElementById("snapshot-time");
      const dimsEl = document.getElementById("snapshot-dims");
      if (timeEl && data.timestamp) timeEl.textContent = data.timestamp;
      if (dimsEl && data.fps !== undefined) dimsEl.textContent = `${data.fps} FPS`;
    }

  } catch (err) {
    setStatus("error", "Connection error");
    log(`Poll error: ${err.message}`, "err");
  }

  if (polling) {
    pollTimer = setTimeout(poll, 2000);
  }
}

function togglePolling() {
  const btn = document.getElementById("connect-btn");
  const urlInput = document.getElementById("pi-url");
  const url = urlInput ? urlInput.value.replace(/\/$/, "") : "";
  const img = document.getElementById("snapshot-img");
  const ph  = document.getElementById("snapshot-placeholder");

  if (!polling) {
    polling = true;
    if (btn) btn.textContent = "Disconnect";
    log("Connecting to Pi 3B…");

    // Connect directly to live MJPEG stream for real-time video
    if (img && ph && url) {
      img.src = `${url}/stream`;
      img.style.display = "block";
      ph.style.display  = "none";
      img.onerror = () => {
        log("MJPEG stream error, falling back to snapshot mode", "err");
      };
    }

    poll();
  } else {
    polling = false;
    clearTimeout(pollTimer);
    if (btn) btn.textContent = "Connect";
    setStatus("", "Disconnected");
    log("Disconnected.");

    if (img && ph) {
      img.src = "";
      img.style.display = "none";
      ph.style.display  = "flex";
    }
  }
}

// ── Command send ────────────────────────────────────────────────────────
async function sendCommand(cmd) {
  const urlInput = document.getElementById("pi-url");
  if (!urlInput) return;

  const url = urlInput.value.replace(/\/$/, "");
  log(`→ CMD: ${cmd}`);

  // Update mode button active state immediately
  const btnSweep = document.getElementById("btn-sweep");
  const btnZone  = document.getElementById("btn-zone");

  if (cmd === "MODE_SWEEP") {
    btnSweep?.classList.add("active");
    btnZone?.classList.remove("active");
  } else if (cmd === "MODE_ZONE") {
    btnZone?.classList.add("active");
    btnSweep?.classList.remove("active");
  }

  try {
    const res = await fetch(`${url}/command`, {
      method:  "POST",
      headers: { "Content-Type": "application/json" },
      body:    JSON.stringify({ command: cmd }),
      signal:  AbortSignal.timeout(3000),
    });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    log(`← ACK: ${cmd}`, "ok");
  } catch (err) {
    log(`Command failed: ${err.message}`, "err");
  }
}

// ── Event Listeners & Boot ──────────────────────────────────────────────
document.addEventListener("DOMContentLoaded", () => {
  initZoneGrid();

  // Auto-detect current origin when served from the Pi HTTP server
  const urlInput = document.getElementById("pi-url");
  if (urlInput && window.location.protocol.startsWith("http")) {
    urlInput.value = window.location.origin;
  }

  // Bind Connect button
  const connectBtn = document.getElementById("connect-btn");
  if (connectBtn) {
    connectBtn.addEventListener("click", togglePolling);
  }

  // Bind Mode buttons
  document.getElementById("btn-sweep")?.addEventListener("click", () => sendCommand("MODE_SWEEP"));
  document.getElementById("btn-zone")?.addEventListener("click", () => sendCommand("MODE_ZONE"));

  // Bind Zone Check buttons
  document.querySelectorAll(".zone-cmd-btn").forEach(btn => {
    btn.addEventListener("click", () => {
      const zone = btn.getAttribute("data-zone");
      if (zone) {
        sendCommand(`ZONE_${zone}`);
      }
    });
  });

  // ── Manual Light Control (placeholder) ──────────────────────────
  const lightToggle     = document.getElementById("light-toggle");
  const lightStateLabel = document.getElementById("light-state-label");
  const lightBrightness = document.getElementById("light-brightness");
  const lightBrightVal  = document.getElementById("light-brightness-val");
  const sensorState     = document.getElementById("sensor-state");

  if (lightToggle && lightStateLabel) {
    lightToggle.addEventListener("change", () => {
      const on = lightToggle.checked;
      lightStateLabel.textContent = on ? "ON" : "OFF";
      lightStateLabel.classList.toggle("on", on);
      if (sensorState) sensorState.textContent = on ? "ON" : "OFF";
      log(`[Light] Power → ${on ? "ON" : "OFF"}`, on ? "ok" : "");
    });
  }

  if (lightBrightness && lightBrightVal) {
    lightBrightness.addEventListener("input", () => {
      lightBrightVal.textContent = lightBrightness.value + "%";
    });
    lightBrightness.addEventListener("change", () => {
      log(`[Light] Brightness → ${lightBrightness.value}%`);
    });
  }

  log("CLASSCAN dashboard ready. Click Connect to start monitoring.");
});

