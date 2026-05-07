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
import re

# Configuration
WEBSITE_URL = "https://www.tejastrails.com/edge"
POLICIES_URL = "https://www.tejastrails.com/policies"
ABOUT_URL = "https://www.tejastrails.com/about"
AID_STATION_URL = "https://www.tejastrails.com/aid-station-info"
KB_FILE = "rivers_edge_knowledge_base.json"
GITHUB_TOKEN = os.environ.get('GITHUB_TOKEN')
GITHUB_REPO = os.environ.get('GITHUB_REPO', 'davesmithey/Trailbot')

CONTENT_TAGS = ['h1', 'h2', 'h3', 'h4', 'p', 'li']

def clean_text(text):
    """Normalize webpage text without smashing words together."""
    if not text:
        return ''
    text = text.replace('\xa0', ' ')
    return re.sub(r'\s+', ' ', text).strip()

def extract_main_content(soup):
    """Find the page content area, falling back to the body if needed."""
    return (
        soup.find('main')
        or soup.find('article')
        or soup.find('div', class_='content')
        or soup.body
        or soup
    )

def extract_page_text(soup):
    """Extract readable page text from headings, paragraphs, and list items."""
    content = extract_main_content(soup)
    text_blocks = []
    for element in content.find_all(CONTENT_TAGS):
        text = clean_text(element.get_text(' ', strip=True))
        if not text:
            continue
        # Squarespace pages repeat large navigation menus. Keep only useful page
        # content and drop tiny/common nav labels.
        if text in {'Open Menu Close Menu', 'Back', 'Register Now', 'Store'}:
            continue
        if len(text) < 3:
            continue
        if not text_blocks or text_blocks[-1] != text:
            text_blocks.append(text)
    return "\n".join(text_blocks), str(content)

def extract_sections(page_text):
    """Group full page text under headings so the chatbot can find details."""
    sections = {}
    current_heading = 'Overview'
    current_lines = []
    for line in page_text.splitlines():
        line = clean_text(line)
        if not line:
            continue
        if line.endswith('▼'):
            line = line[:-1].strip()
        is_heading = (
            len(line) <= 90
            and not line.endswith('.')
            and (
                line.isupper()
                or line.startswith('...')
                or line.startswith('…')
                or line.lower() in {
                    'race schedule',
                    'course information',
                    'aid stations',
                    'drop bags',
                    'swag & stuff',
                    'rules',
                    'pacers',
                    'awards',
                    'family-friendly',
                    'getting here',
                    'lodging',
                    'history',
                    'questions',
                    'volunteering',
                    'results',
                    'timing',
                    'overall awards',
                    'age group awards',
                    'about',
                    'about tejas trails',
                    'river\'s edge',
                }
            )
        )
        if is_heading and current_lines:
            sections[current_heading] = "\n".join(current_lines).strip()
            current_heading = line
            current_lines = []
        elif is_heading:
            current_heading = line
        else:
            current_lines.append(line)
    if current_lines:
        sections[current_heading] = "\n".join(current_lines).strip()
    return sections

def extract_distances(page_text):
    """Extract race distances from page text (e.g., '50 mi', '26.2 mi')"""
    distances = []
    # Look for patterns like "50 mi", "26.2 miles", "50-mile", etc.
    patterns = [
        r'(\d+\.?\d*)\s*(?:mi|mile|miles)',
        r'(\d+\.?\d*)\s*(?:km|kilometer|kilometers)',
    ]

    found_distances = set()
    for pattern in patterns:
        matches = re.finditer(pattern, page_text, re.IGNORECASE)
        for match in matches:
            distance_str = match.group(0).strip()
            if distance_str not in found_distances:
                distances.append(distance_str)
                found_distances.add(distance_str)

    return distances

def extract_race_date(page_text):
    """Extract race date from page text"""
    # Look for patterns like "May 15", "May 15-16", "May 15-16, 2026"
    date_patterns = [
        r'(?:January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{1,2}(?:\s*-\s*\d{1,2})?\s*(?:,?\s*\d{4})?',
    ]

    for pattern in date_patterns:
        match = re.search(pattern, page_text, re.IGNORECASE)
        if match:
            return match.group(0).strip()

    return None

def extract_venue_info(page_text):
    """Extract venue name and location from page text"""
    # Look for common venue indicators
    venue_patterns = [
        r'(?:at|venue|located at|park|state park)\s+([A-Z][A-Za-z\s]+(?:Park|Ranch|Trail|Trail Run))',
        r'([A-Z][A-Za-z\s]+(?:Park|Ranch|Trail|Trail Run))\s*(?:,?\s+(?:near|in|at)\s+)?([A-Za-z\s]+,?\s*(?:TX|Texas))?',
    ]

    for pattern in venue_patterns:
        match = re.search(pattern, page_text)
        if match:
            venue_name = match.group(1).strip() if match.group(1) else None
            if venue_name:
                return venue_name

    return None

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

