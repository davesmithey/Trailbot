# Pandora's Box of Rox Chatbot - Implementation Guide

**Status:** Ready for deployment
**Race:** Pandora's Box of Rox
**Website:** tejastrails.com/pandoras
**Deployment Target:** Separate Render service (like Hippo)

---

## Files Created

✅ **pandoras_website_scraper.py** - Scraper that extracts race data hourly
✅ **pandoras_knowledge_base.json** - Race-specific knowledge (auto-updated)
✅ **pandoras_chatbot_backend.py** - Flask API (direct HTTP to Claude)
✅ **pandoras_chatbot_widget.html** - Chat widget (ready to embed)

---

## Deployment Steps

### Step 1: Create New Render Service

1. Go to Render dashboard: https://dashboard.render.com
2. Click "New +" → "Web Service"
3. Connect to your GitHub repo (davesmithey/Trailbot)
4. Configure:
   - **Name:** `pandoras-chatbot` (or similar)
   - **Environment:** Python 3.14
   - **Build Command:** `pip install -r requirements.txt`
   - **Start Command:** `gunicorn pandoras_chatbot_backend:app`

### Step 2: Add Environment Variables

In Render Settings → Environment:
```
ANTHROPIC_API_KEY=sk-ant-... (same as Hippo)
GITHUB_TOKEN=ghp_... (same as Hippo)
GITHUB_REPO=davesmithey/Trailbot (same as Hippo)
FLASK_ENV=production
```

### Step 3: Commit Files to GitHub

In your `davesmithey/Trailbot` repo, add:
- `pandoras_website_scraper.py`
- `pandoras_knowledge_base.json`
- `pandoras_chatbot_backend.py`
- `pandoras_chatbot_widget.html`

Create a new folder `race_chatbots/` to organize them:
```
race_chatbots/
├── hippo/
│   ├── hippo_chatbot_backend.py
│   ├── hippo_website_scraper.py
│   └── hippo_knowledge_base.json
│
├── pandoras/
│   ├── pandoras_chatbot_backend.py
│   ├── pandoras_website_scraper.py
│   └── pandoras_knowledge_base.json
```

### Step 4: Embed Widget on Website

On the Pandora's Box of Rox page (tejastrails.com/pandoras), add this HTML:

```html
<!-- Chat Widget Script -->
<script src="https://your-render-url.onrender.com/static/pandoras_chatbot_widget.html"></script>
```

Or copy-paste the entire widget HTML into a Squarespace Code block.

### Step 5: Update Widget Endpoint

In `pandoras_chatbot_widget.html`, update the backend URL:

Change:
```javascript
const apiUrl = 'https://hippo-chatbot-xgu0.onrender.com/chat';
```

To:
```javascript
const apiUrl = 'https://pandoras-chatbot-XXXX.onrender.com/chat';  // Your Render URL
```

### Step 6: Test

1. Go to tejastrails.com/pandoras
2. Click the chat button (💬)
3. Ask: "When is Pandora's Box of Rox?"
4. Should respond: "April 25, 2026"

---

## What Gets Extracted Hourly

The scraper automatically pulls:
- ✅ Race distances (52.4 mi, 26.2 mi, 13.1 mi, 8 mi, 4 mi, Youth 1 mi)
- ✅ Date (April 25, 2026)
- ✅ Venue (Reveille Peak Ranch, Burnet, TX)
- ✅ Terrain and course details
- ✅ Race features (family-friendly, beginner-friendly, etc.)

---

## Manual Fields (Edit in JSON)

Some fields aren't on the website, so edit `pandoras_knowledge_base.json` directly in GitHub:
- Schedule/start times (update when they're finalized)
- Registration prices
- Cutoff times
- Specific aid station locations

---

## Optional: Create Scheduler for Pandora's

If you want the scraper to run hourly, create a simple scheduler:

**pandoras_scheduler.py:**
```python
import schedule
import time
from pandoras_website_scraper import main

def schedule_scraper():
    schedule.every().hour.do(main)
    
    while True:
        schedule.run_pending()
        time.sleep(30)

if __name__ == "__main__":
    schedule_scraper()
```

Then add to Procfile:
```
web: gunicorn pandoras_chatbot_backend:app
scheduler: python pandoras_scheduler.py
```

---

## Quick Comparison: Hippo vs Pandora's

| Feature | Hippo | Pandora's |
|---------|-------|-----------|
| URL | tejastrails.com/hippo | tejastrails.com/pandoras |
| Date | March (seasonal) | April 25, 2026 |
| Distances | 5K-50K | 4 mi-52.4 mi |
| Venue | Hippo Social Club, Hutto TX | Reveille Peak Ranch, Burnet TX |
| Terrain | Loop course | Multi-loop trail |
| Family Friendly | Yes (Hippo Haul) | Yes (Youth 1 mi) |
| Spectators | Not mentioned | Free admission |
| Post-race | Food, games | Food trucks, swimming, games |

---

## Troubleshooting

**Chat not loading:**
- Check Render service is "Live"
- Verify environment variables are set
- Check browser console for errors

**No schedule/time info:**
- Schedule isn't on website yet, so it shows "TBD"
- Update manually in `pandoras_knowledge_base.json` once dates are finalized

**Scraper not running:**
- Only runs if you set up scheduler process (optional)
- Manual updates via GitHub edit work fine

---

## Next Race: Use This Template

Once Pandora's is working, create the next race using this same pattern:
1. Copy `pandoras_chatbot_backend.py` → `[racename]_chatbot_backend.py`
2. Copy `pandoras_website_scraper.py` → `[racename]_website_scraper.py`
3. Create `[racename]_knowledge_base.json` with race data
4. Create new Render service
5. Deploy

Or start planning the **multi-race system** when you have 3-4 races ready.

---

## Timeline

- **Immediate:** Deploy Pandora's Box chatbot (1-2 hours setup)
- **This Week:** Get 2-3 more races running
- **Next Week:** Consider multi-race system architecture for remaining 14 races

---

## Questions?

Refer to:
- `DEPLOYMENT_GUIDE.md` - General deployment help
- `CHATBOT_FIX_REPORT.md` - Technical details
- `SCALING_PLAN_MULTI_RACE.md` - Plan for all 18 races

