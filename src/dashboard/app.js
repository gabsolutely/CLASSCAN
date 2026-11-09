// ── State ───────────────────────────────────────────────────────────────
const ZONES     = ["Q1", "Q2", "Q3", "Q4"];
const MAX_SEATS = 10;  // per zone — must match Pi config.py

let polling        = false;
let pollTimer      = null;
let lastCount      = null;
let streamMode     = false;
let streamFailed   = false;
let currentMode    = "SWEEP";  // tracks active detection mode
let heatmapEnabled = false;    // heatmap overlay toggle

// ── Jet Colormap (matches OpenCV COLORMAP_JET) ───────────────────────────
// Maps a normalised value [0..1] → [R, G, B] using the classic jet ramp.
function jetColor(t) {
  // 4-segment piecewise linear interpolation matching matplotlib/OpenCV jet
  const r = Math.max(0, Math.min(1, 1.5 - Math.abs(4 * t - 3)));
  const g = Math.max(0, Math.min(1, 1.5 - Math.abs(4 * t - 2)));
  const b = Math.max(0, Math.min(1, 1.5 - Math.abs(4 * t - 1)));
  return [Math.round(r * 255), Math.round(g * 255), Math.round(b * 255)];
}

// ── Heatmap Render ────────────────────────────────────────────────────────
// Decodes a base64 uint8 104x104 raw byte buffer and renders it onto the
// heatmap canvas using the jet colormap at full canvas resolution.
function renderHeatmap(b64) {
  const canvas = document.getElementById("heatmap-canvas");
  if (!canvas || !heatmapEnabled) return;

  const H = 104, W = 104;
  const raw   = atob(b64);
  const bytes = new Uint8Array(raw.length);
  for (let i = 0; i < raw.length; i++) bytes[i] = raw.charCodeAt(i);

  // Upscale 104x104 → canvas display size via ImageData then drawImage
  const tmpCanvas = document.createElement("canvas");
  tmpCanvas.width  = W;
  tmpCanvas.height = H;
  const ctx2 = tmpCanvas.getContext("2d");
  const imgData = ctx2.createImageData(W, H);

  for (let i = 0; i < H * W; i++) {
    const t = bytes[i] / 255;
    const [r, g, bl] = jetColor(t);
    // Fully transparent where value is very low (background suppression)
    const alpha = t < 0.08 ? 0 : Math.round(t * 220);
    imgData.data[i * 4 + 0] = r;
    imgData.data[i * 4 + 1] = g;
    imgData.data[i * 4 + 2] = bl;
    imgData.data[i * 4 + 3] = alpha;
  }
  ctx2.putImageData(imgData, 0, 0);

  // Stretch the 104x104 tile to fill the canvas (smooth interpolation)
  const ctx = canvas.getContext("2d");
  ctx.imageSmoothingEnabled = true;
  ctx.imageSmoothingQuality = "high";
  canvas.width  = canvas.offsetWidth  || 640;
  canvas.height = canvas.offsetHeight || 480;
  ctx.clearRect(0, 0, canvas.width, canvas.height);
  ctx.drawImage(tmpCanvas, 0, 0, canvas.width, canvas.height);
}

// ── Heatmap Toggle ────────────────────────────────────────────────────────
function toggleHeatmap() {
  heatmapEnabled = !heatmapEnabled;
  const canvas    = document.getElementById("heatmap-canvas");
  const stateEl   = document.getElementById("heatmap-toggle-state");
  const btn       = document.getElementById("btn-heatmap");
  if (canvas)  canvas.style.display  = heatmapEnabled ? "block" : "none";
  if (stateEl) stateEl.textContent   = heatmapEnabled ? "ON"    : "OFF";
  if (btn)     btn.classList.toggle("heatmap-active", heatmapEnabled);
  if (!heatmapEnabled && canvas) {
    const ctx = canvas.getContext("2d");
    ctx.clearRect(0, 0, canvas.width, canvas.height);
  }
  log(`Heatmap overlay ${heatmapEnabled ? "enabled" : "disabled"}`);
}

// In-memory log store for CSV export
// Each entry: { ts: "HH:MM:SS", type: ""|"ok"|"err", message: string }
const _eventLog = [];

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
  // Cap DOM log at 200 entries
  while (scroll.children.length > 200) {
    scroll.removeChild(scroll.firstChild);
  }
  // Mirror to in-memory store (uncapped — full session history for export)
  _eventLog.push({ ts, type: type || "info", message: msg });
}

