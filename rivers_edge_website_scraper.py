#!/usr/bin/env python3
"""
Fix River's Edge scraper on GitHub by updating with corrected indentation.
Run this script with your GitHub token as an argument.
"""
import requests
import base64
import sys
from pathlib import Path

def fix_scraper():
    # Get GitHub token from environment or command line
    token = None
    if len(sys.argv) > 1:
        token = sys.argv[1]
    else:
        token = input("Enter your GitHub token: ").strip()

    if not token:
        print("❌ GitHub token required")
        return False

    # Read the corrected file
    corrected_file = Path(__file__).parent / "rivers_edge_website_scraper_CORRECTED.py"
    if not corrected_file.exists():
        print(f"❌ Corrected file not found at {corrected_file}")
        return False

    with open(corrected_file, 'r') as f:
        content = f.read()

    # Encode content
    content_encoded = base64.b64encode(content.encode()).decode()

    # GitHub API setup
    headers = {
        'Authorization': f'token {token}',
        'Accept': 'application/vnd.github.v3+json'
    }
    file_url = 'https://api.github.com/repos/davesmithey/Trailbot/contents/rivers_edge_website_scraper.py'

    # Get current SHA
    print("Fetching current file info...")
    response = requests.get(file_url, headers=headers)
    if response.status_code != 200:
        print(f"❌ Failed to fetch file: {response.status_code}")
        print(f"   Response: {response.json()}")
        return False

    current_sha = response.json()['sha']
    print(f"✓ Got current SHA: {current_sha[:8]}...")

    # Prepare commit
    payload = {
        'message': '[FIX] Move extraction code outside content-change conditional',
        'content': content_encoded,
        'sha': current_sha,
        'branch': 'main'
    }

    # Commit
    print("Committing fix to GitHub...")
    response = requests.put(file_url, json=payload, headers=headers)

    if response.status_code not in [200, 201]:
        print(f"❌ Commit failed: {response.status_code}")
        print(f"   Response: {response.json()}")
        return False

    print("✓ Fix committed to GitHub!")
    return True

if __name__ == "__main__":
    success = fix_scraper()
    sys.exit(0 if success else 1)
