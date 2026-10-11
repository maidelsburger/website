#!/bin/bash
# Publish the website: commits all changes and pushes to GitHub.
# GitHub then builds the site and puts it live at https://aidelsburgerlab.com (1-2 minutes).
set -e
cd "$(dirname "$0")"
python3 build.py   # local sanity check: abort if the build fails
git add -A
if git diff --cached --quiet; then echo "Nothing to publish - no changes."; exit 0; fi
git commit -m "Update website content ($(date +%Y-%m-%d))"
git push
echo "Pushed. Live in ~2 minutes: https://aidelsburgerlab.com"
echo "Progress: https://github.com/maidelsburger/website/actions"
