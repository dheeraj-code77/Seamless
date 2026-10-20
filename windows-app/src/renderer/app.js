// Seamless Windows Desktop Client Logic
let currentConfig = null;
let selectedTargetDevice = null;
let pollStatusInterval = null;
let pollDevicesInterval = null;
let qrRefreshInterval = null;

document.addEventListener("DOMContentLoaded", () => {
  if (window.lucide) lucide.createIcons();
  initApp();
});

async function initApp() {
  await fetchDeviceInfo();
  await fetchDevices();
  await fetchHistory();

  // The pairing QR code is shown as soon as the app opens and refreshes on its
  // own so the embedded address and token never go stale.
  await refreshPairingQr();

  // Polling loops
  pollDevicesInterval = setInterval(fetchDevices, 3000);
  pollStatusInterval = setInterval(fetchTransferStatus, 600);
  qrRefreshInterval = setInterval(refreshPairingQr, 60000);
}

// 0. Always-visible Pairing QR Code
async function refreshPairingQr() {
  try {
    const res = await fetch(`/api/pair/qr?refresh=${Date.now()}`);
    if (!res.ok) throw new Error(`QR request failed with status ${res.status}.`);
    const img = document.getElementById("pairing-qr-image");
    const blob = await res.blob();
    const objectUrl = URL.createObjectURL(blob);
    if (img.dataset.objectUrl) URL.revokeObjectURL(img.dataset.objectUrl);
    img.dataset.objectUrl = objectUrl;
    img.src = objectUrl;
    const address = document.getElementById("pairing-qr-address");
    if (address && currentConfig) {
      address.innerText = `${currentConfig.ip}:${currentConfig.port}`;
    }
  } catch (err) {
    console.error("Error refreshing pairing QR:", err);
  }
}

// 1. Fetch Local Device Info
async function fetchDeviceInfo() {
  try {
    const res = await fetch("/api/device/info");
    if (!res.ok) return;
    currentConfig = await res.json();

    document.getElementById("pc-name-display").innerText = currentConfig.device_name || "Laptop-Zenith";
    document.getElementById("win-ip-badge").innerText = `${currentConfig.ip} • Port ${currentConfig.port}`;
    document.getElementById("footer-port").innerText = currentConfig.port;
    document.getElementById("footer-download-dir").innerText = currentConfig.download_dir;
    document.getElementById("clipboardToggle").checked = currentConfig.clipboard_sync;
  } catch (err) {
    console.error("Error fetching device info:", err);
  }
}

// 2. Fetch Discovered & Paired Devices
async function fetchDevices() {
  try {
    const res = await fetch("/api/devices");
    if (!res.ok) return;
    const data = await res.json();
    const container = document.getElementById("devices-container");
    const badge = document.getElementById("active-device-badge");

    const paired = data.paired || {};
    const discovered = data.discovered || [];
    const pairedKeys = Object.keys(paired);

    badge.innerText = `${pairedKeys.length} Paired`;

    let html = "";

    // Render Paired Devices (Olive Moss Style)
    if (pairedKeys.length > 0) {
      pairedKeys.forEach(id => {
        const dev = paired[id];
        // Set as default target device if none selected
        if (!selectedTargetDevice) {
          selectedTargetDevice = { id, ...dev };
          updateDropzoneTarget(dev.name);
        }
        const isSelected = selectedTargetDevice && selectedTargetDevice.id === id;

        html += `
          <div onclick="selectDevice('${id}', '${dev.name}', '${dev.ip}', ${dev.port || 5173})"
               class="p-3 rounded-xl bg-moss-olive text-moss-text shadow-sm transition cursor-pointer border ${isSelected ? 'border-moss-dark ring-2 ring-moss-dark/40' : 'border-transparent'}">
            <div class="flex items-start justify-between">
              <div class="flex items-center gap-2.5">
                <div class="w-8 h-8 rounded-lg bg-[#7E9665] text-white flex items-center justify-center">
                  <i data-lucide="smartphone" class="w-4 h-4"></i>
                </div>
                <div>
                  <div class="text-xs font-bold text-moss-text">${escapeHtml(dev.name)}</div>
                  <div class="text-[10px] text-[#1E3A1C] font-semibold">Paired &bull; Local Wi-Fi</div>
                </div>
              </div>
              <span class="w-2 h-2 rounded-full bg-[#183119] mt-1"></span>
            </div>
            <div class="mt-2.5 pt-2 border-t border-[#7E9665]/40 flex items-center justify-between text-[10px] text-[#1E3A1C] font-medium">
              <span>IP: ${dev.ip}</span>
              <span class="font-bold text-[#183119]">${isSelected ? '● Target Device' : 'Ready'}</span>
            </div>
          </div>
        `;
      });
    }

    // Render Discovered but Unpaired Devices
    const unpaired = discovered.filter(d => !paired[d.device_id]);
    unpaired.forEach(dev => {
      html += `
        <div class="p-3 rounded-xl clean-inner-card hover:bg-white transition cursor-pointer">
          <div class="flex items-center justify-between">
            <div class="flex items-center gap-2.5">
              <div class="w-8 h-8 rounded-lg bg-[#E8E4D8] text-[#5C665D] flex items-center justify-center">
                <i data-lucide="${dev.device_type === 'android' ? 'smartphone' : 'laptop'}" class="w-4 h-4"></i>
              </div>
              <div>
                <div class="text-xs font-semibold text-forest-text">${escapeHtml(dev.device_name)}</div>
                <div class="text-[10px] text-[#7C877D]">Discovered &bull; ${dev.ip}</div>
              </div>
            </div>
            <button onclick="openPairingModal()" class="text-[10px] font-bold px-2.5 py-1 rounded-md bg-coral-rose text-white hover:opacity-90 transition shadow-xs">
              Pair
            </button>
          </div>
        </div>
      `;
    });

    if (pairedKeys.length === 0 && unpaired.length === 0) {
      html = `
        <div class="p-4 rounded-xl clean-inner-card text-center text-xs text-[#7C877D]">
          <i data-lucide="wifi" class="w-5 h-5 mx-auto mb-1.5 opacity-60 text-forest-accent"></i>
          Listening on Wi-Fi... Open Seamless on your phone to connect.
        </div>
      `;
    }

    container.innerHTML = html;
    if (window.lucide) lucide.createIcons();
  } catch (err) {
    console.error("Error fetching devices:", err);
  }
}