// ── Download event log as CSV ─────────────────────────────────────────────
function downloadEventLog() {
  if (_eventLog.length === 0) {
    log("Event log is empty — nothing to download.", "err");
    return;
  }

  const date    = new Date().toISOString().slice(0, 19).replace(/:/g, "-");
  const header  = "Timestamp,Type,Message\n";
  const rows    = _eventLog.map(e => {
    // Escape double-quotes and wrap fields that may contain commas
    const safe = s => `"${String(s).replace(/"/g, "\"\"")}"`;
    return `${safe(e.ts)},${safe(e.type)},${safe(e.message)}`;
  }).join("\n");

  const blob = new Blob([header + rows], { type: "text/csv;charset=utf-8;" });
  const url  = URL.createObjectURL(blob);
  const a    = document.createElement("a");
  a.href     = url;
  a.download = `classcan_eventlog_${date}.csv`;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);

  log(`Event log exported (${_eventLog.length} entries) → ${a.download}`, "ok");
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

    // Serial: show "Simulated" rather than "ERROR" when ESP32 is absent
    const label = (key === "serial" && !ok) ? "Simulated" : (ok ? "OK" : "ERROR");
    dotEl.className    = `wd-dot ${ok ? "ok" : "error"}`;
    statEl.textContent = label;
    itemEl.className   = `wd-item ${ok ? "wd-ok" : "wd-error"}`;
  });

  // LDR live readout in the sensor-state element
  const sensorState = document.getElementById("sensor-state");
  if (sensorState) {
    const ldrRaw = wd.ldr;
    const illum  = wd.illumination;
    if (ldrRaw !== null && ldrRaw !== undefined) {
      sensorState.textContent = illum ? `ON (LDR: ${ldrRaw})` : `OFF (LDR: ${ldrRaw})`;
    }
  }

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

// ── Turret Position update ───────────────────────────────────────────────
function updateTurret(panPct, moving) {
  const marker = document.getElementById("turret-marker");
  const quadEl = document.getElementById("turret-quadrant");
  const pctEl  = document.getElementById("turret-pct");
  const movEl  = document.getElementById("turret-moving");

  const clampedPct = Math.max(0, Math.min(100, panPct));
  if (marker) marker.style.left = clampedPct + "%";
  if (quadEl) quadEl.textContent = "Q" + Math.min(4, Math.max(1, Math.floor(clampedPct / 25) + 1));
  if (pctEl)  pctEl.textContent  = clampedPct + "%";
  if (movEl)  {
    movEl.textContent = moving ? "sweeping" : "idle";
    movEl.className = "turret-status " + (moving ? "moving" : "");
  }
}

// ── Mode UI update ───────────────────────────────────────────────────────
// Sweep  = density model only, no zone display, no servo scan needed.
// Zone   = per-quadrant servo scan; requires tilt wired to GPIO 13.
function updateModeUI(mode) {
  if (mode === currentMode) return;
  currentMode = mode;

  const btnSweep     = document.getElementById("btn-sweep");
  const btnZone      = document.getElementById("btn-zone");
  const hintSweep    = document.getElementById("mode-hint-sweep");
  const hintZone     = document.getElementById("mode-hint-zone");
  const zoneGrid     = document.getElementById("zone-grid");
  const zoneTag      = document.getElementById("zone-mode-tag");
  const zoneSweepMsg = document.getElementById("zone-sweep-msg");

  if (mode === "SWEEP") {
    btnSweep?.classList.add("active");
    btnZone?.classList.remove("active");
    if (hintSweep)    hintSweep.style.display    = "";
    if (hintZone)     hintZone.style.display     = "none";
    if (zoneGrid)     zoneGrid.style.display     = "none";
    if (zoneSweepMsg) zoneSweepMsg.style.display = "";
    if (zoneTag) {
      zoneTag.textContent = "SWEEP \u2014 zones inactive";
      zoneTag.className   = "zone-mode-tag";
    }
    // Reset stale zone values so they don\u2019t show when switching back
    ZONES.forEach(z => {
      const c = document.getElementById(`zone-count-${z}`);
      const b = document.getElementById(`zone-bar-${z}`);
      if (c) c.textContent = "\u2014";
      if (b) b.style.width = "0%";
    });
  } else {
    // ZONE_CHECK
    btnZone?.classList.add("active");
    btnSweep?.classList.remove("active");
    if (hintZone)     hintZone.style.display     = "";
    if (hintSweep)    hintSweep.style.display    = "none";
    if (zoneGrid)     zoneGrid.style.display     = "";
    if (zoneSweepMsg) zoneSweepMsg.style.display = "none";
    if (zoneTag) {
      zoneTag.textContent = "ZONE CHECK \u2014 per-quadrant";
      zoneTag.className   = "zone-mode-tag zone-mode-tag-active";
    }
  }
}

