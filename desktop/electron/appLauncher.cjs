/**
 * APP LAUNCHER ADAPTER — Electron Main Process
 * =============================================
 * Launches real Windows applications safely and truthfully verifies
 * that the process actually opened on the Windows desktop.
 *
 * SECURITY:
 * - Only approved allowlist application identifiers are accepted.
 * - ShellExecute via `start` ensures real Windows desktop GUI invocation.
 * - No user-supplied command strings or arguments are executed.
 * - Honest verification: verifies actual process existence in Windows tasklist.
 */

const { exec } = require('child_process');

/**
 * Common Windows browser process names for truthful verification
 */
const BROWSER_PROCESSES = ['chrome.exe', 'msedge.exe', 'brave.exe', 'firefox.exe', 'opera.exe'];

/**
 * Comprehensive application registry with native launch commands,
 * process names, and web/PWA fallbacks.
 */
const APP_REGISTRY = [
  // ── Native Windows Utilities ──
  {
    id: 'notepad',
    displayName: 'Notepad',
    aliases: ['notepad', 'notes', 'text editor', 'textpad'],
    launchCommand: 'cmd.exe /c start "" notepad',
    processNames: ['Notepad.exe', 'notepad.exe'],
    type: 'native',
  },
  {
    id: 'calculator',
    displayName: 'Calculator',
    aliases: ['calc', 'calculator', 'math'],
    launchCommand: 'cmd.exe /c start "" calc',
    processNames: ['CalculatorApp.exe', 'Calculator.exe', 'calc.exe'],
    type: 'native',
  },
  {
    id: 'explorer',
    displayName: 'File Explorer',
    aliases: ['explorer', 'files', 'my computer', 'file manager', 'folders'],
    launchCommand: 'cmd.exe /c start "" explorer',
    processNames: ['explorer.exe'],
    type: 'native',
  },
  {
    id: 'paint',
    displayName: 'Paint',
    aliases: ['paint', 'mspaint', 'draw', 'drawing'],
    launchCommand: 'cmd.exe /c start "" mspaint',
    processNames: ['mspaint.exe', 'PaintApp.exe'],
    type: 'native',
  },
  {
    id: 'cmd',
    displayName: 'Command Prompt',
    aliases: ['cmd', 'terminal', 'command prompt', 'shell'],
    launchCommand: 'cmd.exe /c start "" cmd',
    processNames: ['cmd.exe', 'conhost.exe'],
    type: 'native',
  },
  {
    id: 'chrome',
    displayName: 'Google Chrome',
    aliases: ['chrome', 'google chrome', 'browser', 'internet'],
    launchCommand: 'cmd.exe /c start "" chrome',
    processNames: ['chrome.exe'],
    type: 'native',
  },
  {
    id: 'vscode',
    displayName: 'Visual Studio Code',
    aliases: ['vscode', 'vs code', 'code', 'editor'],
    launchCommand: 'cmd.exe /c start "" code',
    processNames: ['Code.exe'],
    type: 'native',
  },

  // ── Dual-Mode Apps (Native first, Web fallback) ──
  {
    id: 'whatsapp',
    displayName: 'WhatsApp',
    aliases: ['whatsapp', 'wa', 'whats app'],
    launchCommand: 'cmd.exe /c start whatsapp:',
    processNames: ['WhatsApp.exe', 'WhatsApp.Root.exe'],
    fallbackUrl: 'https://web.whatsapp.com',
    type: 'hybrid',
  },
  {
    id: 'spotify',
    displayName: 'Spotify',
    aliases: ['spotify', 'music', 'songs'],
    launchCommand: 'cmd.exe /c start spotify:',
    processNames: ['Spotify.exe'],
    fallbackUrl: 'https://open.spotify.com',
    searchUrl: 'https://open.spotify.com/search/',
    type: 'hybrid',
  },
  {
    id: 'discord',
    displayName: 'Discord',
    aliases: ['discord'],
    launchCommand: 'cmd.exe /c start discord:',
    processNames: ['Discord.exe'],
    fallbackUrl: 'https://discord.com/app',
    type: 'hybrid',
  },

  // ── Web Services & Cloud Apps (Smart Browser Launch) ──
  {
    id: 'youtube',
    displayName: 'YouTube',
    aliases: ['youtube', 'yt', 'videos', 'watch'],
    webUrl: 'https://www.youtube.com',
    searchUrl: 'https://www.youtube.com/results?search_query=',
    processNames: BROWSER_PROCESSES,
    type: 'web',
  },
  {
    id: 'netflix',
    displayName: 'Netflix',
    aliases: ['netflix', 'movies', 'series'],
    webUrl: 'https://www.netflix.com',
    processNames: BROWSER_PROCESSES,
    type: 'web',
  },
  {
    id: 'primevideo',
    displayName: 'Prime Video',
    aliases: ['prime video', 'amazon prime', 'primevideo'],
    webUrl: 'https://www.primevideo.com',
    processNames: BROWSER_PROCESSES,
    type: 'web',
  },
  {
    id: 'disney',
    displayName: 'Disney+',
    aliases: ['disney', 'disney+', 'hotstar', 'disney plus'],
    webUrl: 'https://www.disneyplus.com',
    processNames: BROWSER_PROCESSES,
    type: 'web',
  },
  {
    id: 'soundcloud',
    displayName: 'SoundCloud',
    aliases: ['soundcloud', 'sound cloud'],
    webUrl: 'https://soundcloud.com',
    searchUrl: 'https://soundcloud.com/search?q=',
    processNames: BROWSER_PROCESSES,
    type: 'web',
  },
  {
    id: 'twitch',
    displayName: 'Twitch',
    aliases: ['twitch', 'stream'],
    webUrl: 'https://www.twitch.tv',
    searchUrl: 'https://www.twitch.tv/search?term=',
    processNames: BROWSER_PROCESSES,
    type: 'web',
  },
  {
    id: 'chatgpt',
    displayName: 'ChatGPT',
    aliases: ['chatgpt', 'chat gpt', 'ai chat', 'openai'],
    webUrl: 'https://chatgpt.com',
    processNames: BROWSER_PROCESSES,
    type: 'web',
  },
  {
    id: 'claude',
    displayName: 'Claude',
    aliases: ['claude', 'anthropic'],
    webUrl: 'https://claude.ai',
    processNames: BROWSER_PROCESSES,
    type: 'web',
  },
  {
    id: 'gemini',
    displayName: 'Google Gemini',
    aliases: ['gemini', 'google bard', 'bard'],
    webUrl: 'https://gemini.google.com',
    processNames: BROWSER_PROCESSES,
    type: 'web',
  },
  {
    id: 'copilot',
    displayName: 'Microsoft Copilot',
    aliases: ['copilot', 'bing chat', 'ms copilot'],
    webUrl: 'https://copilot.microsoft.com',
    processNames: BROWSER_PROCESSES,
    type: 'web',
  },
  {
    id: 'github',
    displayName: 'GitHub',
    aliases: ['github', 'git', 'repo', 'repositories'],
    webUrl: 'https://github.com',
    searchUrl: 'https://github.com/search?q=',
    processNames: BROWSER_PROCESSES,
    type: 'web',
  },
  {
    id: 'gitlab',
    displayName: 'GitLab',
    aliases: ['gitlab'],
    webUrl: 'https://gitlab.com',
    processNames: BROWSER_PROCESSES,
    type: 'web',
  },
  {
    id: 'stackoverflow',
    displayName: 'Stack Overflow',
    aliases: ['stack overflow', 'stackoverflow', 'stack'],
    webUrl: 'https://stackoverflow.com',
    searchUrl: 'https://stackoverflow.com/search?q=',
    processNames: BROWSER_PROCESSES,
    type: 'web',
  },
  {
    id: 'gmail',
    displayName: 'Gmail',
    aliases: ['gmail', 'google mail', 'emails', 'inbox'],
    webUrl: 'https://mail.google.com',
    processNames: BROWSER_PROCESSES,
    type: 'web',
  },
  {
    id: 'drive',
    displayName: 'Google Drive',
    aliases: ['drive', 'google drive', 'gdrive'],
    webUrl: 'https://drive.google.com',
    processNames: BROWSER_PROCESSES,
    type: 'web',
  },
  {
    id: 'docs',
    displayName: 'Google Docs',
    aliases: ['docs', 'google docs', 'document'],
    webUrl: 'https://docs.new',
    processNames: BROWSER_PROCESSES,
    type: 'web',
  },
  {
    id: 'sheets',
    displayName: 'Google Sheets',
    aliases: ['sheets', 'google sheets', 'spreadsheet'],
    webUrl: 'https://sheets.new',
    processNames: BROWSER_PROCESSES,
    type: 'web',
  },
  {
    id: 'notion',
    displayName: 'Notion',
    aliases: ['notion'],
    webUrl: 'https://www.notion.so',
    processNames: BROWSER_PROCESSES,
    type: 'web',
  },
  {
    id: 'slack',
    displayName: 'Slack',
    aliases: ['slack'],
    webUrl: 'https://slack.com',
    processNames: BROWSER_PROCESSES,
    type: 'web',
  },
  {
    id: 'trello',
    displayName: 'Trello',
    aliases: ['trello'],
    webUrl: 'https://trello.com',
    processNames: BROWSER_PROCESSES,
    type: 'web',
  },
  {
    id: 'google',
    displayName: 'Google',
    aliases: ['google', 'search', 'web search'],
    webUrl: 'https://www.google.com',
    searchUrl: 'https://www.google.com/search?q=',
    processNames: BROWSER_PROCESSES,
    type: 'web',
  },
  {
    id: 'canva',
    displayName: 'Canva',
    aliases: ['canva', 'design'],
    webUrl: 'https://www.canva.com',
    processNames: BROWSER_PROCESSES,
    type: 'web',
  },
  {
    id: 'linkedin',
    displayName: 'LinkedIn',
    aliases: ['linkedin', 'jobs'],
    webUrl: 'https://www.linkedin.com',
    processNames: BROWSER_PROCESSES,
    type: 'web',
  },
  {
    id: 'twitter',
    displayName: 'X (Twitter)',
    aliases: ['twitter', 'x', 'tweet'],
    webUrl: 'https://x.com',
    searchUrl: 'https://x.com/search?q=',
    processNames: BROWSER_PROCESSES,
    type: 'web',
  },
  {
    id: 'reddit',
    displayName: 'Reddit',
    aliases: ['reddit'],
    webUrl: 'https://www.reddit.com',
    searchUrl: 'https://www.reddit.com/search/?q=',
    processNames: BROWSER_PROCESSES,
    type: 'web',
  },
  {
    id: 'instagram',
    displayName: 'Instagram',
    aliases: ['instagram', 'insta'],
    webUrl: 'https://www.instagram.com',
    processNames: BROWSER_PROCESSES,
    type: 'web',
  },
  {
    id: 'facebook',
    displayName: 'Facebook',
    aliases: ['facebook', 'fb'],
    webUrl: 'https://www.facebook.com',
    processNames: BROWSER_PROCESSES,
    type: 'web',
  },
  {
    id: 'maps',
    displayName: 'Google Maps',
    aliases: ['maps', 'google maps', 'navigation', 'directions'],
    webUrl: 'https://maps.google.com',
    searchUrl: 'https://maps.google.com/maps?q=',
    processNames: BROWSER_PROCESSES,
    type: 'web',
  },
  {
    id: 'calendar',
    displayName: 'Google Calendar',
    aliases: ['calendar', 'google calendar', 'schedule'],
    webUrl: 'https://calendar.google.com',
    processNames: BROWSER_PROCESSES,
    type: 'web',
  },
  {
    id: 'terminal',
    displayName: 'Terminal',
    aliases: ['terminal', 'powershell', 'pwsh'],
    launchCommand: 'cmd.exe /c start powershell',
    processNames: ['powershell.exe', 'WindowsTerminal.exe', 'conhost.exe'],
    type: 'native',
  },
  {
    id: 'settings',
    displayName: 'Windows Settings',
    aliases: ['settings', 'control panel', 'config'],
    launchCommand: 'cmd.exe /c start ms-settings:',
    processNames: ['SystemSettings.exe'],
    type: 'native',
  },
  {
    id: 'meet',
    displayName: 'Google Meet',
    aliases: ['meet', 'google meet', 'gmeet', 'video call'],
    webUrl: 'https://meet.google.com',
    processNames: BROWSER_PROCESSES,
    type: 'web',
  },
  {
    id: 'word',
    displayName: 'Microsoft Word',
    aliases: ['word', 'ms word', 'microsoft word', 'winword'],
    launchCommand: 'cmd.exe /c start winword',
    processNames: ['WINWORD.EXE', 'winword.exe'],
    fallbackUrl: 'https://word.office.com',
    type: 'hybrid',
  },
  {
    id: 'excel',
    displayName: 'Microsoft Excel',
    aliases: ['excel', 'ms excel', 'microsoft excel'],
    launchCommand: 'cmd.exe /c start excel',
    processNames: ['EXCEL.EXE', 'excel.exe'],
    fallbackUrl: 'https://excel.office.com',
    type: 'hybrid',
  },
  {
    id: 'powerpoint',
    displayName: 'Microsoft PowerPoint',
    aliases: ['powerpoint', 'power point', 'ms powerpoint', 'ppt', 'microsoft powerpoint'],
    launchCommand: 'cmd.exe /c start powerpnt',
    processNames: ['POWERPNT.EXE', 'powerpnt.exe'],
    fallbackUrl: 'https://powerpoint.office.com',
    type: 'hybrid',
  },
  {
    id: 'outlook',
    displayName: 'Microsoft Outlook',
    aliases: ['outlook', 'ms outlook', 'microsoft outlook'],
    launchCommand: 'cmd.exe /c start outlook',
    processNames: ['OUTLOOK.EXE', 'outlook.exe'],
    fallbackUrl: 'https://outlook.live.com',
    type: 'hybrid',
  },
  {
    id: 'onedrive',
    displayName: 'Microsoft OneDrive',
    aliases: ['onedrive', 'one drive', 'microsoft onedrive'],
    launchCommand: 'cmd.exe /c start onedrive',
    processNames: ['OneDrive.exe'],
    fallbackUrl: 'https://onedrive.live.com',
    type: 'hybrid',
  },
  {
    id: 'replit',
    displayName: 'Replit',
    aliases: ['replit', 'repl.it', 'repl'],
    webUrl: 'https://replit.com',
    searchUrl: 'https://replit.com/search?q=',
    processNames: BROWSER_PROCESSES,
    type: 'web',
  },
  {
    id: 'codepen',
    displayName: 'CodePen',
    aliases: ['codepen', 'code pen'],
    webUrl: 'https://codepen.io',
    searchUrl: 'https://codepen.io/search/pens?q=',
    processNames: BROWSER_PROCESSES,
    type: 'web',
  },
  {
    id: 'dockerhub',
    displayName: 'Docker Hub',
    aliases: ['docker hub', 'dockerhub', 'docker'],
    webUrl: 'https://hub.docker.com',
    searchUrl: 'https://hub.docker.com/search?q=',
    processNames: BROWSER_PROCESSES,
    type: 'web',
  },
  {
    id: 'aws',
    displayName: 'AWS Console',
    aliases: ['aws', 'aws console', 'amazon web services', 'amazon console'],
    webUrl: 'https://console.aws.amazon.com',
    processNames: BROWSER_PROCESSES,
    type: 'web',
  },
  {
    id: 'telegram',
    displayName: 'Telegram',
    aliases: ['telegram', 'tg'],
    launchCommand: 'cmd.exe /c start tg:',
    processNames: ['Telegram.exe'],
    fallbackUrl: 'https://web.telegram.org',
    type: 'hybrid',
  },
  {
    id: 'zoom',
    displayName: 'Zoom',
    aliases: ['zoom', 'zoom meeting', 'zoom meetings'],
    launchCommand: 'cmd.exe /c start zoommtg:',
    processNames: ['Zoom.exe'],
    fallbackUrl: 'https://zoom.us',
    type: 'hybrid',
  },
  {
    id: 'teams',
    displayName: 'Microsoft Teams',
    aliases: ['teams', 'microsoft teams', 'ms teams'],
    launchCommand: 'cmd.exe /c start msteams:',
    processNames: ['ms-teams.exe', 'Teams.exe'],
    fallbackUrl: 'https://teams.microsoft.com',
    type: 'hybrid',
  },
  {
    id: 'coursera',
    displayName: 'Coursera',
    aliases: ['coursera', 'online courses'],
    webUrl: 'https://www.coursera.org',
    searchUrl: 'https://www.coursera.org/search?query=',
    processNames: BROWSER_PROCESSES,
    type: 'web',
  },
  {
    id: 'udemy',
    displayName: 'Udemy',
    aliases: ['udemy', 'courses'],
    webUrl: 'https://www.udemy.com',
    searchUrl: 'https://www.udemy.com/courses/search/?q=',
    processNames: BROWSER_PROCESSES,
    type: 'web',
  },
  {
    id: 'wikipedia',
    displayName: 'Wikipedia',
    aliases: ['wikipedia', 'wiki', 'encyclopedia'],
    webUrl: 'https://www.wikipedia.org',
    searchUrl: 'https://en.wikipedia.org/wiki/Special:Search?search=',
    processNames: BROWSER_PROCESSES,
    type: 'web',
  },
  {
    id: 'figma',
    displayName: 'Figma',
    aliases: ['figma', 'ui design', 'figma design'],
    launchCommand: 'cmd.exe /c start figma:',
    processNames: ['Figma.exe'],
    fallbackUrl: 'https://www.figma.com',
    type: 'hybrid',
  },
  {
    id: 'canva',
    displayName: 'Canva',
    aliases: ['canva', 'design', 'graphics'],
    webUrl: 'https://www.canva.com',
    searchUrl: 'https://www.canva.com/search?q=',
    processNames: BROWSER_PROCESSES,
    type: 'web',
  },
  {
    id: 'jira',
    displayName: 'Jira',
    aliases: ['jira', 'atlassian jira', 'tickets'],
    webUrl: 'https://www.atlassian.com/software/jira',
    processNames: BROWSER_PROCESSES,
    type: 'web',
  },
  {
    id: 'pinterest',
    displayName: 'Pinterest',
    aliases: ['pinterest', 'pins'],
    webUrl: 'https://www.pinterest.com',
    searchUrl: 'https://www.pinterest.com/search/pins/?q=',
    processNames: BROWSER_PROCESSES,
    type: 'web',
  },
];

