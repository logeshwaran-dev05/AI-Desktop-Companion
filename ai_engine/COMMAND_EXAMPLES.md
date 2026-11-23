
# AI Engine – Command Understanding and Testing

## 1. Overview

The AI Engine processes user text commands and converts them into structured plans.

It identifies the user's intent, extracts the requested application, matches the application against the available application catalogue, and determines whether the command can be accepted, requires clarification, or is unsupported.

The AI Engine does not directly execute applications.

## 2. Supported Command Patterns

The planner currently supports these application launch commands:

- Open
- Launch
- Start

Examples:

| User Command | Expected Behaviour |
|---|---|
| Open Notepad | Accept command |
| Launch Notepad | Accept command |
| Start Notepad | Accept command |
| Please open Notepad | Accept command |
| Please launch Calculator | Accept command |
| Could you start Chrome | Accept command |

## 3. Capitalization Handling

Commands are normalized to lowercase before processing.

Examples:

| Input | Expected Result |
|---|---|
| OPEN NOTEPAD | Accepted |
| Open Notepad | Accepted |
| open notepad | Accepted |
| OpEn NoTePaD | Accepted |

Capitalization does not affect application matching.

## 4. Extra Spaces Handling

Extra spaces are normalized before processing.

Example:

Input:
  Open     Notepad

Expected result:
  plan_ready

Whitespace-only input is treated as empty input.

## 5. Spelling Mistake Handling

The planner uses similarity matching to identify application names with minor spelling mistakes.

Examples:

| User Command | Expected Behaviour |
|---|---|
| Open Notepd | Match Notepad |
| Open Notepadd | Match Notepad |
| Open notep | Ask for clarification |

The planner uses confidence thresholds:

- Confidence >= 0.85: Accept the match.
- Confidence >= 0.65 and < 0.85: Ask for clarification.
- Confidence < 0.65: Reject the match.

Ambiguous matches are also sent for clarification.

## 6. Application Catalogue

The current temporary application catalogue contains:

| Application | Application ID |
|---|---|
| Notepad | notepad |
| Calculator | calculator |
| Google Chrome | chrome |
| Visual Studio Code | vscode |
| Visual Studio 2022 | visualstudio2022 |
| Microsoft Edge | edge |
| Paint | paint |

Examples:

- Open Calculator
- Open Chrome
- Open Paint

The catalogue is temporary and will be replaced with the actual installed-application catalogue through backend integration.

## 7. Unknown Applications

Applications that cannot be matched with sufficient confidence are rejected.

Examples:

| User Command | Expected Status |
|---|---|
| Open Photoshop | unsupported |
| Open Blender | unsupported |

The planner does not create an application launch plan for unsupported applications.

## 8. Empty Input and Missing Application

The planner handles missing user input safely.

Examples:

| User Input | Expected Behaviour |
|---|---|
| Empty string | Ask for input |
| Spaces only | Ask for input |
| Open | Ask which application to open |

Expected status:
  clarification_required

## 9. Ambiguous Application Matching

When multiple applications match the requested name, the planner asks the user to clarify.

Example:

User command:
  Open Visual Studio

Possible matches:
- Visual Studio Code
- Visual Studio 2022

Expected status:
  clarification_required

The planner does not automatically choose between ambiguous applications.

## 10. Unsupported Commands

The current planner supports application launch requests only.

Examples:

- Delete a file
- Close an application

These commands are currently unsupported.

Expected status:
  unsupported

## 11. Test Results

Testing command:

  python -m unittest discover -s ai_engine/tests -v

Final result:

- Total test cases: 24
- Passed: 24
- Failed: 0

Test categories:

1. Empty input handling
2. Missing application handling
3. Capitalization variations
4. Extra spaces
5. Spelling mistake handling
6. Alternate command phrases
7. Supported application matching
8. Unknown application rejection
9. Ambiguous application detection
10. Unsupported command handling

## 12. Current Limitations

1. The application catalogue is temporary and not connected to the actual Windows installed-app inventory.
2. Only application launch commands are supported.
3. File operations and application closing are not implemented.
4. Spelling correction depends on similarity scores and may not understand every spelling variation.
5. The planner prepares structured execution plans but does not execute applications.
6. Backend integration is still required for real-time installed-application discovery.

## 13. Conclusion

The AI Engine successfully processes supported application launch commands, handles capitalization and minor spelling variations, identifies unknown applications, and requests clarification for ambiguous inputs.

All 24 unit tests passed successfully.

The module is ready for the next stage of integration with the shared backend and Windows automation components.
