
# Temporary Installed Application Catalogue

INSTALLED_APPS = [
    {
        "app_name": "Notepad",
        "app_id": "notepad",
        "executable": "notepad.exe"
    },
    {
        "app_name": "Calculator",
        "app_id": "calculator",
        "executable": "calc.exe"
    },
    {
        "app_name": "Google Chrome",
        "app_id": "chrome",
        "executable": "chrome.exe"
    },
    {
        "app_name": "Visual Studio Code",
        "app_id": "vscode",
        "executable": "code.exe"
    },
    {
        "app_name": "Visual Studio 2022",
        "app_id": "visualstudio2022",
        "executable": "devenv.exe"
    },
    {
        "app_name": "Microsoft Edge",
        "app_id": "edge",
        "executable": "msedge.exe"
    },
    {
        "app_name": "Paint",
        "app_id": "paint",
        "executable": "mspaint.exe"
    }
]


def get_installed_apps():
    """Return the temporary application catalogue."""
    return INSTALLED_APPS
