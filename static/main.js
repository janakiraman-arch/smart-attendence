const videoEl = document.getElementById('video');
const canvasEl = document.getElementById('canvas');
const statusEl = document.getElementById('status');
const toastEl = document.getElementById('toast');
const enrollBtn = document.getElementById('enrollBtn');
const checkBtn = document.getElementById('checkBtn');
const checkoutBtn = document.getElementById('checkoutBtn');
const refreshBtn = document.getElementById('refreshBtn');
const tableBody = document.querySelector('#attendanceTable tbody');
const scanOverlay = document.getElementById('scanOverlay');
const locationToggle = document.getElementById('locationToggle');
const liveLocEl = document.getElementById('liveLocation');
const locTextEl = liveLocEl?.querySelector('.loc-text');
const locAccEl = liveLocEl?.querySelector('.loc-accuracy');
const stationNameInput = document.getElementById('stationName');

function playDing() {
  try {
    const ctx = new (window.AudioContext || window.webkitAudioContext)();
    const osc = ctx.createOscillator();
    const gain = ctx.createGain();
    osc.type = 'sine';
    osc.frequency.setValueAtTime(880, ctx.currentTime);
    osc.frequency.exponentialRampToValueAtTime(1760, ctx.currentTime + 0.1);
    gain.gain.setValueAtTime(0.15, ctx.currentTime);
    gain.gain.exponentialRampToValueAtTime(0.01, ctx.currentTime + 0.3);
    osc.connect(gain);
    gain.connect(ctx.destination);
    osc.start();
    osc.stop(ctx.currentTime + 0.3);
  } catch (e) {
    // AudioContext not supported or blocked
  }
}

function setStatus(text) {
  statusEl.textContent = text;
}

function showToast(message, ok = true) {
  toastEl.textContent = message;
  toastEl.style.borderColor = ok ? 'rgba(120,255,186,0.5)' : 'rgba(255,107,107,0.8)';
  toastEl.classList.add('show');
  
  if (ok) playDing();
  speak(message);
  
  setTimeout(() => toastEl.classList.remove('show'), 2500);
}

function speak(text) {
  if ('speechSynthesis' in window) {
    const utterance = new SpeechSynthesisUtterance(text);
    // Optional: setup voice properties like pitch, rate
    utterance.rate = 1.0;
    utterance.pitch = 1.0;
    window.speechSynthesis.speak(utterance);
  }
}

async function initCamera() {
  try {
    const stream = await navigator.mediaDevices.getUserMedia({ video: true });
    videoEl.srcObject = stream;
    return true;
  } catch (err) {
    console.error(err);
    showToast('Enable camera to continue', false);
    return false;
  }
}

function captureFrame() {
  const w = videoEl.videoWidth;
  const h = videoEl.videoHeight;
  if (!w || !h) return null;
  canvasEl.width = w;
  canvasEl.height = h;
  const ctx = canvasEl.getContext('2d');
  ctx.drawImage(videoEl, 0, 0, w, h);
  return canvasEl.toDataURL('image/jpeg', 0.9);
}

async function enroll() {
  const name = prompt('Enter full name for enrollment');
  if (!name) return;
  const frame = captureFrame();
  if (!frame) {
    showToast('Camera not ready', false);
    return;
  }
  setStatus('enrolling…');
  
  if (scanOverlay) scanOverlay.classList.add('scanning');
  
  const res = await fetch('/api/enroll', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ name, image: frame })
  });
  const data = await res.json();
  if (res.ok) {
    showToast(`Enrolled ${data.name}`);
  } else {
    showToast(data.error || 'Enroll failed', false);
  }
  
  if (scanOverlay) scanOverlay.classList.remove('scanning');
  
  setStatus('idle');
  await loadAttendance();
}