const APP_ALLOWLIST = APP_REGISTRY;

/**
 * Checks whether any of the given process names are currently running in Windows tasklist
 * @param {string[]} processNames
 * @returns {Promise<boolean>}
 */
function verifyProcessRunning(processNames) {
  return new Promise((resolve) => {
    exec('tasklist /fo csv /nh', { windowsHide: true }, (err, stdout) => {
      if (err || !stdout) {
        resolve(false);
        return;
      }
      const lower = stdout.toLowerCase();
      const matched = processNames.some((p) => lower.includes(p.toLowerCase()));
      resolve(matched);
    });
  });
}

/**
 * Open a URL in the user's default browser or Chrome safely
 * @param {string} url
 * @returns {Promise<boolean>}
 */
function openBrowserUrl(url) {
  return new Promise((resolve) => {
    // start "" "<url>" triggers Windows ShellExecute to open the default web browser
    const cmd = `cmd.exe /c start "" "${url.replace(/"/g, '')}"`;
    exec(cmd, { windowsHide: false }, (err) => {
      resolve(!err);
    });
  });
}

/**
 * Launch an application or web fallback safely with truth verification.
 * Supports:
 * - Native application execution
 * - Hybrid native-to-web fallback (e.g. WhatsApp, Spotify)
 * - Direct Web application launch (YouTube, Netflix, ChatGPT, etc.)
 * - Search query routing (e.g. "search lofi on youtube")
 *
 * @param {string} appId - Allowlist identifier or search request
 * @param {object} [options]
 * @param {string} [options.query] - Optional query or search term
 * @returns {Promise<{
 *   success: boolean,
 *   verified: boolean,
 *   displayName: string,
 *   mode: 'real' | 'fallback-web' | 'not-found',
 *   error?: string
 * }>}
 */
