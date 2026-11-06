# Temporary Installed Application Catalogue

INSTALLED_APPS = [
    {
        "app_name": "Notepad",
        "app_id": "notepad",
        "executable": "notepad.exe",
        "aliases": ["note pad", "not pad"]
    },
    {
        "app_name": "Calculator",
        "app_id": "calculator",
        "executable": "calc.exe",
        "aliases": ["calc", "calculation app"]
    },
    {
        "app_name": "Google Chrome",
        "app_id": "chrome",
        "executable": "chrome.exe",
        "aliases": ["chrome"]
    },
    {
        "app_name": "Visual Studio Code",
        "app_id": "vscode",
        "executable": "code.exe",
        "aliases": ["vs code", "vscode", "visual studio code editor"]
    },
    {
        "app_name": "Visual Studio 2022",
        "app_id": "visualstudio2022",
        "executable": "devenv.exe",
        "aliases": ["vs 2022"]
    },
    {
        "app_name": "Microsoft Edge",
        "app_id": "edge",
        "executable": "msedge.exe",
        "aliases": ["edge", "microsoft edge"]
    },
    {
        "app_name": "Paint",
        "app_id": "paint",
        "executable": "mspaint.exe",
        "aliases": ["ms paint", "mspaint"]
    }
]


def get_installed_apps():
    """Return the temporary application catalogue."""
    return INSTALLED_APPS