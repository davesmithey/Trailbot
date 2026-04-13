#!/usr/bin/env python3
"""
Pandora's Box of Rox Website Scraper
Automatically extracts race information from tejastrails.com/pandoras
and updates the knowledge base JSON on a scheduled basis.
"""

import requests
from bs4 import BeautifulSoup
import json
import os
import base64
from datetime import datetime

# Configuration
WEBSITE_URL = "https://www.tejastrails.com/pandoras"
KB_FILE = "pandoras_knowledge_base.json"
GITHUB_TOKEN = os.environ.get('GITHUB_TOKEN')
GITHUB_REPO = os.environ.get('GITHUB_REPO', 'davesmithey/Trailbot')

def fetch_website():
    """Fetch the Pandora's Box of Rox webpage"""
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
        response = requests.get(WEBSITE_URL, headers=headers, timeout=10)
        response.raise_for_status()
        return response.text
    except requests.RequestException as e:
        print(f"Error fetching website: {e}")
        return None

def parse_website(html):
    """Parse website HTML and extract race information"""
    soup = BeautifulSoup(html, 'html.parser')
    data = {}

    # Extract race distances
    distances_section = soup.find(string=lambda s: s and "Races:" in s)
    if distances_section:
        distances_text = distances_section.strip()
        # Extract distances from text like "Races: 52.4 mi, 26.2 mi, 13.1 mi, 8 mi, 4 mi, Youth 1 mi"
        if ":" in distances_text:
            distances_str = distances_text.split(":", 1)[1].strip()
            # Parse individual distances
            distances = [d.strip() for d in distances_str.split(",")]
            distances = [d for d in distances if d]  # Remove empty strings
            data['distances'] = distances
            print(f"✓ Found {len(distances)} distances")

    # Extract when/date
    when_section = soup.find(string=lambda s: s and "When:" in s)
    if when_section:
        when_text = when_section.strip()
        if ":" in when_text:
            date_str = when_text.split(":", 1)[1].strip()
            data['date'] = date_str
            print(f"✓ Found date: {date_str}")

    # Extract where/venue
    where_section = soup.find(string=lambda s: s and "Where:" in s)
    if where_section:
        where_text = where_section.strip()
        if ":" in where_text:
            venue_str = where_text.split(":", 1)[1].strip()
            data['venue_text'] = venue_str
            print(f"✓ Found venue: {venue_str}")

    # Extract venue details from link if available
    venue_link = soup.find('a', string=lambda s: s and "Reveille Peak Ranch" in s if s else False)
    if venue_link:
        data['venue_name'] = "Reveille Peak Ranch"
        data['venue_location'] = "Burnet, TX"
        print(f"✓ Found venue: Reveille Peak Ranch, Burnet, TX")

    return data

