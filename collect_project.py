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
    DEST_DIR_NAME  # Don't copy the output folder into itself
}

# Specific files to ignore
IGNORE_FILES = {
    "collect_project.py", # Don't copy this script
    ".env",               # Security: Don't upload tokens
    "discord.log",        # Logs are local only
    ".DS_Store",          # Mac junk
    "Thumbs.db"           # Windows junk
}

# If you want to include the database, remove "database.db" from this list.
# Usually, you exclude the binary DB file when uploading code changes.
IGNORE_FILES.add("database.db") 

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

    copied_count = 0

    # 2. Walk and Copy
    for root, dirs, files in os.walk(SOURCE_DIR):
        # Filter directories in-place to prevent walking into ignored folders
        dirs[:] = [d for d in dirs if d not in IGNORE_DIRS]
        
        # Calculate relative path to mirror structure
        rel_path = Path(root).relative_to(SOURCE_DIR)
        target_path = DEST_DIR / rel_path

        # Create the directory in destination
        if not target_path.exists():
            target_path.mkdir(parents=True, exist_ok=True)

        for file in files:
            if file in IGNORE_FILES:
                continue
            
            # Skip compiled python files if they aren't in __pycache__
            if file.endswith(".pyc"):
                continue

            src_file = Path(root) / file
            dst_file = target_path / file

            shutil.copy2(src_file, dst_file)
            copied_count += 1
            print(f"   📄 Copied: {rel_path / file}")

    print("-" * 40)
    print(f"✅ Success! Copied {copied_count} files.")
    print(f"📂 Your files are ready in: {DEST_DIR}")

if __name__ == "__main__":
    main()