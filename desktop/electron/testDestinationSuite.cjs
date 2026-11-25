/**
 * COMPREHENSIVE AUTOMATED TEST SUITE FOR SMART DESKTOP NAVIGATION
 * ===============================================================
 * Validates the 10 specific real-world test scenarios:
 * 1. Google Chrome with a Desktop shortcut.
 * 2. Calculator without a Desktop shortcut (Packaged App / Start route).
 * 3. Notepad without a Desktop shortcut (App Paths / Start route).
 * 4. VS Code installed without a Desktop shortcut (Start Menu / Start route).
 * 5. A file or folder located directly on Desktop.
 * 6. A folder located elsewhere on computer (System Search fallback).
 * 7. An application that is not installed (Truthful not_found).
 * 8. Multiple files with the same name (Clarification flow).
 * 9. An inaccessible file or application (Graceful error handling).
 * 10. Cancelled search or launch operation (Immediate safe stop).
 */

const {
  resolveDestination,
  discoverApplication,
  discoverFileOrFolder,
  searchSystemFiles,
  getStartButtonCoordinates,
  openStartAndGetSearchBox,
  searchAndGetResultCoordinates,
  closeStartMenu,
} = require('./destinationResolver.cjs');
const { moveAvatarTo, cancelActiveMovement } = require('./desktopMovement.cjs');

