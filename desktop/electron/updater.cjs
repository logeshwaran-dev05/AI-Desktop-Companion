/**
 * JM VERTEX AI COMPANION — In-App Auto-Updater
 * ==============================================
 * Checks for updates against GitHub repository and GitHub Pages.
 * Automatically downloads and applies updates silently in user-space
 * (%LocalAppData%\Programs\JM-Vertex).
 * If auto-update fails (e.g. offline, firewalled, file locked),
 * provides direct 1-click manual download fallback.
 */

const fs = require('fs');
const path = require('path');
const https = require('https');
const { exec } = require('child_process');

const PRIMARY_VERSION_URL = 'https://raw.githubusercontent.com/logeshwaran-dev05/AI-Desktop-Companion/main/landing-page/version.json';
const FALLBACK_VERSION_URL = 'https://logeshwaran-dev05.github.io/AI-Desktop-Companion/version.json';
const FALLBACK_MANUAL_URL = 'https://logeshwaran-dev05.github.io/AI-Desktop-Companion/downloads/JM-Vertex-AI-Companion-Setup.exe';

/**
 * Returns current installed version from local version.json
 */
function getCurrentVersion() {
  try {
    const vPath = path.join(__dirname, '..', 'version.json');
    if (fs.existsSync(vPath)) {
      const data = JSON.parse(fs.readFileSync(vPath, 'utf8'));
      return data.version || '1.0.0';
    }
  } catch (err) {
    console.warn('[Updater] Could not read local version.json:', err.message);
  }
  return '1.0.0';
}

/**
 * Basic semver compare: returns 1 if v2 > v1, -1 if v1 > v2, 0 if equal.
 */
function compareSemver(v1, v2) {
  const p1 = (v1 || '0.0.0').split('.').map((n) => parseInt(n, 10) || 0);
  const p2 = (v2 || '0.0.0').split('.').map((n) => parseInt(n, 10) || 0);
  for (let i = 0; i < 3; i++) {
    const a = p1[i] || 0;
    const b = p2[i] || 0;
    if (b > a) return 1;
    if (a > b) return -1;
  }
  return 0;
}

/**
 * HTTP GET request helper returning parsed JSON with timeout
 */
function fetchJson(url) {
  return new Promise((resolve, reject) => {
    const req = https.get(url, { headers: { 'User-Agent': 'JM-Vertex-Companion' }, timeout: 8000 }, (res) => {
      if (res.statusCode >= 300 && res.statusCode < 400 && res.headers.location) {
        return resolve(fetchJson(res.headers.location));
      }
      if (res.statusCode !== 200) {
        return reject(new Error(`Server returned HTTP ${res.statusCode}`));
      }
      let raw = '';
      res.on('data', (chunk) => { raw += chunk; });
      res.on('end', () => {
        try {
          const parsed = JSON.parse(raw);
          resolve(parsed);
        } catch (e) {
          reject(e);
        }
      });
    });

    req.on('timeout', () => {
      req.destroy();
      reject(new Error('Connection timed out'));
    });
    req.on('error', reject);
  });
}

/**
 * Check for updates against remote GitHub repository.
 */
async function checkForUpdates() {
  const currentVersion = getCurrentVersion();
  let remoteInfo = null;

  try {
    remoteInfo = await fetchJson(PRIMARY_VERSION_URL);
  } catch (err1) {
    console.warn('[Updater] Primary check failed, trying fallback...', err1.message);
    try {
      remoteInfo = await fetchJson(FALLBACK_VERSION_URL);
    } catch (err2) {
      console.error('[Updater] All remote version checks failed:', err2.message);
      return {
        updateAvailable: false,
        currentVersion,
        error: 'Unable to reach update server. Check your internet connection.',
        manualUrl: FALLBACK_MANUAL_URL,
      };
    }
  }

  const remoteVersion = remoteInfo.version || '1.0.0';
  const hasUpdate = compareSemver(currentVersion, remoteVersion) > 0;

  return {
    updateAvailable: hasUpdate,
    currentVersion,
    remoteVersion,
    releaseNotes: remoteInfo.releaseNotes || 'General performance and stability improvements.',
    downloadUrl: remoteInfo.downloadUrl || '',
    setupExeUrl: remoteInfo.setupExeUrl || FALLBACK_MANUAL_URL,
    manualUrl: remoteInfo.setupExeUrl || FALLBACK_MANUAL_URL,
  };
}

