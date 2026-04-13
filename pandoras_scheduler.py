#!/usr/bin/env python3
"""
Pandora's Box of Rox Website Scraper Scheduler
Runs the scraper every hour to keep knowledge base updated
"""

import schedule
import time
import sys
from pandoras_website_scraper import main

def schedule_scraper():
    """Schedule the scraper to run every hour"""
    schedule.every().hour.do(main)

    print("\n" + "="*60)
    print("  PANDORA'S BOX SCRAPER SCHEDULER STARTED")
    print("  Scraper will run every hour")
    print("="*60 + "\n")

    while True:
        try:
            schedule.run_pending()
            time.sleep(30)  # Check every 30 seconds if a task is due
        except KeyboardInterrupt:
            print("\nScheduler stopped")
            sys.exit(0)
        except Exception as e:
            print(f"Error in scheduler: {e}")
            time.sleep(30)

if __name__ == "__main__":
    schedule_scraper()
