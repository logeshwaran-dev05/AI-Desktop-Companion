# Command Examples – AI Engine

## 1. Supported Input

| User Input | Intent | Expected Result |
|---|---|---|
| Open Notepad | open_application | Generate a plan to open Notepad |

## 2. Ambiguous Inputs

| User Input | Why It Is Ambiguous | Expected Assistant Response |
|---|---|---|
| Open | Application name is missing | Ask which application to open |
| Open it | The application is not identified | Ask what the user wants to open |
| Start the application | Application name is missing | Ask for the application name |

## 3. Unsupported Inputs

| User Input | Reason |
|---|---|
| Open Photoshop | Photoshop is not currently supported |
| Open Chrome | Chrome is not currently supported |
| Delete a file | File deletion is not implemented |
| Send an email | Email functionality is not implemented |

## 4. Other Inputs

| User Input | Current Handling |
|---|---|
| Empty input | Ask the user to enter a command |
| What is Python? | Classified as a general question; answering is not implemented yet |
| Play music | Not currently supported |

## 5. Current Limitations

- The planner currently uses rule-based command recognition.
- Only Notepad is supported for application-opening commands.
- The planner generates structured plans but does not execute them.
- Voice input and multilingual processing are not implemented yet.
- General questions are classified but not answered.