/**
 * Download a remote file to a local destination
 */
function downloadFile(url, destPath) {
  return new Promise((resolve, reject) => {
    const file = fs.createWriteStream(destPath);
    const req = https.get(url, { headers: { 'User-Agent': 'JM-Vertex-Companion' }, timeout: 60000 }, (res) => {
      if (res.statusCode >= 300 && res.statusCode < 400 && res.headers.location) {
        file.close();
        try { fs.unlinkSync(destPath); } catch {}
        return resolve(downloadFile(res.headers.location, destPath));
      }
      if (res.statusCode !== 200) {
        file.close();
        try { fs.unlinkSync(destPath); } catch {}
        return reject(new Error(`Failed to download update package: HTTP ${res.statusCode}`));
      }

      res.pipe(file);
      file.on('finish', () => {
        file.close(resolve);
      });
    });

    req.on('timeout', () => {
      req.destroy();
      file.close();
      try { fs.unlinkSync(destPath); } catch {}
      reject(new Error('Download timed out'));
    });

    req.on('error', (err) => {
      file.close();
      try { fs.unlinkSync(destPath); } catch {}
      reject(err);
    });
  });
}

/**
 * Automatically download payload.zip and extract over application directory.
 * If automatic extraction fails, returns manualUrl so the user can download with 1-click.
 */
async function downloadAndApplyUpdate(updateInfo) {
  const manualUrl = updateInfo.setupExeUrl || FALLBACK_MANUAL_URL;
  if (!updateInfo.downloadUrl) {
    return {
      success: false,
      error: 'Download URL missing from update metadata.',
      manualUrl,
    };
  }

  const tempZip = path.join(process.env.TEMP || 'C:\\Windows\\Temp', `jm_vertex_payload_${Date.now()}.zip`);
  const appRoot = path.resolve(__dirname, '..', '..');

  try {
    console.log(`[Updater] Downloading update payload from: ${updateInfo.downloadUrl}`);
    await downloadFile(updateInfo.downloadUrl, tempZip);

    if (!fs.existsSync(tempZip) || fs.statSync(tempZip).size < 1000) {
      throw new Error('Downloaded update file is invalid or empty.');
    }

    console.log(`[Updater] Extracting payload to: ${appRoot}`);
    // Extract using PowerShell Expand-Archive
    await new Promise((resolve, reject) => {
      const psCmd = `powershell -NoProfile -ExecutionPolicy Bypass -Command "Expand-Archive -LiteralPath '${tempZip}' -DestinationPath '${appRoot}' -Force"`;
      exec(psCmd, { windowsHide: true }, (err, stdout, stderr) => {
        if (err) {
          reject(new Error(stderr || err.message));
        } else {
          resolve(stdout);
        }
      });
    });

    // Write updated version.json
    try {
      const vPath = path.join(__dirname, '..', 'version.json');
      fs.writeFileSync(vPath, JSON.stringify({
        version: updateInfo.remoteVersion,
        releaseDate: new Date().toISOString(),
        updatedAt: Date.now(),
      }, null, 2), 'utf8');
    } catch {}

    // Cleanup temp zip
    try { fs.unlinkSync(tempZip); } catch {}

    return {
      success: true,
      newVersion: updateInfo.remoteVersion,
    };
  } catch (err) {
    console.error('[Updater] Auto-update extraction failed:', err);
    try { fs.unlinkSync(tempZip); } catch {}
    return {
      success: false,
      error: err.message,
      manualUrl,
    };
  }
}

module.exports = {
  getCurrentVersion,
  checkForUpdates,
  downloadAndApplyUpdate,
  FALLBACK_MANUAL_URL,
};
