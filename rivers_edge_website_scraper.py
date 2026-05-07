#!/usr/bin/env python3
"""
River's Edge Trail Race Website Scraper
Automatically extracts race information from tejastrails.com/edge and related pages
Pulls from: race page, policies, about page, and aid-station-info
Updates knowledge base JSON on a scheduled basis.
"""

import requests
from bs4 import BeautifulSoup
import json
import os
import base64
from datetime import datetime

# Configuration
WEBSITE_URL = "https://www.tejastrails.com/edge"
POLICIES_URL = "https://www.tejastrails.com/policies"
ABOUT_URL = "https://www.tejastrails.com/about"
AID_STATION_URL = "https://www.tejastrails.com/aid-station-info"
KB_FILE = "rivers_edge_knowledge_base.json"
GITHUB_TOKEN = os.environ.get('GITHUB_TOKEN')
GITHUB_REPO = os.environ.get('GITHUB_REPO', 'davesmithey/Trailbot')

def fetch_url(url):
    """Fetch a webpage"""
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        return response.text
    except requests.RequestException as e:
        print(f"Error fetching {url}: {e}")
        return None

def parse_website(html):
    """Parse River's Edge race page and extract race information"""
    soup = BeautifulSoup(html, 'html.parser')
    data = {}

    # Extract race distances
    distances_section = soup.find(string=lambda s: s and "Races:" in s)
    if distances_section:
        distances_text = distances_section.strip()
        if ":" in distances_text:
            distances_str = distances_text.split(":", 1)[1].strip()
            distances = [d.strip() for d in distances_str.split(",")]
            distances = [d for d in distances if d]
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

    # Try to extract venue link
    for link in soup.find_all('a'):
        link_text = link.get_text()
        if link_text and any(venue in link_text for venue in ['Ranch', 'Park', 'Trail']):
            data['venue_name'] = link_text.strip()
            print(f"✓ Found venue: {link_text.strip()}")
            break

    return data

def parse_policies(html):
    """Parse policies page and extract policy information"""
    soup = BeautifulSoup(html, 'html.parser')
    policies_text = []

    # Try to find the main content area
    main_content = soup.find('main') or soup.find('article') or soup.find('div', class_='content')
    if main_content:
        for element in main_content.find_all(['h2', 'h3', 'p']):
            text = element.get_text(strip=True)
            if text:
                policies_text.append(text)

    # If no main content found, try extracting from body
    if not policies_text:
        for element in soup.find_all(['h2', 'h3', 'p']):
            text = element.get_text(strip=True)
            if text and len(text) > 10:
                policies_text.append(text)

    policies_content = "\n".join(policies_text)
    return {
        'policies_content': policies_content,
        'policies_raw_html': str(main_content) if main_content else None
    }

def parse_about(html):
    """Parse about page and extract company/race information"""
    soup = BeautifulSoup(html, 'html.parser')
    about_text = []

    # Try to find the main content area
    main_content = soup.find('main') or soup.find('article') or soup.find('div', class_='content')
    if main_content:
        for element in main_content.find_all(['h2', 'h3', 'p']):
            text = element.get_text(strip=True)
            if text:
                about_text.append(text)

    # If no main content found, try extracting from body
    if not about_text:
        for element in soup.find_all(['h2', 'h3', 'p']):
            text = element.get_text(strip=True)
            if text and len(text) > 10:
                about_text.append(text)

    about_content = "\n".join(about_text)
    return {
        'about_content': about_content,
        'about_raw_html': str(main_content) if main_content else None
    }

