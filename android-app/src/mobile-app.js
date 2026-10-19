// Seamless Android Mobile Client Logic
let laptopIp = window.location.hostname || "127.0.0.1";
let laptopPort = window.location.port || "5173";
let authToken = localStorage.getItem("seamless_token") || "";
let pairedPcName = localStorage.getItem("seamless_pc_name") || "Windows Laptop";
let mobileHistory = JSON.parse(localStorage.getItem("seamless_mobile_history") || "[]");

document.addEventListener("DOMContentLoaded", () => {
  if (window.lucide) lucide.createIcons();
  updateClock();
  setInterval(updateClock, 1000);
  initMobileApp();
});

function updateClock() {
  const now = new Date();
  const hrs = String(now.getHours()).padStart(2, '0');
  const mins = String(now.getMinutes()).padStart(2, '0');
  const clock = document.getElementById("mobile-clock");
  if (clock) clock.innerText = `${hrs}:${mins}`;
}

async function initMobileApp() {
  // If user entered a manual IP in localStorage, use it
  const savedIp = localStorage.getItem("seamless_laptop_ip");
  if (savedIp) laptopIp = savedIp;

  document.getElementById("manual-laptop-ip").value = laptopIp;
  document.getElementById("target-pc-ip").innerText = laptopIp;

  await checkLaptopConnection();
  renderMobileHistory();
  setInterval(checkLaptopConnection, 4000);
}

// 1. Check Connection to Windows Laptop
async function checkLaptopConnection() {
  try {
    const res = await fetch(`http://${laptopIp}:${laptopPort}/api/device/info`, {
      signal: AbortSignal.timeout(2500)
    });
    if (res.ok) {
      const data = await res.json();
      document.getElementById("target-pc-name").innerText = data.device_name || "Windows Laptop";
      document.getElementById("target-pc-status").innerText = "Connected • Low Latency";
      document.getElementById("target-pc-dot").className = "w-1.5 h-1.5 rounded-full bg-[#183119]";
      document.getElementById("mobile-conn-tag").innerText = "Connected";
      document.getElementById("mobile-conn-tag").className = "text-[9px] px-1.5 py-0.2 rounded-full bg-moss-badge text-[#23421C] font-semibold";
      pairedPcName = data.device_name;
      localStorage.setItem("seamless_pc_name", pairedPcName);
      return true;
    }
  } catch (err) {
    document.getElementById("target-pc-name").innerText = "Searching for Laptop...";
    document.getElementById("target-pc-status").innerText = "Not Connected";
    document.getElementById("target-pc-dot").className = "w-1.5 h-1.5 rounded-full bg-rose-500";
    document.getElementById("mobile-conn-tag").innerText = "Offline";
    document.getElementById("mobile-conn-tag").className = "text-[9px] px-1.5 py-0.2 rounded-full bg-rose-100 text-rose-700 font-semibold";
  }
  return false;
}

// 2. File Selection & Upload
function triggerFilePick(type) {
  if (type === 'photo') {
    document.getElementById("mobile-photo-input").click();
  } else {
    document.getElementById("mobile-file-input").click();
  }
}

function handleMobileFileSelected(event) {
  const files = event.target.files;
  if (!files || files.length === 0) return;
  uploadFilesToLaptop(files);
}

async function uploadFilesToLaptop(files) {
  const card = document.getElementById("mobile-transfer-card");
  card.classList.remove("hidden");

  for (let i = 0; i < files.length; i++) {
    const file = files[i];
    await uploadSingleFile(file);
  }
}

async function uploadSingleFile(file) {
  const card = document.getElementById("mobile-transfer-card");
  const filenameEl = document.getElementById("mobile-filename");
  const percentEl = document.getElementById("mobile-percent");
  const progressBar = document.getElementById("mobile-progress-bar");
  const speedEl = document.getElementById("mobile-speed");

  filenameEl.innerText = file.name;
  percentEl.innerText = "0%";
  progressBar.style.width = "0%";
  speedEl.innerText = "0.0 MB/s";

  const targetUrl = `http://${laptopIp}:${laptopPort}/api/transfer/send`;
  const headers = {
    "X-Seamless-Filename": encodeURIComponent(file.name),
    "X-Seamless-Filesize": file.size.toString(),
    "X-Seamless-Sender-Id": "android_phone",
    "X-Seamless-Sender-Name": "Android Phone",
    "X-Seamless-Token": authToken
  };

  try {
    const startTime = Date.now();
    let lastLoaded = 0;

    // Use XMLHttpRequest for live upload progress events
    await new Promise((resolve, reject) => {
      const xhr = new XMLHttpRequest();
      xhr.open("POST", targetUrl, true);

      for (const [k, v] of Object.entries(headers)) {
        xhr.setRequestHeader(k, v);
      }

      xhr.upload.onprogress = (e) => {
        if (e.lengthComputable) {
          const percent = Math.round((e.loaded / e.total) * 100);
          percentEl.innerText = `${percent}%`;
          progressBar.style.width = `${percent}%`;

          const dt = (Date.now() - startTime) / 1000;
          if (dt > 0.3) {
            const speed = ((e.loaded / (1024 * 1024)) / dt).toFixed(1);
            speedEl.innerText = `${speed} MB/s`;
          }
        }
      };

      xhr.onload = () => {
        if (xhr.status >= 200 && xhr.status < 300) {
          resolve(xhr.responseText);
        } else {
          reject(new Error(`Upload failed with status ${xhr.status}`));
        }
      };

      xhr.onerror = () => reject(new Error("Network error during transfer"));
      xhr.send(file);
    });

    percentEl.innerText = "100%";
    progressBar.style.width = "100%";
    speedEl.innerText = "Completed";
    showMobileToast(`Sent ${file.name} to ${pairedPcName}!`);

    // Record in local history
    addMobileHistoryEntry({
      filename: file.name,
      filesize: file.size,
      direction: "outgoing",
      status: "completed",
      timestamp: Math.floor(Date.now() / 1000)
    });

    setTimeout(() => {
      card.classList.add("hidden");
    }, 2000);

  } catch (err) {
    console.error("Upload error:", err);
    speedEl.innerText = "Failed";
    showMobileToast(`Failed to send ${file.name}: ${err.message}`);
    setTimeout(() => {
      card.classList.add("hidden");
    }, 2500);
  }
}