function selectDevice(id, name, ip, port) {
  selectedTargetDevice = { id, name, ip, port };
  updateDropzoneTarget(name);
  fetchDevices();
  showToast(`Selected ${name} as target device.`);
}

function updateDropzoneTarget(deviceName) {
  const title = document.getElementById("dropzone-title");
  if (title) {
    title.innerText = `Drag files here to send to ${deviceName}`;
  }
}

// 3. Real-Time Transfer Status Polling
async function fetchTransferStatus() {
  try {
    const res = await fetch("/api/transfer/status");
    if (!res.ok) return;
    const data = await res.json();
    const panel = document.getElementById("active-transfer-panel");

    if (data.status === "transferring" || data.status === "paused") {
      panel.classList.remove("hidden");
      document.getElementById("transfer-filename").innerText = data.filename || "File";
      document.getElementById("transfer-direction").innerText = data.direction || "Incoming";

      const mbSent = (data.bytes_transferred / (1024 * 1024)).toFixed(1);
      const mbTotal = (data.filesize / (1024 * 1024)).toFixed(1);
      document.getElementById("transfer-stats").innerText = `${mbSent} MB of ${mbTotal} MB`;
      document.getElementById("transfer-speed").innerText = `${data.speed_mbps || 0} MB/s`;
      document.getElementById("transfer-eta").innerText = `ETA: ${data.eta_seconds || 0}s`;

      const bar = document.getElementById("transfer-bar");
      bar.style.width = `${data.progress_percent || 0}%`;

      // Update pause icon
      const pauseIcon = document.querySelector("#transfer-pause-btn i");
      if (pauseIcon) {
        pauseIcon.setAttribute("data-lucide", data.is_paused ? "play" : "pause");
        if (window.lucide) lucide.createIcons();
      }
    } else if (data.status === "completed") {
      // Completed state
      document.getElementById("transfer-bar").style.width = "100%";
      document.getElementById("transfer-speed").innerText = "Completed";
      document.getElementById("transfer-eta").innerText = "Verified";
      setTimeout(() => {
        panel.classList.add("hidden");
        fetchHistory();
      }, 2500);
    } else if (data.status === "cancelled" || data.status === "failed") {
      document.getElementById("transfer-speed").innerText = data.status.toUpperCase();
      setTimeout(() => {
        panel.classList.add("hidden");
        fetchHistory();
      }, 2000);
    } else {
      panel.classList.add("hidden");
    }
  } catch (err) {
    // suppress poll errors
  }
}

// 4. Transfer Controls
async function toggleTransferPause() {
  try {
    const statusRes = await fetch("/api/transfer/status");
    const status = await statusRes.json();
    const endpoint = status.is_paused ? "/api/transfer/resume" : "/api/transfer/pause";
    await fetch(endpoint, { method: "POST" });
  } catch (err) {
    console.error(err);
  }
}

async function cancelActiveTransfer() {
  try {
    await fetch("/api/transfer/cancel", { method: "POST" });
    showToast("Transfer cancelled.");
  } catch (err) {
    console.error(err);
  }
}