def parse_aid_stations(html):
    """Parse aid station information page"""
    soup = BeautifulSoup(html, 'html.parser')
    aid_text = []

    # Try to find the main content area
    main_content = soup.find('main') or soup.find('article') or soup.find('div', class_='content')
    if main_content:
        for element in main_content.find_all(['h2', 'h3', 'p', 'li']):
            text = element.get_text(strip=True)
            if text:
                aid_text.append(text)

    # If no main content found, try extracting from body
    if not aid_text:
        for element in soup.find_all(['h2', 'h3', 'p', 'li']):
            text = element.get_text(strip=True)
            if text and len(text) > 5:
                aid_text.append(text)

    aid_content = "\n".join(aid_text)
    return {
        'aid_stations_content': aid_content,
        'aid_stations_raw_html': str(main_content) if main_content else None
    }

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
            print(f"✓ Updated venue: {new_venue}")

    # Update policies
    if 'policies_content' in scraped_data:
        old_policies = kb.get('policies', {}).get('content', '')
        new_policies = scraped_data['policies_content']
        if old_policies != new_policies and new_policies:
            if 'policies' not in kb:
                kb['policies'] = {}
            kb['policies']['content'] = new_policies
            kb['policies']['last_updated'] = datetime.now().isoformat()
            changes_made = True
            print(f"✓ Updated policies ({len(new_policies)} chars)")

    # Update about
    if 'about_content' in scraped_data:
        old_about = kb.get('about', {}).get('content', '')
        new_about = scraped_data['about_content']
        if old_about != new_about and new_about:
            if 'about' not in kb:
                kb['about'] = {}
            kb['about']['content'] = new_about
            kb['about']['last_updated'] = datetime.now().isoformat()
            changes_made = True
            print(f"✓ Updated about section ({len(new_about)} chars)")

    # Update aid stations
    if 'aid_stations_content' in scraped_data:
        old_aid = kb.get('aid_stations', {}).get('content', '')
        new_aid = scraped_data['aid_stations_content']
        if old_aid != new_aid and new_aid:
            if 'aid_stations' not in kb:
                kb['aid_stations'] = {}
            kb['aid_stations']['content'] = new_aid
            kb['aid_stations']['last_updated'] = datetime.now().isoformat()
            changes_made = True
            print(f"✓ Updated aid stations ({len(new_aid)} chars)")

    # Add last updated timestamp
    kb['_lastUpdated'] = datetime.now().isoformat()
    kb['_source'] = 'Automated scraper from tejastrails.com/edge, /policies, /about, and /aid-station-info'

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
        file_content = json.dumps(kb, indent=2)
        file_content_encoded = base64.b64encode(file_content.encode()).decode()

        headers = {
            'Authorization': f'token {GITHUB_TOKEN}',
            'Accept': 'application/vnd.github.v3+json'
        }

        file_url = f'https://api.github.com/repos/{GITHUB_REPO}/contents/{KB_FILE}'

        get_response = requests.get(file_url, headers=headers)
        if get_response.status_code == 200:
            current_sha = get_response.json()['sha']
        else:
            current_sha = None

        commit_payload = {
            'message': f'[AUTO] Update River\'s Edge knowledge base from website scraper - {datetime.now().isoformat()}',
            'content': file_content_encoded,
            'branch': 'main'
        }

        if current_sha:
            commit_payload['sha'] = current_sha

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
    print(f"  RIVER'S EDGE TRAIL RACE WEBSITE SCRAPER")
    print(f"  {datetime.now().isoformat()}")
    print(f"{'='*60}\n")

    scraped_data = {}

    # Fetch and parse race page
    print(f"Fetching {WEBSITE_URL}...")
    try:
        html = fetch_url(WEBSITE_URL)
        if html:
            print("✓ Race page fetched")
            print("\nParsing race page content...")
            race_data = parse_website(html)
            scraped_data.update(race_data)
            print("✓ Race page parsed")
        else:
            print("⚠ Failed to fetch race page (continuing)")
    except Exception as e:
        print(f"❌ ERROR fetching race page: {e}")
        import traceback
        traceback.print_exc()

    # Fetch and parse policies
    print(f"\nFetching {POLICIES_URL}...")
    try:
        policies_html = fetch_url(POLICIES_URL)
        if policies_html:
            print("✓ Policies page fetched")
            print("\nParsing policies...")
            policies_data = parse_policies(policies_html)
            scraped_data.update(policies_data)
            print("✓ Policies parsed")
        else:
            print("⚠ Failed to fetch policies page (continuing)")
    except Exception as e:
        print(f"❌ ERROR fetching policies: {e}")
        import traceback
        traceback.print_exc()

    # Fetch and parse about page
    print(f"\nFetching {ABOUT_URL}...")
    try:
        about_html = fetch_url(ABOUT_URL)
        if about_html:
            print("✓ About page fetched")
            print("\nParsing about section...")
            about_data = parse_about(about_html)
            scraped_data.update(about_data)
            print("✓ About section parsed")
        else:
            print("⚠ Failed to fetch about page (continuing)")
    except Exception as e:
        print(f"❌ ERROR fetching about: {e}")
        import traceback
        traceback.print_exc()

    # Fetch and parse aid station info
    print(f"\nFetching {AID_STATION_URL}...")
    try:
        aid_html = fetch_url(AID_STATION_URL)
        if aid_html:
            print("✓ Aid station info page fetched")
            print("\nParsing aid station information...")
            aid_data = parse_aid_stations(aid_html)
            scraped_data.update(aid_data)
            print("✓ Aid station info parsed")
        else:
            print("⚠ Failed to fetch aid station info (continuing)")
    except Exception as e:
        print(f"❌ ERROR fetching aid stations: {e}")
        import traceback
        traceback.print_exc()

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
