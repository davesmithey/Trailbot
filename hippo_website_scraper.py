#!/usr/bin/env python3
"""
Hippo Trail Fest Website Scraper
Automatically extracts race information from tejastrails.com/hippo
and updates the knowledge base JSON on a scheduled basis.
"""

import requests
from bs4 import BeautifulSoup
import json
import os
import base64
from datetime import datetime

# Configuration
WEBSITE_URL = "https://www.tejastrails.com/hippo"
KB_FILE = "hippo_knowledge_base.json"
GITHUB_TOKEN = os.environ.get('GITHUB_TOKEN')
GITHUB_REPO = os.environ.get('GITHUB_REPO', 'davesmithey/Trailbot')

def fetch_website():
    """Fetch the Hippo Trail Fest webpage"""
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
    distances_section = soup.find(string=lambda s: s and "RACE DISTANCES" in s)
    if distances_section:
        distances_text = distances_section.strip()
        # Extract distances from text like "RACE DISTANCES: 1 Mile Youth Run, 5k, ..."
        if ":" in distances_text:
            distances_str = distances_text.split(":", 1)[1].strip()
            # Parse individual distances
            distances = [d.strip() for d in distances_str.split(";")]
            distances = [d for d in distances if d]  # Remove empty strings
            data['distances'] = distances
            print(f"✓ Found {len(distances)} distances")

    # Extract schedule/start times
    schedule_items = []
    schedule_list = soup.find('ul')
    if schedule_list:
        for item in schedule_list.find_all('li'):
            text = item.get_text(strip=True)
            if 'am' in text.lower() or 'pm' in text.lower():
                schedule_items.append(text)

    if schedule_items:
        data['schedule_items'] = schedule_items
        print(f"✓ Found {len(schedule_items)} schedule items")

    # Extract venue/location info
    location_info = {}

    # Look for address
    address_elem = soup.find(string=lambda s: s and "Hippo Social Club" in s)
    if address_elem:
        location_info['venue'] = "Hippo Social Club"

    # Look for city/location text
    hutto_elem = soup.find(string=lambda s: s and "Hutto" in s)
    if hutto_elem:
        location_info['area'] = "Hutto, Texas"

    if location_info:
        data['location_info'] = location_info
        print(f"✓ Found location info: {location_info}")

    return data

def load_knowledge_base():
    """Load current knowledge base JSON"""
    try:
        with open(KB_FILE, 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        print(f"Warning: {KB_FILE} not found")
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

    # Update location
    if 'location_info' in scraped_data:
        if 'race' not in kb:
            kb['race'] = {}
        if 'location' not in kb['race']:
            kb['race']['location'] = {}

        location_data = scraped_data['location_info']
        if 'venue' in location_data:
            old_venue = kb['race']['location'].get('venue')
            new_venue = location_data['venue']
            if old_venue != new_venue:
                kb['race']['location']['venue'] = new_venue
                changes_made = True

        if 'area' in location_data:
            # This is informational, not necessarily in the structure
            pass

    # Update schedule times
    if 'schedule_items' in scraped_data:
        # Parse schedule items into structured format
        schedule_dict = parse_schedule_items(scraped_data['schedule_items'])

        if 'schedule' not in kb:
            kb['schedule'] = {}
        if 'raceWeekend' not in kb['schedule']:
            kb['schedule']['raceWeekend'] = {}
        if 'saturday' not in kb['schedule']['raceWeekend']:
            kb['schedule']['raceWeekend']['saturday'] = {}

        saturday = kb['schedule']['raceWeekend']['saturday']

        # Update start times if they exist
        if 'starts' in schedule_dict:
            old_starts = saturday.get('starts', {})
            new_starts = schedule_dict['starts']
            if old_starts != new_starts:
                saturday['starts'] = new_starts
                changes_made = True
                print(f"✓ Updated start times")

    # Add last updated timestamp
    kb['_lastUpdated'] = datetime.now().isoformat()
    kb['_source'] = 'Automated scraper from tejastrails.com/hippo'

    return kb, changes_made

def parse_schedule_items(items):
    """Parse schedule items into structured format"""
    schedule = {'starts': {}}

    for item in items:
        # Parse items like "7:30am: 50K Trail Run Start"
        if ':' in item:
            try:
                time_part, event_part = item.split(':', 1)
                time = time_part.strip()
                event = event_part.strip()

                # Extract distance/event name
                if '50K' in event or '50k' in event:
                    schedule['starts']['50K'] = time
                elif '20' in event and 'mile' in event.lower():
                    schedule['starts']['20mileAnd10mile'] = time
                elif '10 mile' in event.lower() and 'ruck' not in event.lower():
                    if '20mileAnd10mile' not in schedule['starts']:
                        schedule['starts']['20mileAnd10mile'] = time
                elif '10K' in event or '10k' in event:
                    if 'ruck' not in event.lower():
                        schedule['starts']['10K'] = time
                elif '5K' in event or '5k' in event:
                    schedule['starts']['5K'] = time
                elif '10 mile' in event.lower() and 'ruck' in event.lower():
                    schedule['starts']['10mileRuck'] = time
                elif '10K' in event and 'ruck' in event.lower():
                    schedule['starts']['10KRuck'] = time
                elif 'Youth' in event or '1 Mile' in event or '1 mile' in event:
                    schedule['starts']['youthMile'] = time
                elif 'Haul' in event or 'weight' in event.lower():
                    schedule['starts']['hippoHaul'] = time
            except:
                pass

    return schedule

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
            'message': f'[AUTO] Update knowledge base from website scraper - {datetime.now().isoformat()}',
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
    print(f"  HIPPO TRAIL FEST WEBSITE SCRAPER")
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
