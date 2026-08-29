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
    if (data.snapshot)            updateSnapshot(data.snapshot, data.timestamp || "—");
    if (data.zones)               updateZones(data.zones);

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
  if (!polling) {
    polling = true;
    if (btn) btn.textContent = "Disconnect";
    log("Connecting to Pi 3B…");
    poll();
  } else {
    polling = false;
    clearTimeout(pollTimer);
    if (btn) btn.textContent = "Connect";
    setStatus("", "Disconnected");
    log("Disconnected.");
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

  log("CLASSCAN dashboard ready. Click Connect to start monitoring.");
});

