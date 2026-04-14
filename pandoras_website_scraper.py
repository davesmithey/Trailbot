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
import re

# Configuration
WEBSITE_URL = "https://www.tejastrails.com/pandora"
POLICIES_URL = "https://www.tejastrails.com/policies"
KB_FILE = "pandoras_knowledge_base.json"
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

    page_text, raw_html = extract_page_text(soup)
    if page_text:
        data['pandoras_content'] = page_text
        data['pandoras_sections'] = extract_sections(page_text)
        data['pandoras_raw_html'] = raw_html
        print(f"✓ Found Pandora page content ({len(page_text)} chars)")

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

def fetch_policies():
    """Fetch the Tejas Trails policies page"""
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
        response = requests.get(POLICIES_URL, headers=headers, timeout=10)
        response.raise_for_status()
        return response.text
    except requests.RequestException as e:
        print(f"Error fetching policies page: {e}")
        return None

def parse_policies(html):
    """Parse policies page and extract policy information"""
    soup = BeautifulSoup(html, 'html.parser')
    policies_content, raw_html = extract_page_text(soup)

    return {
        'policies_content': policies_content,
        'policies_sections': extract_sections(policies_content),
        'policies_raw_html': raw_html
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

        if 'venue_location' in scraped_data:
            old_city = location_data.get('city')
            new_city = scraped_data['venue_location']
            if old_city != new_city:
                location_data['city'] = new_city
                changes_made = True

        if changes_made and 'venue_name' in scraped_data:
            print(f"✓ Updated venue: {scraped_data['venue_name']}, {scraped_data.get('venue_location', '')}")

    # Update policies if provided
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

        if 'policies_sections' in scraped_data:
            kb.setdefault('policies', {})['sections'] = scraped_data['policies_sections']

    # Store full source page text so the chatbot can answer detailed questions
    # that are not represented by the small structured fields above.
    if 'pandoras_content' in scraped_data:
        source_pages = kb.setdefault('source_pages', {})
        pandoras_page = source_pages.setdefault('pandoras', {})
        if (
            pandoras_page.get('content') != scraped_data['pandoras_content']
            or pandoras_page.get('sections') != scraped_data.get('pandoras_sections', {})
        ):
            pandoras_page['url'] = WEBSITE_URL
            pandoras_page['content'] = scraped_data['pandoras_content']
            pandoras_page['sections'] = scraped_data.get('pandoras_sections', {})
            pandoras_page['last_updated'] = datetime.now().isoformat()
            changes_made = True
            print(f"✓ Updated full Pandora page content ({len(scraped_data['pandoras_content'])} chars)")

    if 'policies_content' in scraped_data:
        source_pages = kb.setdefault('source_pages', {})
        policies_page = source_pages.setdefault('policies', {})
        if (
            policies_page.get('content') != scraped_data['policies_content']
            or policies_page.get('sections') != scraped_data.get('policies_sections', {})
        ):
            policies_page['url'] = POLICIES_URL
            policies_page['content'] = scraped_data['policies_content']
            policies_page['sections'] = scraped_data.get('policies_sections', {})
            policies_page['last_updated'] = datetime.now().isoformat()
            changes_made = True
            print(f"✓ Updated full policies page content ({len(scraped_data['policies_content'])} chars)")

    # Add last updated timestamp
    kb['_lastUpdated'] = datetime.now().isoformat()
    kb['_source'] = 'Automated scraper from tejastrails.com/pandoras and tejastrails.com/policies'

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

    # Fetch policies page
    print(f"\nFetching {POLICIES_URL}...")
    policies_html = fetch_policies()
    if policies_html:
        print("✓ Policies page fetched")
        print("\nParsing policies content...")
        policies_data = parse_policies(policies_html)
        if policies_data and policies_data.get('policies_content'):
            scraped_data.update(policies_data)
            print("✓ Policies parsed and added to scraped data")
        else:
            print("⚠ Could not extract policies content")
    else:
        print("⚠ Failed to fetch policies page (continuing without it)")

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