// 5. Transfer History
async function fetchHistory() {
  try {
    const res = await fetch("/api/history");
    if (!res.ok) return;
    const data = await res.json();
    const list = document.getElementById("history-list");
    const items = data.history || [];

    if (items.length === 0) {
      list.innerHTML = `
        <div class="p-3 text-center text-xs text-[#7C877D] clean-inner-card rounded-xl">
          No transfer history recorded yet.
        </div>
      `;
      return;
    }

    let html = "";
    items.forEach(item => {
      const isIncoming = item.direction === "incoming";
      const iconName = isIncoming ? "arrow-down-left" : "arrow-up-right";
      const sizeMb = (item.filesize / (1024 * 1024)).toFixed(1);
      const timeStr = formatTimeAgo(item.timestamp);

      html += `
        <div class="p-2.5 rounded-xl clean-inner-card flex items-center justify-between text-xs hover:border-[#D5CFC2] transition shadow-xs">
          <div class="flex items-center gap-3 truncate">
            <div class="w-7 h-7 rounded-lg bg-[#D6E2CB] text-[#23421C] flex items-center justify-center shrink-0">
              <i data-lucide="${iconName}" class="w-3.5 h-3.5"></i>
            </div>
            <div class="truncate">
              <div class="font-bold text-forest-text truncate">${escapeHtml(item.filename)}</div>
              <div class="text-[10px] text-[#687469]">${isIncoming ? 'From' : 'To'} ${escapeHtml(item.peer_name || 'Device')} &bull; ${sizeMb} MB &bull; ${timeStr}</div>
            </div>
          </div>
          <div class="flex items-center gap-2 shrink-0">
            <span class="text-[10px] font-bold text-[#23421C] bg-moss-badge px-2 py-0.5 rounded capitalize">${item.status}</span>
            ${item.saved_path ? `<button onclick="openFolderAtPath('${escapeJs(item.saved_path)}')" class="text-[#7C877D] hover:text-forest-text p-1" title="Open file"><i data-lucide="external-link" class="w-3.5 h-3.5"></i></button>` : ''}
          </div>
        </div>
      `;
    });

    list.innerHTML = html;
    if (window.lucide) lucide.createIcons();
  } catch (err) {
    console.error("Error loading history:", err);
  }
}

async function clearHistoryRecords() {
  try {
    await fetch("/api/history/clear", { method: "POST" });
    fetchHistory();
    showToast("History cleared.");
  } catch (err) {
    console.error(err);
  }
}

// 6. File Drop & Sending
function triggerFilePicker() {
  document.getElementById("file-input").click();
}

function handleDragOver(e) {
  e.preventDefault();
  e.stopPropagation();
  document.getElementById("dropzone").classList.add("ring-2", "ring-forest-accent");
}

function handleDragLeave(e) {
  e.preventDefault();
  e.stopPropagation();
  document.getElementById("dropzone").classList.remove("ring-2", "ring-forest-accent");
}

function handleDrop(e) {
  e.preventDefault();
  e.stopPropagation();
  document.getElementById("dropzone").classList.remove("ring-2", "ring-forest-accent");
  if (e.dataTransfer && e.dataTransfer.files.length > 0) {
    sendFilesToTarget(e.dataTransfer.files);
  }
}

function handleFileSelect(e) {
  if (e.target.files && e.target.files.length > 0) {
    sendFilesToTarget(e.target.files);
  }
}

async function sendFilesToTarget(files) {
  if (!selectedTargetDevice) {
    showToast("Please pair or select a target phone from Connected Devices first.");
    openPairingModal();
    return;
  }

  showToast(`Preparing to send ${files.length} file(s) to ${selectedTargetDevice.name}...`);

  for (let i = 0; i < files.length; i++) {
    const file = files[i];
    await sendSingleFile(file, selectedTargetDevice);
  }
}

async function sendSingleFile(file, target) {
  const targetUrl = `http://${target.ip}:${target.port || 5173}/api/transfer/send`;
  const headers = {
    "X-Seamless-Filename": encodeURIComponent(file.name),
    "X-Seamless-Filesize": file.size.toString(),
    "X-Seamless-Sender-Id": currentConfig?.device_id || "win-client",
    "X-Seamless-Sender-Name": currentConfig?.device_name || "Windows Laptop",
    "X-Seamless-Token": target.token || ""
  };

  try {
    // Show active transfer immediately
    const panel = document.getElementById("active-transfer-panel");
    panel.classList.remove("hidden");
    document.getElementById("transfer-filename").innerText = file.name;
    document.getElementById("transfer-direction").innerText = "Outgoing";
    document.getElementById("transfer-stats").innerText = `Sending to ${target.name}...`;

    const res = await fetch(targetUrl, {
      method: "POST",
      headers: headers,
      body: file
    });

    if (res.ok) {
      showToast(`Successfully sent ${file.name} to ${target.name}!`);
      fetchHistory();
    } else {
      showToast(`Failed to send ${file.name}: Peer returned error.`);
    }
  } catch (err) {
    console.error("File send error:", err);
    showToast(`Connection to ${target.name} (${target.ip}) timed out.`);
  }
}

