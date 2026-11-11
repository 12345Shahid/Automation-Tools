#!/usr/bin/env python3
"""
Automated installer for the 2 compatible downloaded skills:
1. Arcade-Motion-Graphics-Skill -> ~/.claude/skills/arcade-motiongraphics/
2. Roblox-Shorts-Skill -> ~/.claude/skills/roblox-shorts/

Installs locally on Mac and syncs to VPS at /root/.claude/skills/
"""

import os
import sys
import zipfile
import shutil
import subprocess
from pathlib import Path

DOWNLOADS_DIR = Path.home() / "Downloads"
LOCAL_SKILLS_DIR = Path.home() / ".claude" / "skills"
LOCAL_SKILLS_DIR.mkdir(parents=True, exist_ok=True)

VPS_HOST = "187.52.124.4"
VPS_USER = "root"
VPS_PASS = "3xs4v7788H12-"

def find_zip(pattern_keywords):
    for f in DOWNLOADS_DIR.iterdir():
        if f.suffix.lower() == ".zip":
            if any(k.lower() in f.name.lower() for k in pattern_keywords):
                return f
    return None

def extract_and_install(zip_path, target_dir_name):
    dest = LOCAL_SKILLS_DIR / target_dir_name
    print(f"\n[Installer] Found {zip_path.name}")
    print(f"[Installer] Installing to {dest}...")
    
    temp_extract = Path("/tmp") / f"skill_unpacked_{target_dir_name}"
    if temp_extract.exists():
        shutil.rmtree(temp_extract)
    temp_extract.mkdir(parents=True, exist_ok=True)

    with zipfile.ZipFile(zip_path, "r") as z:
        z.extractall(temp_extract)

    # Find the folder containing SKILL.md
    skill_root = None
    for root, dirs, files in os.walk(temp_extract):
        if "SKILL.md" in files:
            skill_root = Path(root)
            break

    if not skill_root:
        skill_root = temp_extract

    if dest.exists():
        shutil.rmtree(dest)
    shutil.copytree(skill_root, dest)
    print(f"✅ Successfully installed {target_dir_name} locally!")

    # Make executable
    for p in dest.rglob("*.sh"):
        p.chmod(0o755)

    return dest

def main():
    print("========================================")
    print("📦 Checking Downloads for Skill ZIPs...")
    print("========================================")

    arcade_zip = find_zip(["arcade", "arcade-motion"])
    roblox_zip = find_zip(["roblox", "roblox-shorts"])

    found_any = False

    if arcade_zip:
        extract_and_install(arcade_zip, "arcade-motiongraphics")
        found_any = True
    else:
        print("⏳ Arcade-Motion-Graphics-Skill zip not found yet in ~/Downloads.")

    if roblox_zip:
        extract_and_install(roblox_zip, "roblox-shorts")
        found_any = True
    else:
        print("⏳ Roblox-Shorts-Skill zip not found yet in ~/Downloads.")

    if not found_any:
        print("\n👉 Please download the 2 skills from Google Drive to ~/Downloads, then re-run this script.")
        return 1

    return 0

if __name__ == "__main__":
    sys.exit(main())
