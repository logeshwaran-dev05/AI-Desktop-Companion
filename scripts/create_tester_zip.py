import os
import zipfile

def package_tester_release():
    output_zip = "JM-Vertex-AI-Companion-v1.0-Tester-Release.zip"
    if os.path.exists(output_zip):
        os.remove(output_zip)

    include_dirs = [
        "api",
        "windows_automation",
        "ai_engine",
        "desktop/dist",
        "desktop/electron",
        "desktop/public",
        "desktop/src",
        "installer"
    ]
    
    include_files = [
        "Launch-Companion.bat",
        "run_local.py",
        "run_in_chrome.py",
        "run_in_chrome.ps1",
        "TESTER_INSTRUCTIONS.md",
        "README.md",
        "TEAM_CONTRACTS.md",
        "package.json",
        "package-lock.json",
        "desktop/package.json",
        "landing-page/downloads/JM-Vertex-AI-Companion-Setup.exe"
    ]

    exclude_exts = {".pyc", ".pyo", ".log", ".tmp"}
    exclude_dirs = {"__pycache__", ".git", ".gemini", "node_modules", ".vscode"}

    count = 0
    with zipfile.ZipFile(output_zip, "w", zipfile.ZIP_DEFLATED) as zf:
        for f in include_files:
            if os.path.exists(f):
                arcname = os.path.normpath(f)
                zf.write(f, arcname)
                count += 1
                print(f"[FILE] {f}")

        for d in include_dirs:
            if os.path.exists(d):
                for root, dirs, files in os.walk(d):
                    dirs[:] = [sub for sub in dirs if sub not in exclude_dirs]
                    for file in files:
                        ext = os.path.splitext(file)[1].lower()
                        if ext in exclude_exts:
                            continue
                        full_path = os.path.join(root, file)
                        arcname = os.path.normpath(full_path)
                        zf.write(full_path, arcname)
                        count += 1

    size_mb = os.path.getsize(output_zip) / (1024 * 1024)
    print(f"\n[+] Created {output_zip} successfully!")
    print(f"    Total files packaged: {count}")
    print(f"    Package size: {size_mb:.2f} MB")

    # Also copy to landing-page/downloads so it's accessible via web
    landing_dest = os.path.join("landing-page", "downloads", output_zip)
    import shutil
    shutil.copy2(output_zip, landing_dest)
    print(f"[+] Also copied to {landing_dest}")

if __name__ == "__main__":
    package_tester_release()
