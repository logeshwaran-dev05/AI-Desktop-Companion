/**
 * JM VERTEX AI COMPANION — 100% Silent Background Auto-Updater
 * ==============================================================
 * Automatically checks for updates against GitHub repository in the background.
 * Silently downloads payload.zip and updates files in-place inside user-space
 * (%LocalAppData%\Programs\JM-Vertex or current install directory).
 *
 * ZERO Windows administrator / UAC prompts (user-space execution).
 * ZERO separate setup.exe or manual installer dialogs needed.
 */

const fs = require('fs');
const path = require('path');
const https = require('https');
const { exec } = require('child_process');

const PRIMARY_VERSION_URL = 'https://raw.githubusercontent.com/logeshwaran-dev05/AI-Desktop-Companion/main/landing-page/version.json';
const FALLBACK_VERSION_URL = 'https://logeshwaran-dev05.github.io/AI-Desktop-Companion/version.json';

/**
 * Returns current installed version from local version.json
 */
function getCurrentVersion() {
  try {
    const vPath = path.join(__dirname, '..', 'version.json');
    if (fs.existsSync(vPath)) {
      const data = JSON.parse(fs.readFileSync(vPath, 'utf8'));
      return data.version || '1.0.1';
    }
  } catch (err) {
    console.warn('[Updater] Could not read local version.json:', err.message);
  }
  return '1.0.1';
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
  } catch {
    try {
      remoteInfo = await fetchJson(FALLBACK_VERSION_URL);
    } catch (err2) {
      console.warn('[Updater] Remote version checks unreachable:', err2.message);
      return {
        updateAvailable: false,
        currentVersion,
        error: 'Unable to check update server.',
      };
    }
  }

  const remoteVersion = remoteInfo.version || '1.0.1';
  const hasUpdate = compareSemver(currentVersion, remoteVersion) > 0;

  return {
    updateAvailable: hasUpdate,
    currentVersion,
    remoteVersion,
    releaseNotes: remoteInfo.releaseNotes || 'Automatic background improvements.',
    downloadUrl: remoteInfo.downloadUrl || '',
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
        return reject(new Error(`Download failed: HTTP ${res.statusCode}`));
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
 * Automatically download payload.zip and extract silently over application directory.
 * Uses path.resolve(__dirname, '..', '..') so it always targets the exact installed location,
 * whether it's default AppData or a custom path, avoiding any permission problems.
 */
async function downloadAndApplyUpdate(updateInfo) {
  if (!updateInfo || !updateInfo.downloadUrl) {
    return {
      success: false,
      error: 'Download URL missing from update metadata.',
    };
  }

  const tempZip = path.join(process.env.TEMP || 'C:\\Windows\\Temp', `jm_vertex_payload_${Date.now()}.zip`);
  const appRoot = path.resolve(__dirname, '..', '..');

  try {
    console.log(`[Updater] Downloading silent update from: ${updateInfo.downloadUrl}`);
    await downloadFile(updateInfo.downloadUrl, tempZip);

    if (!fs.existsSync(tempZip) || fs.statSync(tempZip).size < 1000) {
      throw new Error('Downloaded update file is invalid or empty.');
    }

    console.log(`[Updater] Silently extracting update to: ${appRoot}`);
    // Extract using PowerShell Expand-Archive (silent user-space overwrite)
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

    // Update local version stamp
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
    console.error('[Updater] Background auto-update failed:', err);
    try { fs.unlinkSync(tempZip); } catch {}
    return {
      success: false,
      error: err.message,
    };
  }
}

/**
 * Full-cycle silent background auto-update.
 */
async function runSilentAutoUpdate() {
  const check = await checkForUpdates();
  if (!check.updateAvailable) {
    return { updated: false, currentVersion: check.currentVersion };
  }
  const result = await downloadAndApplyUpdate(check);
  return {
    updated: result.success,
    newVersion: check.remoteVersion,
    error: result.error,
  };
}

module.exports = {
  getCurrentVersion,
  checkForUpdates,
  downloadAndApplyUpdate,
  runSilentAutoUpdate,
};