def load_knowledge_base():
    """Load current knowledge base JSON"""
    try:
        with open(KB_FILE, 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        print(f"Warning: {KB_FILE} not found, starting fresh")
        return {}
    except json.JSONDecodeError:
        print(f"Warning: {KB_FILE} is not valid JSON")
        return {}

def update_knowledge_base(kb, scraped_data):
    """Update knowledge base with scraped data"""
    if not scraped_data:
        return kb, False

    changes_made = False

    # Update distances
    if 'distances' in scraped_data:
        if 'race' not in kb:
            kb['race'] = {}

        old_distances = kb['race'].get('distances', [])
        new_distances = scraped_data['distances']

        if old_distances != new_distances:
            kb['race']['distances'] = new_distances
            changes_made = True
            print(f"✓ Updated distances ({len(new_distances)} items)")

    # Update date
    if 'date' in scraped_data:
        if 'race' not in kb:
            kb['race'] = {}
        old_date = kb['race'].get('date')
        new_date = scraped_data['date']
        if old_date != new_date:
            kb['race']['date'] = new_date
            changes_made = True
            print(f"✓ Updated date: {new_date}")

    # Update venue
    if 'venue_name' in scraped_data:
        if 'race' not in kb:
            kb['race'] = {}
        if 'location' not in kb['race']:
            kb['race']['location'] = {}

        location_data = kb['race']['location']
        old_venue = location_data.get('venue')
        new_venue = scraped_data.get('venue_name')

        if old_venue != new_venue:
            location_data['venue'] = new_venue
            changes_made = True

        if 'venue_location' in scraped_data:
            old_city = location_data.get('city')
            new_city = scraped_data['venue_location']
            if old_city != new_city:
                location_data['city'] = new_city
                changes_made = True

        if changes_made and 'venue_name' in scraped_data:
            print(f"✓ Updated venue: {scraped_data['venue_name']}, {scraped_data.get('venue_location', '')}")

    # Add last updated timestamp
    kb['_lastUpdated'] = datetime.now().isoformat()
    kb['_source'] = 'Automated scraper from tejastrails.com/pandoras'

    return kb, changes_made

def save_knowledge_base(kb):
    """Save knowledge base to JSON file"""
    try:
        with open(KB_FILE, 'w') as f:
            json.dump(kb, f, indent=2)
        return True
    except Exception as e:
        print(f"Error saving knowledge base: {e}")
        return False

def commit_to_github(kb):
    """Commit updated knowledge base to GitHub"""
    if not GITHUB_TOKEN or not GITHUB_REPO:
        print("Warning: GitHub credentials not configured")
        return False

    try:
        # Prepare file content
        file_content = json.dumps(kb, indent=2)
        file_content_encoded = base64.b64encode(file_content.encode()).decode()

        # GitHub API headers
        headers = {
            'Authorization': f'token {GITHUB_TOKEN}',
            'Accept': 'application/vnd.github.v3+json'
        }

        file_url = f'https://api.github.com/repos/{GITHUB_REPO}/contents/{KB_FILE}'

        # Get current file SHA
        get_response = requests.get(file_url, headers=headers)
        if get_response.status_code == 200:
            current_sha = get_response.json()['sha']
        else:
            current_sha = None

        # Prepare commit payload
        commit_payload = {
            'message': f'[AUTO] Update Pandora\'s Box knowledge base from website scraper - {datetime.now().isoformat()}',
            'content': file_content_encoded,
            'branch': 'main'
        }

        if current_sha:
            commit_payload['sha'] = current_sha

        # Commit to GitHub
        response = requests.put(file_url, json=commit_payload, headers=headers)

        if response.status_code in [200, 201]:
            print(f"✓ Committed to GitHub")
            return True
        else:
            print(f"✗ GitHub commit failed: {response.status_code}")
            print(f"  Response: {response.json()}")
            return False
    except Exception as e:
        print(f"Error committing to GitHub: {e}")
        return False

def main():
    """Main scraper workflow"""
    print(f"\n{'='*60}")
    print(f"  PANDORA'S BOX OF ROX WEBSITE SCRAPER")
    print(f"  {datetime.now().isoformat()}")
    print(f"{'='*60}\n")

    # Fetch website
    print(f"Fetching {WEBSITE_URL}...")
    html = fetch_website()
    if not html:
        print("✗ Failed to fetch website")
        return False
    print("✓ Website fetched")

    # Parse website
    print("\nParsing website content...")
    scraped_data = parse_website(html)
    if not scraped_data:
        print("✗ No data extracted from website")
        return False
    print("✓ Website parsed")

    # Load current knowledge base
    print("\nLoading knowledge base...")
    kb = load_knowledge_base()
    print("✓ Knowledge base loaded")

    # Update with scraped data
    print("\nUpdating knowledge base...")
    kb, changes_made = update_knowledge_base(kb, scraped_data)

    if not changes_made:
        print("ℹ No changes detected")
        return True

    print("✓ Knowledge base updated")

    # Save locally
    print("\nSaving knowledge base...")
    if not save_knowledge_base(kb):
        print("✗ Failed to save knowledge base")
        return False
    print("✓ Knowledge base saved")

    # Commit to GitHub
    print("\nCommitting to GitHub...")
    if not commit_to_github(kb):
        print("✗ Failed to commit to GitHub")
        return False

    print("\n" + "="*60)
    print("  ✓ SCRAPE COMPLETE - RENDER REDEPLOY TRIGGERED")
    print("="*60 + "\n")

    return True

if __name__ == "__main__":
    success = main()
    exit(0 if success else 1)