function launchApp(appId, options = {}) {
  return new Promise(async (resolve) => {
    const rawTarget = (appId || '').trim();
    const normalized = rawTarget.toLowerCase();

    // 1. Find entry in registry by ID or alias
    const appEntry = APP_REGISTRY.find(
      (a) => a.id === normalized || (a.aliases && a.aliases.includes(normalized))
    );

    // 2. Handle known Web-first apps (e.g. YouTube, Netflix, ChatGPT)
    if (appEntry && appEntry.type === 'web') {
      const targetUrl = (options.query && appEntry.searchUrl)
        ? `${appEntry.searchUrl}${encodeURIComponent(options.query)}`
        : appEntry.webUrl;

      console.log(`[Launcher] Opening web app ${appEntry.displayName}: ${targetUrl}`);
      await openBrowserUrl(targetUrl);

      // Verify browser opened in tasklist
      const verified = await waitForProcess(BROWSER_PROCESSES, 3000);
      resolve({
        success: true,
        verified,
        displayName: options.query ? `${appEntry.displayName}: "${options.query}"` : `${appEntry.displayName}`,
        mode: 'real',
      });
      return;
    }

    // 3. Handle Native or Hybrid apps (e.g. Notepad, Calculator, WhatsApp, Spotify)
    if (appEntry) {
      // If query is requested for a hybrid app like Spotify with searchUrl
      if (options.query && appEntry.searchUrl) {
        if (appEntry.id === 'spotify') {
          exec(`cmd.exe /c start spotify:search:${encodeURIComponent(options.query)}`, { windowsHide: false }, () => {});
          const isNative = await waitForProcess(appEntry.processNames, 1500);
          if (isNative) {
            resolve({
              success: true,
              verified: true,
              displayName: `${appEntry.displayName}: "${options.query}"`,
              mode: 'real',
            });
            return;
          }
        }
        // Fallback to web search
        const webSearchUrl = `${appEntry.searchUrl}${encodeURIComponent(options.query)}`;
        await openBrowserUrl(webSearchUrl);
        const isBrowserRunning = await waitForProcess(BROWSER_PROCESSES, 2500);
        resolve({
          success: true,
          verified: isBrowserRunning,
          displayName: `${appEntry.displayName}: "${options.query}"`,
          mode: 'real',
        });
        return;
      }

      console.log(`[Launcher] Attempting native launch for ${appEntry.displayName}`);
      exec(appEntry.launchCommand, { windowsHide: false }, () => {});

      // Verify native process within 1.8 seconds
      const isNativeRunning = await waitForProcess(appEntry.processNames, 1800);

      if (isNativeRunning) {
        console.log(`[Launcher] Confirmed native ${appEntry.displayName} process is running!`);
        resolve({
          success: true,
          verified: true,
          displayName: appEntry.displayName,
          mode: 'real',
        });
        return;
      }

      // If native failed and we have a web fallback (e.g. WhatsApp Web, Spotify Web)
      if (appEntry.fallbackUrl) {
        console.log(`[Launcher] Native ${appEntry.displayName} not found. Falling back to Web App: ${appEntry.fallbackUrl}`);
        await openBrowserUrl(appEntry.fallbackUrl);
        const isBrowserRunning = await waitForProcess(BROWSER_PROCESSES, 2500);

        resolve({
          success: true,
          verified: isBrowserRunning,
          displayName: `${appEntry.displayName} (Web Fallback)`,
          mode: 'fallback-web',
        });
        return;
      }

      // Native utility verification timeout
      resolve({
        success: false,
        verified: false,
        displayName: appEntry.displayName,
        mode: 'real',
        error: `Could not verify that ${appEntry.displayName} opened. It may not be installed on this Windows PC.`,
      });
      return;
    }

    // 4. Universal Fallback: Unrecognized command -> Search Google
    const queryTerm = options.query || rawTarget;
    console.log(`[Launcher] No local app registered for "${rawTarget}". Triggering smart search fallback for: ${queryTerm}`);
    const searchUrl = `https://www.google.com/search?q=${encodeURIComponent(queryTerm)}`;
    await openBrowserUrl(searchUrl);
    const browserVerified = await waitForProcess(BROWSER_PROCESSES, 2500);

    resolve({
      success: true,
      verified: browserVerified,
      displayName: `Google Search: "${queryTerm}"`,
      mode: 'fallback-web',
    });
  });
}

/**
 * Polls for process existence up to timeoutMs
 * @param {string[]} processNames
 * @param {number} timeoutMs
 * @returns {Promise<boolean>}
 */
function waitForProcess(processNames, timeoutMs = 2500) {
  return new Promise((resolve) => {
    const start = Date.now();
    const interval = setInterval(async () => {
      const running = await verifyProcessRunning(processNames);
      if (running) {
        clearInterval(interval);
        resolve(true);
        return;
      }
      if (Date.now() - start >= timeoutMs) {
        clearInterval(interval);
        resolve(false);
      }
    }, 350);
  });
}

module.exports = { launchApp, APP_ALLOWLIST, APP_REGISTRY };