// 3. Mobile Pairing Handshake
function openMobilePairingModal() {
  document.getElementById("mobile-pairing-modal").classList.remove("hidden");
  document.getElementById("mobile-pairing-modal").classList.add("flex");
}

function closeMobilePairingModal() {
  document.getElementById("mobile-pairing-modal").classList.add("hidden");
  document.getElementById("mobile-pairing-modal").classList.remove("flex");
}

async function submitPairingPin() {
  const pinInput = document.getElementById("mobile-pin-input");
  const ipInput = document.getElementById("manual-laptop-ip");
  const pin = pinInput.value.trim();
  const customIp = ipInput.value.trim();

  if (customIp) {
    laptopIp = customIp;
    localStorage.setItem("seamless_laptop_ip", laptopIp);
  }

  if (pin.length !== 6) {
    showMobileToast("Please enter a valid 6-digit PIN.");
    return;
  }

  try {
    const res = await fetch(`http://${laptopIp}:${laptopPort}/api/pair/verify`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        pin: pin,
        device_id: "android_client_" + Math.random().toString(36).substring(7),
        device_name: "Galaxy S24 Ultra",
        device_ip: window.location.hostname
      })
    });

    const data = await res.json();
    if (res.ok && data.success) {
      authToken = data.token;
      localStorage.setItem("seamless_token", authToken);
      closeMobilePairingModal();
      showMobileToast("Paired successfully with Windows Laptop!");
      await checkLaptopConnection();
    } else {
      showMobileToast(data.error || "Incorrect or expired PIN.");
    }
  } catch (err) {
    showMobileToast("Connection error: Could not reach laptop.");
  }
}

// 4. Mobile History
function addMobileHistoryEntry(entry) {
  mobileHistory.unshift(entry);
  if (mobileHistory.length > 20) mobileHistory.pop();
  localStorage.setItem("seamless_mobile_history", JSON.stringify(mobileHistory));
  renderMobileHistory();
}

function renderMobileHistory() {
  const list = document.getElementById("mobile-recent-list");
  const countTag = document.getElementById("recent-count-tag");
  countTag.innerText = `${mobileHistory.length} file(s) today`;

  if (mobileHistory.length === 0) {
    list.innerHTML = `
      <div class="p-3 text-center text-xs text-[#7C877D] clean-inner-card rounded-xl">
        No transfers recorded yet.
      </div>
    `;
    return;
  }

  let html = "";
  mobileHistory.forEach(item => {
    const isDoc = !item.filename.match(/\.(jpg|jpeg|png|gif|webp|mp4|mov)$/i);
    const icon = isDoc ? "file-text" : "image";
    const sizeMb = (item.filesize / (1024 * 1024)).toFixed(1);

    html += `
      <div class="p-2.5 rounded-xl clean-inner-card flex items-center justify-between shadow-xs">
        <div class="flex items-center gap-2 truncate">
          <i data-lucide="${icon}" class="w-4 h-4 text-forest-accent"></i>
          <div class="truncate">
            <div class="text-[11px] font-bold text-forest-text truncate">${item.filename}</div>
            <div class="text-[9px] text-[#7C877D]">Sent &bull; ${sizeMb} MB</div>
          </div>
        </div>
        <span class="text-[10px] font-bold text-[#23421C] bg-moss-badge px-2 py-0.5 rounded">Completed</span>
      </div>
    `;
  });

  list.innerHTML = html;
  if (window.lucide) lucide.createIcons();
}

function refreshMobileHistory() {
  renderMobileHistory();
  showMobileToast("Refreshed transfer history.");
}

// 5. Clipboard Sync
function toggleMobileClipboard(checkbox) {
  showMobileToast(checkbox.checked ? "Clipboard Sync enabled on phone." : "Clipboard Sync paused.");
}

// 6. Toast
function showMobileToast(msg) {
  const toast = document.getElementById("mobile-toast");
  const text = document.getElementById("mobile-toast-text");
  text.innerText = msg;
  toast.classList.remove("translate-y-20", "opacity-0");
  setTimeout(() => {
    toast.classList.add("translate-y-20", "opacity-0");
  }, 3000);
}
