import os
import zipfile

def create_payload():
    output_zip = os.path.join("installer", "payload.zip")
    if os.path.exists(output_zip):
        os.remove(output_zip)

    include_dirs = ["api", "windows_automation", "ai_engine", "desktop/electron", "desktop/dist", "desktop/public"]
    include_files = ["Launch-Companion.bat", "desktop/package.json", "desktop/version.json", "package.json"]

    with zipfile.ZipFile(output_zip, "w", zipfile.ZIP_DEFLATED) as zf:
        for f in include_files:
            if os.path.exists(f):
                zf.write(f, f)
                print(f"Added file: {f}")

        for d in include_dirs:
            if os.path.exists(d):
                for root, _, files in os.walk(d):
                    for file in files:
                        full_path = os.path.join(root, file)
                        # Normalize path
                        rel_path = os.path.relpath(full_path, ".")
                        zf.write(full_path, rel_path)
                print(f"Added dir: {d}")

    print(f"Payload created at {output_zip}, size: {os.path.getsize(output_zip)} bytes")

if __name__ == "__main__":
    create_payload()
