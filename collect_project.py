import os
import shutil
from pathlib import Path

# --- CONFIGURATION ---
SOURCE_DIR = Path(__file__).parent
DEST_DIR_NAME = "_upload_ready"
DEST_DIR = SOURCE_DIR / DEST_DIR_NAME

# Directories to completely ignore
IGNORE_DIRS = {
    ".git", 
    "__pycache__", 
    "venv", 
    "env", 
    ".idea", 
    ".vscode", 
    "assets",
    "tests",
    ".pytest_cache",
    "database/backups",
    DEST_DIR_NAME  # Don't copy the output folder into itself
}

# Specific files to ignore
IGNORE_FILES = {
    "collect_project.py", # Don't copy this script
    ".env",               # Security: Don't upload tokens
    "discord.log",        # Logs are local only
    ".DS_Store",          # Mac junk
    "Thumbs.db",          # Windows junk
    "run_app.bat",
    "requirements.txt",
    "icon.png",
    "config.json",
    "README.md",
    "UPDATES.md",
    ".gitattributes",
    ".gitignore",
    "config_test.json",
    "conftest.py",
    "tests.py",
    "prompt.txt"
}

# If you want to include the database, remove "database.db" from this list.
# Usually, you exclude the binary DB file when uploading code changes.
IGNORE_FILES.add("database.db") 

def build_flat_name(src_path: Path) -> str:
    """
    Given a source file path under SOURCE_DIR, build a flattened filename
    that includes its relative directory as a prefix, joined by underscores.
    """
    rel = src_path.relative_to(SOURCE_DIR)

    parent_parts = rel.parent.parts
    if parent_parts:
        prefix = "_".join(parent_parts)
        return f"{prefix}_{rel.name}"
    else:
        return rel.name

def main():
    print(f"📦 Starting collection from: {SOURCE_DIR}")
    print(f"🎯 Destination: {DEST_DIR}")

    # 1. Clean previous build
    if DEST_DIR.exists():
        print("🧹 Cleaning previous output directory...")
        try:
            shutil.rmtree(DEST_DIR)
        except PermissionError:
            print("❌ Error: Close any files open in the '_upload_ready' folder and try again.")
            return

    DEST_DIR.mkdir(parents=True, exist_ok=True)

    copied_count = 0
    copied_files = []  # NEW: track copied destination files in order

    # 2. Walk and Copy
    for root, dirs, files in os.walk(SOURCE_DIR):
        # Filter directories in-place to prevent walking into ignored folders
        dirs[:] = [d for d in dirs if d not in IGNORE_DIRS]
        
        for file in files:
            if file in IGNORE_FILES:
                continue

            # Skip compiled python files if they aren't in __pycache__
            if file.endswith(".pyc"):
                continue

            src_file = Path(root) / file
            flat_name = build_flat_name(src_file)
            dst_file = DEST_DIR / flat_name

            # Optional: detect collisions
            if dst_file.exists():
                raise FileExistsError(
                    f"Flattened name collision: '{flat_name}' already exists.\n"
                    f"Current file: {src_file.relative_to(SOURCE_DIR)}"
                )

            shutil.copy2(src_file, dst_file)
            copied_count += 1
            copied_files.append((src_file, dst_file))  # NEW: remember src & dst

            print(
                f"   📄 Copied: {src_file.relative_to(SOURCE_DIR)} "
                f"-> {flat_name}"
            )

    # 3. Build combined file for LLM consumption  # NEW
    if copied_files:
        combined_path = DEST_DIR / "ALL_CODE_COMBINED.txt"
        print(f"🧬 Creating combined file: {combined_path}")

        with combined_path.open("w", encoding="utf-8") as combined:
            combined.write(
                "=========== PROJECT CODE BUNDLE START ===========\n"
                "Each section below represents one source file.\n"
                "Use the FILE START/END markers to navigate.\n"
                "===============================================\n\n"
            )

            for src_file, dst_file in copied_files:
                rel = src_file.relative_to(SOURCE_DIR)
                header = (
                    "---------- FILE START ----------\n"
                    f"ORIGINAL_PATH: {rel}\n"
                    f"FLATTENED_NAME: {dst_file.name}\n"
                    "---------- FILE CONTENT ----------\n\n"
                )
                footer = (
                    "\n---------- FILE END ------------\n\n"
                )

                combined.write(header)
                try:
                    # Read as text; for non-text files this may fail.
                    combined.write(dst_file.read_text(encoding="utf-8"))
                except UnicodeDecodeError:
                    # If you want to skip non-text files silently:
                    combined.write("[BINARY OR NON‑TEXT FILE OMITTED]\n")
                combined.write(footer)

            combined.write("=========== PROJECT CODE BUNDLE END ============\n")

        print(f"✅ Combined file created at: {combined_path}")
    else:
        print("⚠️ No files were copied; combined file not created.")

    print("-" * 40)
    print(f"✅ Success! Copied {copied_count} files.")
    print(f"📂 Your files are ready in: {DEST_DIR}")

if __name__ == "__main__":
    main()