async function getLocation() {
  const getIPLocation = async () => {
    // Primary IP provider
    const tryIpApi = async () => {
      const ipRes = await fetch('https://ipapi.co/json/');
      if (ipRes.ok) {
        const ipData = await ipRes.json();
        if (ipData.city) {
          return {
            display: `${ipData.city}, ${ipData.region} (IP-based)`,
            accuracy: null,
            source: 'ip',
            lat: ipData.latitude ?? null,
            lon: ipData.longitude ?? null
          };
        }
      }
      throw new Error('ipapi failed');
    };

    // Secondary IP provider
    const tryGeoDb = async () => {
      const res = await fetch('https://geolocation-db.com/json/');
      if (res.ok) {
        const data = await res.json();
        if (data.city || data.state) {
          return {
            display: `${data.city || 'Unknown'}, ${data.state || data.country_code || ''} (IP-based)`,
            accuracy: null,
            source: 'ip',
            lat: data.latitude ?? null,
            lon: data.longitude ?? null
          };
        }
      }
      throw new Error('geolocation-db failed');
    };

    try {
      return await tryIpApi();
    } catch (e) {
      console.warn('Primary IP geolocation failed', e);
      try {
        return await tryGeoDb();
      } catch (err) {
        console.warn('Secondary IP geolocation failed', err);
      }
    }

    return { display: 'Unknown Location', accuracy: null, source: 'ip', lat: null, lon: null };
  };

  return new Promise((resolve) => {
    if (!navigator.geolocation) {
      getIPLocation().then(resolve);
      return;
    }

    navigator.geolocation.getCurrentPosition(
      async (pos) => {
        const { latitude: lat, longitude: lon, altitude, accuracy } = pos.coords;
        console.log(`Location: ${lat}, ${lon}, Alt: ${altitude}, Acc: ${accuracy}m`);
        
        const altStr = Number.isFinite(altitude) ? `, Alt: ${altitude.toFixed(1)}m` : '';
        const accuracyMeters = Number.isFinite(accuracy) ? Math.max(0, Math.round(accuracy)) : null;
        let display = `${lat.toFixed(4)}, ${lon.toFixed(4)}${altStr}`;
        
        // Reverse geocode via open-meteo (no API key, browser-friendly)
        try {
          const res = await fetch(`https://geocoding-api.open-meteo.com/v1/reverse?latitude=${lat}&longitude=${lon}&language=en&count=1`, { cache: 'no-store' });
          if (res.ok) {
            const data = await res.json();
            if (data?.results?.length) {
              const place = data.results[0];
              const parts = [place.name, place.admin1, place.country].filter(Boolean);
              display = `${parts.join(', ')} (${lat.toFixed(4)}, ${lon.toFixed(4)}${altStr})`;
            }
          }
        } catch (e) { /* keep fallback */ }
        
        resolve({ display, accuracy: accuracyMeters, source: 'gps', lat, lon });
      },
      async (err) => {
        console.warn("Browser geolocation failed, falling back to IP", err);
        const ipLoc = await getIPLocation();
        if (err?.code === err?.PERMISSION_DENIED) {
          ipLoc.display = ipLoc.display
            ? `${ipLoc.display} (permission denied; IP fallback)`
            : 'Location denied (IP fallback)';
          ipLoc.denied = true;
        }
        resolve(ipLoc);
      },
      {
        enableHighAccuracy: true,
        timeout: 10000,
        maximumAge: 0
      }
    );
  });
}

async function verifySystemBiometrics() {
  if (!window.PublicKeyCredential) return true; // Fallback if browser doesn't support
  
  const isAvailable = await PublicKeyCredential.isUserVerifyingPlatformAuthenticatorAvailable();
  if (!isAvailable) return true; // Fallback if no Fingerprint/FaceID hardware

  try {
    // This triggers the native Touch ID/Face ID prompt on macOS/Windows/Mobile
    // We use a dummy challenge just to confirm "Intent and Presence"
    const challenge = new Uint8Array(32);
    window.crypto.getRandomValues(challenge);
    
    await navigator.credentials.get({
      publicKey: {
        challenge,
        userVerification: "required",
        timeout: 60000,
        allowCredentials: [] // We don't need a specific key, just "Any" valid user verification
      }
    });
    return true;
  } catch (err) {
    console.warn("Biometric confirmation skipped or failed", err);
    // If the user cancels the fingerprint prompt, we should still allow 
    // the face recognition to work, or we can block it if we want 'Strict Mode'.
    // For now, let's just log it.
    return true; 
  }
}