// 7. Pairing Modal
async function openPairingModal() {
  const modal = document.getElementById("pairing-modal");
  modal.classList.remove("hidden");
  modal.classList.add("flex");
  await requestNewPin();
}

function closePairingModal() {
  const modal = document.getElementById("pairing-modal");
  modal.classList.add("hidden");
  modal.classList.remove("flex");
}

async function requestNewPin() {
  try {
    const res = await fetch("/api/pair/request", { method: "POST" });
    if (!res.ok) throw new Error(`Pairing PIN request failed with status ${res.status}.`);
    const data = await res.json();
    const pin = data.pin.toString();
    document.getElementById("pairing-qr-code").src = `/api/pair/qr?refresh=${Date.now()}`;
    const container = document.getElementById("pin-boxes-container");
    container.innerHTML = `
      <span class="w-10 h-12 rounded-xl bg-cream-100 border border-[#D5CFC2] flex items-center justify-center text-xl font-mono font-bold text-forest-accent shadow-xs">${pin[0]}</span>
      <span class="w-10 h-12 rounded-xl bg-cream-100 border border-[#D5CFC2] flex items-center justify-center text-xl font-mono font-bold text-forest-accent shadow-xs">${pin[1]}</span>
      <span class="w-10 h-12 rounded-xl bg-cream-100 border border-[#D5CFC2] flex items-center justify-center text-xl font-mono font-bold text-forest-accent shadow-xs">${pin[2]}</span>
      <span class="text-[#8F8A7D] font-bold">&ndash;</span>
      <span class="w-10 h-12 rounded-xl bg-cream-100 border border-[#D5CFC2] flex items-center justify-center text-xl font-mono font-bold text-forest-accent shadow-xs">${pin[3]}</span>
      <span class="w-10 h-12 rounded-xl bg-cream-100 border border-[#D5CFC2] flex items-center justify-center text-xl font-mono font-bold text-forest-accent shadow-xs">${pin[4]}</span>
      <span class="w-10 h-12 rounded-xl bg-cream-100 border border-[#D5CFC2] flex items-center justify-center text-xl font-mono font-bold text-forest-accent shadow-xs">${pin[5]}</span>
    `;
  } catch (err) {
    console.error("Error requesting PIN:", err);
    showToast("Could not prepare secure pairing. Check the local server and try again.");
  }
}

// 8. Clipboard Toggle
async function toggleClipboardSync(checkbox) {
  try {
    await fetch("/api/settings/clipboard", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ enabled: checkbox.checked })
    });
    showToast(checkbox.checked ? "Clipboard Sync enabled." : "Clipboard Sync disabled.");
  } catch (err) {
    console.error(err);
  }
}

// 9. Folder Actions
async function openDownloadFolder() {
  try {
    const res = await fetch("/api/settings/open_folder", { method: "POST" });
    const data = await res.json();
    if (data.success) {
      showToast(`Transfer folder opened: ${data.download_dir || currentConfig?.download_dir || ""}`);
    } else {
      showToast(data.error || "Could not open the transfer folder.");
    }
  } catch (err) {
    console.error(err);
    showToast(`Files are stored at: ${currentConfig?.download_dir || ""}`);
  }
}

function openFolderAtPath(path) {
  showToast(`File saved: ${path}`);
}

// 10. Helpers
function showToast(msg) {
  const toast = document.getElementById("toast");
  const toastMsg = document.getElementById("toast-message");
  toastMsg.innerText = msg;
  toast.classList.remove("translate-y-20", "opacity-0");
  setTimeout(() => {
    toast.classList.add("translate-y-20", "opacity-0");
  }, 3500);
}

function formatTimeAgo(ts) {
  const sec = Math.floor((Date.now() / 1000) - ts);
  if (sec < 60) return "just now";
  const min = Math.floor(sec / 60);
  if (min < 60) return `${min}m ago`;
  const hr = Math.floor(min / 60);
  return `${hr}h ago`;
}

function escapeHtml(str) {
  return (str || "").replace(/[&<>'"]/g, tag => ({
    '&': '&amp;',
    '<': '&lt;',
    '>': '&gt;',
    "'": '&#39;',
    '"': '&quot;'
  }[tag] || tag));
}

function escapeJs(str) {
  return (str || "").replace(/\\/g, '\\\\').replace(/'/g, "\\'");
}