// ── Polling loop ────────────────────────────────────────────────────────
async function poll() {
  const urlInput = document.getElementById("pi-url");
  if (!urlInput) return;

  const url = urlInput.value.replace(/\/$/, "");
  try {
    const res = await fetch(`${url}/status`, { signal: AbortSignal.timeout(6000) });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const data = await res.json();
    setStatus("connected", "Connected");

    if (data.count !== undefined) updateCount(data.count);
    if (data.zones)               updateZones(data.zones);
    if (data.mode)                updateModeUI(data.mode);
    if (data.pan_pct !== undefined) updateTurret(data.pan_pct, !!data.pan_moving);
    updateMotion(!!data.motion);
    if (data.watchdog)            updateWatchdog(data.watchdog);
    if (data.heatmap)             renderHeatmap(data.heatmap);

    // Only fall back to base64 snapshot if the live MJPEG stream failed or was disabled
    if (streamFailed) {
      if (data.snapshot) updateSnapshot(data.snapshot, data.timestamp || "—");
    } else {
      const timeEl = document.getElementById("snapshot-time");
      const dimsEl = document.getElementById("snapshot-dims");
      if (timeEl && data.timestamp) timeEl.textContent = data.timestamp;
      if (dimsEl && data.fps !== undefined) dimsEl.textContent = `${data.fps} FPS (Live)`;
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
    streamMode = true;
    streamFailed = false;
    if (btn) btn.textContent = "Disconnect";
    log("Connecting to Pi 3B…");

    // Connect directly to live MJPEG stream for real-time video
    if (img && ph && url) {
      img.onerror = () => {
        if (!streamFailed) {
          streamFailed = true;
          log("MJPEG stream error, falling back to snapshot mode", "err");
        }
      };
      img.onload = () => {
        streamFailed = false;
        img.style.display = "block";
        ph.style.display  = "none";
      };
      img.src = `${url}/stream`;
      img.style.display = "block";
      ph.style.display  = "none";
    }

    poll();
  } else {
    polling = false;
    streamMode = false;
    streamFailed = false;
    clearTimeout(pollTimer);
    if (btn) btn.textContent = "Connect";
    setStatus("", "Disconnected");
    log("Disconnected.");

    if (img && ph) {
      img.onerror = null;
      img.onload  = null;
      img.src = "";
      img.style.display = "none";
      ph.style.display  = "flex";
    }

    // Clear stale metadata
    const timeEl = document.getElementById("snapshot-time");
    const dimsEl = document.getElementById("snapshot-dims");
    if (timeEl) timeEl.textContent = "—";
    if (dimsEl) dimsEl.textContent = "—";
  }
}

// ── Command send ────────────────────────────────────────────────────────
async function sendCommand(cmd) {
  const urlInput = document.getElementById("pi-url");
  if (!urlInput) return;

  const url = urlInput.value.replace(/\/$/, "");
  log(`→ CMD: ${cmd}`);

  // Update mode UI immediately on button click (don't wait for next poll)
  if (cmd === "MODE_SWEEP") updateModeUI("SWEEP");
  else if (cmd === "MODE_ZONE") updateModeUI("ZONE_CHECK");

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

  // Bind Heatmap toggle
  document.getElementById("btn-heatmap")?.addEventListener("click", toggleHeatmap);

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

  // Bind Download Log button
  const downloadBtn = document.getElementById("btn-download-log");
  if (downloadBtn) {
    downloadBtn.addEventListener("click", downloadEventLog);
  }

  log("CLASSCAN dashboard ready. Click Connect to start monitoring.");
});