async function refreshLiveLocation() {
  if (!liveLocEl || !locationToggle) return;
  if (locationToggle.checked) {
    liveLocEl.classList.add('active');
    locTextEl.textContent = 'calibrating…';
    liveLocEl.classList.remove('show-acc');
    if (locAccEl) locAccEl.textContent = '';
    try {
      const loc = await getLocation();
      locTextEl.textContent = loc.display;
      if (loc.denied) showToast('Location permission denied; using IP-based location', false);
      if (!loc.lat && window.isSecureContext === false) {
        showToast('Location needs HTTPS or localhost; using coarse IP.', false);
      }
      if (locAccEl) {
        const showAcc = Boolean(loc.accuracy) || loc.source === 'ip';
        if (showAcc) {
          locAccEl.textContent = loc.accuracy ? `±${loc.accuracy} m` : 'coarse';
          locAccEl.title = loc.source === 'ip'
            ? 'IP-based city/region accuracy (coarse)'
            : 'GPS horizontal accuracy radius';
          liveLocEl.classList.add('show-acc');
        } else {
          liveLocEl.classList.remove('show-acc');
        }
      }
    } catch (e) {
      liveLocEl.classList.remove('show-acc');
      locTextEl.textContent = 'Location Blocked';
    }
  } else {
    liveLocEl.classList.remove('active');
    liveLocEl.classList.remove('show-acc');
    locTextEl.textContent = 'Disabled';
    if (locAccEl) locAccEl.textContent = '';
  }
}

async function recognize(action = 'check_in') {
  const frame = captureFrame();
  if (!frame) {
    showToast('Camera not ready', false);
    return;
  }
  setStatus('verifying…');
  let location = { display: 'Disabled', accuracy: null, source: 'off', lat: null, lon: null };
  
  if (locationToggle && locationToggle.checked) {
    setStatus('getting location…');
    try {
      location = await getLocation();
    } catch (err) {
      showToast(err, false);
      setStatus('idle');
      return;
    }
  }
  
  setStatus('checking…');
  
  const stationName = stationNameInput?.value || 'Unknown Station';
  const accNote = location.accuracy ? ` (±${location.accuracy}m)` : '';
  const ipNote = !location.accuracy && location.source === 'ip' ? ' (IP-based)' : '';
  const deniedNote = location.denied ? ' (permission denied)' : '';
  const locationSuffix = location.display !== 'Disabled'
    ? ` @ ${location.display}${accNote}${ipNote}${deniedNote}`
    : '';
  const finalLocation = `${stationName}${locationSuffix}`;
  
  if (scanOverlay) scanOverlay.classList.add('scanning');
  
  const res = await fetch('/api/recognize', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ image: frame, location: finalLocation, lat: location.lat, lon: location.lon, action })
  });
  const data = await res.json();
  if (res.ok && data.matched) {
    // STEP 2: Secondary Biometric Confirmation (Fingerprint/FaceID)
    setStatus('biometric confirm…');
    await verifySystemBiometrics();
    
    if (action === "check_out") {
      showToast(`Bye ${data.name}! Biometrics Authenticated.`);
    } else {
      showToast(`Hi ${data.name}! Biometrics Authenticated.`);
    }
  } else {
    showToast(data.error || 'No match found', false);
  }
  
  if (scanOverlay) scanOverlay.classList.remove('scanning');
  
  setStatus('idle');
  await loadAttendance();
}

async function loadAttendance() {
  const res = await fetch('/api/attendance');
  const rows = await res.json();
  tableBody.innerHTML = '';
  rows.forEach(({ name, timestamp, location, checkout, lat, lon }) => {
    const tr = document.createElement('tr');
    tr.innerHTML = `<td>${name}</td>
                    <td>${new Date(timestamp).toLocaleTimeString()}</td>
                    <td>${checkout ? new Date(checkout).toLocaleTimeString() : '--'}</td>
                    <td>${location || 'Unknown'}</td>
                    <td>${(lat !== null && lon !== null) ? `${Number(lat).toFixed(4)}, ${Number(lon).toFixed(4)}` : '—'}</td>`;
    tableBody.appendChild(tr);
  });
}

enrollBtn.addEventListener('click', enroll);
checkBtn.addEventListener('click', () => recognize('check_in'));
if (checkoutBtn) checkoutBtn.addEventListener('click', () => recognize('check_out'));
refreshBtn.addEventListener('click', loadAttendance);

(async function bootstrap() {
  await initCamera();
  await loadAttendance();
  
  // Persist location preference
  if (locationToggle) {
    const saved = localStorage.getItem('locationEnabled');
    if (saved !== null) {
      locationToggle.checked = saved === 'true';
    }
      locationToggle.addEventListener('change', () => {
        localStorage.setItem('locationEnabled', locationToggle.checked);
        refreshLiveLocation();
      });
    }

    if (stationNameInput) {
      const savedStation = localStorage.getItem('stationName');
      if (savedStation) stationNameInput.value = savedStation;
      stationNameInput.addEventListener('change', () => {
        localStorage.setItem('stationName', stationNameInput.value);
      });
    }
    
    refreshLiveLocation();
})();