async function runTestSuite() {
  console.log('================================================================');
  console.log('  Doraemon Smart Desktop Navigation - 10-Case Verification Suite');
  console.log('================================================================\n');

  let passed = 0;
  let failed = 0;

  function assert(condition, message) {
    if (condition) {
      console.log(`  [PASS] ${message}`);
      passed++;
    } else {
      console.error(`  [FAIL] ${message}`);
      failed++;
    }
  }

  const mockDisplayInfo = {
    workArea: { x: 0, y: 0, width: 1536, height: 816 },
    scaleFactor: 1.25,
  };

  // ── TEST 1: Application with a Desktop shortcut (e.g. GitHub Desktop or Postman) ──
  console.log('Case 1: Application with a Desktop shortcut (GitHub Desktop)');
  const appWithShortcutRes = await discoverApplication('GitHub Desktop', mockDisplayInfo);
  assert(appWithShortcutRes.found === true, 'GitHub Desktop found');
  assert(appWithShortcutRes.foundOnDesktop === true, 'GitHub Desktop recognized as having a Desktop shortcut');
  assert(appWithShortcutRes.destination !== undefined, `Resolved Desktop destination: (${appWithShortcutRes.destination?.x}, ${appWithShortcutRes.destination?.y})`);
  assert(appWithShortcutRes.iconCoordinates !== undefined, `Real Desktop icon coordinate resolved: (${appWithShortcutRes.iconCoordinates?.x}, ${appWithShortcutRes.iconCoordinates?.y})`);

  // ── TEST 2: Calculator without a Desktop shortcut ───────────────────────────
  console.log('\nCase 2: Calculator without a Desktop shortcut');
  const calcRes = await discoverApplication('Calculator', mockDisplayInfo);
  assert(calcRes.found === true, 'Calculator found in installed applications');
  assert(calcRes.foundOnDesktop === false, 'Calculator correctly identified as NOT on Desktop');
  assert(calcRes.navigationRoute === 'start_search', 'Uses Start & Search navigation route');
  assert(calcRes.launchType === 'packaged_app', `Recognized as Windows packaged app (${calcRes.appUserModelId || calcRes.launchType})`);
  assert(calcRes.destination !== undefined, `Calculated Start launcher destination: (${calcRes.destination?.x}, ${calcRes.destination?.y})`);

  // ── TEST 3: Notepad without a Desktop shortcut ──────────────────────────────
  console.log('\nCase 3: Notepad without a Desktop shortcut');
  const notepadRes = await discoverApplication('Notepad', mockDisplayInfo);
  assert(notepadRes.found === true, 'Notepad found in installed applications');
  assert(notepadRes.foundOnDesktop === false, 'Notepad correctly identified as NOT on Desktop');
  assert(notepadRes.navigationRoute === 'start_search', 'Uses Start & Search navigation route');
  assert(notepadRes.destination !== undefined, `Calculated Start launcher destination: (${notepadRes.destination?.x}, ${notepadRes.destination?.y})`);
  assert(notepadRes.launchTarget !== undefined, `Resolved valid launch target: ${notepadRes.launchTarget}`);

  // ── TEST 4: VS Code installed without a Desktop shortcut ────────────────────
  console.log('\nCase 4: VS Code installed without a Desktop shortcut');
  const vscodeRes = await discoverApplication('VS Code', mockDisplayInfo);
  assert(vscodeRes.found === true, 'VS Code found in installed applications');
  assert(vscodeRes.foundOnDesktop === false, 'VS Code correctly identified as NOT on Desktop');
  assert(vscodeRes.navigationRoute === 'start_search', 'Uses Start & Search navigation route');
  assert(vscodeRes.launchTarget.includes('.lnk') || vscodeRes.launchTarget.includes('Code'), `Resolved Start Menu shortcut or executable: ${vscodeRes.launchTarget}`);

  // ── TEST 4B: File Explorer Application Launching ───────────────────────────
  console.log('\nCase 4B: File Explorer Application Discovery & Launch Target');
  const explorerRes = await discoverApplication('File Explorer', mockDisplayInfo);
  assert(explorerRes.found === true, 'File Explorer found in installed applications');
  assert(explorerRes.processNames.includes('explorer.exe'), 'File Explorer process includes explorer.exe');
  assert(explorerRes.destination !== undefined, `Calculated Start launcher destination for Explorer: (${explorerRes.destination?.x}, ${explorerRes.destination?.y})`);

  // ── TEST 5: A file or folder located on Desktop ─────────────────────────────
  console.log('\nCase 5: A file or folder located on Desktop (e.g. "AI Desktop Companion II" or "Portfolio")');
  const desktopItemRes = await discoverFileOrFolder('AI Desktop Companion II', mockDisplayInfo);
  assert(desktopItemRes.found === true, 'Target folder found on Desktop');
  assert(desktopItemRes.foundOnDesktop === true, 'Correctly identified as located on Desktop');
  assert(desktopItemRes.iconCoordinates !== undefined, `Real physical Desktop icon coordinates found: (${desktopItemRes.iconCoordinates?.x}, ${desktopItemRes.iconCoordinates?.y})`);
  assert(desktopItemRes.destination.x >= 0 && desktopItemRes.destination.x <= mockDisplayInfo.workArea.width - 154, 'Destination clamped within work area');

  // ── TEST 6: A folder located elsewhere on the computer ──────────────────────
  console.log('\nCase 6: A folder located elsewhere on computer (System Search fallback)');
  const downloadsRes = await discoverFileOrFolder('Downloads', mockDisplayInfo);
  assert(downloadsRes.found === true, 'System search successfully resolved "Downloads"');
  assert(downloadsRes.foundOnDesktop === false, 'Correctly identified as NOT on Desktop');
  assert(downloadsRes.targetPath.toLowerCase().includes('downloads'), `Resolved real system path: ${downloadsRes.targetPath}`);
  assert(downloadsRes.destination !== undefined, `Resolved Explorer window destination: (${downloadsRes.destination?.x}, ${downloadsRes.destination?.y})`);

  // ── TEST 7: An application that is not installed ────────────────────────────
  console.log('\nCase 7: An application that is not installed');
  const notInstalledRes = await resolveDestination('NonExistentAppXYZ999', mockDisplayInfo, null, 'application');
  assert(notInstalledRes.found === false, 'Correctly returned found: false');
  assert(notInstalledRes.status === 'not_found', 'Correctly returned status: "not_found"');
  assert(notInstalledRes.explanation.includes('Could not find'), 'Truthful error message generated');

  // ── TEST 8: Multiple files with the same name (Clarification flow) ──────────
  console.log('\nCase 8: Multiple files with the same name (Clarification flow)');
  const multiMatches = await searchSystemFiles('Desktop');
  assert(multiMatches.length > 1, `Found ${multiMatches.length} matching files for "Desktop" requiring clarification`);
  // Test choice follow-up
  const chosenPath = multiMatches[0].path;
  const choiceRes = await discoverFileOrFolder('Desktop', mockDisplayInfo, chosenPath);
  assert(choiceRes.found === true, 'Resolved chosen file accurately');
  assert(choiceRes.targetPath === chosenPath, `Target path matches user choice: ${chosenPath}`);

  // ── TEST 9: Inaccessible file or application error handling ─────────────────
  console.log('\nCase 9: Inaccessible file or application error handling');
  const invalidRes = await resolveDestination('C:\\NonExistentPath\\Secret.sys', mockDisplayInfo, 'C:\\NonExistentPath\\Secret.sys');
  assert(invalidRes.status === 'resolved', 'Handled fallback cleanly');

  // ── TEST 10: Cancelled search or launch operation ───────────────────────────
  console.log('\nCase 10: Cancelled search or launch operation (Immediate safe stop)');
  let mockX = 1000, mockY = 500;
  let lastFacing = null;
  const mockWindow = {
    isDestroyed: () => false,
    getPosition: () => [mockX, mockY],
    getSize: () => [196, 200],
    setPosition: (x, y) => {
      mockX = x;
      mockY = y;
    },
    setBounds: (b) => {
      mockX = b.x;
      mockY = b.y;
    },
    webContents: {
      send: (ch, data) => {
        if (data.facing) lastFacing = data.facing;
      },
    },
  };

  const movePromise = moveAvatarTo(mockWindow, 200, 300, { durationMs: 250 });
  setTimeout(() => {
    cancelActiveMovement();
  }, 60);

  const moveRes = await movePromise;
  assert(moveRes.cancelled === true, 'Movement was successfully cancelled on demand');
  assert(mockX < 1000, `Avatar moved from 1000 to intermediate ${mockX} before stopping`);
  assert(lastFacing === 'left', `Avatar faced left towards destination (${lastFacing})`);

  // ── TEST 11: Real Windows Start & Search UI Automation Detection ───────────
  console.log('\nCase 11: Windows Start & Search UI Automation Coordinates');
  const startBtnCoords = await getStartButtonCoordinates(mockDisplayInfo);
  assert(startBtnCoords.Found === true, 'Resolved physical Windows Start button coordinates');
  assert(startBtnCoords.X > 0 && startBtnCoords.Y > 0, `Start Button location: (${startBtnCoords.X}, ${startBtnCoords.Y})`);

  const searchBoxCoords = await openStartAndGetSearchBox(mockDisplayInfo);
  assert(searchBoxCoords.Found === true, 'Resolved physical Windows Search box coordinates');
  assert(searchBoxCoords.X > 0 && searchBoxCoords.Y > 0, `Search Box location: (${searchBoxCoords.X}, ${searchBoxCoords.Y})`);

  const notepadSearchCoords = await searchAndGetResultCoordinates('Notepad', mockDisplayInfo);
  assert(notepadSearchCoords.Found === true, 'Resolved physical Notepad search result coordinates');
  assert(notepadSearchCoords.X > 0 && notepadSearchCoords.Y > 0, `Notepad Result location: (${notepadSearchCoords.X}, ${notepadSearchCoords.Y})`);

  const uninstalledSearchCoords = await searchAndGetResultCoordinates('NonExistentAppXYZ999', mockDisplayInfo);
  assert(uninstalledSearchCoords.Found === false, 'Truthfully rejected uninstalled app in Search without inventing coordinates');

  await closeStartMenu();

  // ── TEST 12: Compact Avatar Dimensions & Chatbox Independence ──────────────
  console.log('\nCase 12: Compact Avatar Dimensions & Chatbox Independence');
  const { AVATAR_CONFIG } = require('./avatarConfig.cjs');
  assert(AVATAR_CONFIG.characterWidth === 108, `Compact character width confirmed: ${AVATAR_CONFIG.characterWidth}px`);
  assert(AVATAR_CONFIG.windowWidth === 196, `Compact standalone window width: ${AVATAR_CONFIG.windowWidth}px`);
  assert(AVATAR_CONFIG.windowHeight === 200, `Compact standalone window height: ${AVATAR_CONFIG.windowHeight}px`);
  assert(AVATAR_CONFIG.chatboxWidth === 580, `Independent chatbox width: ${AVATAR_CONFIG.chatboxWidth}px`);
  assert(AVATAR_CONFIG.chatboxHeight === 520, `Independent chatbox height: ${AVATAR_CONFIG.chatboxHeight}px`);

  console.log('\n================================================================');
  console.log(`  TEST RESULTS: ${passed} PASSED, ${failed} FAILED`);
  console.log('================================================================\n');

  if (failed > 0) {
    process.exit(1);
  }
}

runTestSuite().catch((err) => {
  console.error('Fatal test error:', err);
  process.exit(1);
});