def parse_website(html, url_name="race"):
    """Parse website HTML and extract full page content"""
    soup = BeautifulSoup(html, 'html.parser')
    data = {}

    page_text, raw_html = extract_page_text(soup)
    if page_text:
        data[f'{url_name}_content'] = page_text
        data[f'{url_name}_sections'] = extract_sections(page_text)
        data[f'{url_name}_raw_html'] = raw_html
        print(f"✓ Found {url_name} page content ({len(page_text)} chars)")

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

    # Initialize race object if needed
    if 'race' not in kb:
        kb['race'] = {}
    if 'race_overview' not in kb:
        kb['race_overview'] = {}

    # Update River's Edge page content (race overview) and extract specific fields
    if 'rivers_edge_content' in scraped_data:
        old_content = kb['race_overview'].get('content', '')
        new_content = scraped_data['rivers_edge_content']

        if old_content != new_content:
            kb['race_overview']['content'] = new_content
            kb['race_overview']['sections'] = scraped_data.get('rivers_edge_sections', {})
            kb['race_overview']['last_updated'] = datetime.now().isoformat()
            changes_made = True
            print(f"✓ Updated River's Edge race overview ({len(new_content)} chars)")

            # Extract specific fields from race page content
            # Extract distances
            distances = extract_distances(new_content)
            if distances and kb['race'].get('distances') != distances:
                kb['race']['distances'] = distances
                changes_made = True
                print(f"✓ Extracted distances: {', '.join(distances)}")

            # Extract race date
            race_date = extract_race_date(new_content)
            if race_date and kb['race'].get('date') != race_date:
                kb['race']['date'] = race_date
                changes_made = True
                print(f"✓ Extracted race date: {race_date}")

            # Extract venue
            venue = extract_venue_info(new_content)
            if venue:
                if 'location' not in kb['race']:
                    kb['race']['location'] = {}
                if kb['race']['location'].get('venue') != venue:
                    kb['race']['location']['venue'] = venue
                    changes_made = True
                    print(f"✓ Extracted venue: {venue}")

    # Update Policies page content
    if 'policies_content' in scraped_data:
        # Initialize policies object if needed
        if 'policies' not in kb:
            kb['policies'] = {}

        old_content = kb['policies'].get('content', '')
        new_content = scraped_data['policies_content']

        if old_content != new_content:
            kb['policies']['content'] = new_content
            kb['policies']['sections'] = scraped_data.get('policies_sections', {})
            kb['policies']['last_updated'] = datetime.now().isoformat()
            changes_made = True
            print(f"✓ Updated policies ({len(new_content)} chars)")

    # Update About page content
    if 'about_content' in scraped_data:
        # Initialize about object if needed
        if 'about' not in kb:
            kb['about'] = {}

        old_content = kb['about'].get('content', '')
        new_content = scraped_data['about_content']

        if old_content != new_content:
            kb['about']['content'] = new_content
            kb['about']['sections'] = scraped_data.get('about_sections', {})
            kb['about']['last_updated'] = datetime.now().isoformat()
            changes_made = True
            print(f"✓ Updated about ({len(new_content)} chars)")

    # Update Aid Stations page content
    if 'aid_stations_content' in scraped_data:
        # Initialize aid_stations object if needed
        if 'aid_stations' not in kb:
            kb['aid_stations'] = {}

        old_content = kb['aid_stations'].get('content', '')
        new_content = scraped_data['aid_stations_content']

        if old_content != new_content:
            kb['aid_stations']['content'] = new_content
            kb['aid_stations']['sections'] = scraped_data.get('aid_stations_sections', {})
            kb['aid_stations']['last_updated'] = datetime.now().isoformat()
            changes_made = True
            print(f"✓ Updated aid stations ({len(new_content)} chars)")

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
        print("Warning: GitHub credentials not configured; skipping remote commit")
        return None

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
    html = fetch_url(WEBSITE_URL)
    if html:
        print("✓ Race page fetched")
        print("\nParsing race page content...")
        race_data = parse_website(html, "rivers_edge")
        scraped_data.update(race_data)
        print("✓ Race page parsed")
    else:
        print("⚠ Failed to fetch race page (continuing)")

    # Fetch and parse policies page
    print(f"\nFetching {POLICIES_URL}...")
    policies_html = fetch_url(POLICIES_URL)
    if policies_html:
        print("✓ Policies page fetched")
        print("\nParsing policies...")
        policies_data = parse_website(policies_html, "policies")
        scraped_data.update(policies_data)
        print("✓ Policies parsed")
    else:
        print("⚠ Failed to fetch policies page (continuing)")

    # Fetch and parse about page
    print(f"\nFetching {ABOUT_URL}...")
    about_html = fetch_url(ABOUT_URL)
    if about_html:
        print("✓ About page fetched")
        print("\nParsing about section...")
        about_data = parse_website(about_html, "about")
        scraped_data.update(about_data)
        print("✓ About section parsed")
    else:
        print("⚠ Failed to fetch about page (continuing)")

    # Fetch and parse aid station info
    print(f"\nFetching {AID_STATION_URL}...")
    aid_html = fetch_url(AID_STATION_URL)
    if aid_html:
        print("✓ Aid station info page fetched")
        print("\nParsing aid station information...")
        aid_data = parse_website(aid_html, "aid_stations")
        scraped_data.update(aid_data)
        print("✓ Aid station info parsed")
    else:
        print("⚠ Failed to fetch aid station info (continuing)")

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
    github_result = commit_to_github(kb)
    if github_result is False:
        print("✗ Failed to commit to GitHub")
        return False

    print("\n" + "="*60)
    if github_result is None:
        print("  ✓ SCRAPE COMPLETE - LOCAL KNOWLEDGE BASE UPDATED")
    else:
        print("  ✓ SCRAPE COMPLETE - RENDER REDEPLOY TRIGGERED")
    print("="*60 + "\n")

    return True

if __name__ == "__main__":
    success = main()
    exit(0 if success else 1)
