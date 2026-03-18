#!/usr/bin/env python3
"""
Hippo Trail Fest Website Scraper Scheduler
Runs the website scraper on a schedule (hourly by default).
This can run as a background process alongside the Flask app.
"""

import schedule
import time
import threading
import sys
from datetime import datetime
import hippo_website_scraper

def run_scraper():
    """Run the website scraper"""
    try:
        print(f"\n[{datetime.now().isoformat()}] Running scheduled scrape...")
        success = hippo_website_scraper.main()
        if success:
            print(f"[{datetime.now().isoformat()}] Scrape completed successfully")
        else:
            print(f"[{datetime.now().isoformat()}] Scrape completed with errors")
    except Exception as e:
        print(f"[{datetime.now().isoformat()}] Error running scraper: {e}")

def schedule_scraper(interval_hours=1):
    """Schedule the scraper to run at regular intervals"""
    schedule.every(interval_hours).hours.do(run_scraper)

    print(f"\n{'='*60}")
    print(f"  HIPPO TRAIL FEST SCRAPER SCHEDULER")
    print(f"  Interval: Every {interval_hours} hour(s)")
    print(f"  Started: {datetime.now().isoformat()}")
    print(f"{'='*60}\n")

    # Run the scheduler loop
    while True:
        schedule.run_pending()
        time.sleep(60)  # Check every minute if a job needs to run

def run_scraper_background(interval_hours=1):
    """Run scheduler in a background thread"""
    scheduler_thread = threading.Thread(
        target=schedule_scraper,
        args=(interval_hours,),
        daemon=True
    )
    scheduler_thread.start()
    return scheduler_thread

if __name__ == "__main__":
    # Parse command line arguments
    interval = 1  # Default: every hour
    if len(sys.argv) > 1:
        try:
            interval = int(sys.argv[1])
        except ValueError:
            print(f"Usage: {sys.argv[0]} [hours between scrapes]")
            sys.exit(1)

    # Run scheduler
    schedule_scraper(interval)
