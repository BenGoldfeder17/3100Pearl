#!/usr/bin/env python3
"""
3100 Pearl Apartment Availability Monitor v2
==============================================
Uses Playwright for full JS rendering to scrape RentCafe-powered sites.
Sends push notifications via ntfy.sh, SMS via Twilio, email, or macOS alerts.

Setup:
    pip install playwright beautifulsoup4 requests
    playwright install chromium

Usage:
    python 3100pearl_monitor_v2.py                # Run once
    python 3100pearl_monitor_v2.py --watch         # Poll every 30 min
    python 3100pearl_monitor_v2.py --watch 15      # Poll every 15 min
    python 3100pearl_monitor_v2.py --test-notify   # Test notifications
"""

import json
import re
import sys
import time
import hashlib
import smtplib
import os
import subprocess
import platform
from datetime import datetime, date
from pathlib import Path
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

try:
    import requests
except ImportError:
    subprocess.check_call([sys.executable, "-m", "pip", "install",
                           "requests", "--break-system-packages", "-q"])
    import requests

try:
    from bs4 import BeautifulSoup
except ImportError:
    subprocess.check_call([sys.executable, "-m", "pip", "install",
                           "beautifulsoup4", "--break-system-packages", "-q"])
    from bs4 import BeautifulSoup

# ╔══════════════════════════════════════════════════════════════════════════╗
# ║  CONFIGURATION                                                          ║
# ╚══════════════════════════════════════════════════════════════════════════╝

CONFIG = {
    # ── Search Filters ──────────────────────────────────────────────────
    "target_types":    ["studio", "1 bed", "1 bedroom", "1 br", "1bd",
                        "1br", "s1", "a1", "a2", "a3", "a4", "a5"],
    "max_rent":        2000,
    "preferred_rent":  1800,
    "min_move_in":     None,

    # ── Data Storage ────────────────────────────────────────────────────
    "data_dir":        Path.home() / ".3100pearl",

    # ── Playwright ──────────────────────────────────────────────────────
    "headless":        True,        # False to watch the browser
    "timeout_ms":      45000,       # page load timeout
    "wait_after_load": 5000,        # extra ms to wait for dynamic content

    # ── Notifications (enable the ones you want) ────────────────────────
    #
    # OPTION 1: ntfy.sh — FREE, no signup, works on iOS + Android + desktop
    #   1. Install the ntfy app on your phone (iOS App Store / Google Play)
    #   2. Subscribe to your topic (e.g. "ben-3100pearl")
    #   3. Set ntfy_enabled = True and ntfy_topic below
    #   That's it. Instant push notifications.
    #
    "ntfy_enabled":    True,
    "ntfy_topic":      "ben-3100pearl",       # change to your own secret topic name
    "ntfy_server":     "https://ntfy.sh",     # or self-host

    # OPTION 2: Twilio SMS — pay-per-message, very reliable
    #   Get credentials at https://console.twilio.com
    #
    "twilio_enabled":  False,
    "twilio_sid":      "",           # your Account SID
    "twilio_token":    "",           # your Auth Token
    "twilio_from":     "",           # your Twilio phone number (+1...)
    "twilio_to":       "",           # your personal phone number (+1...)

    # OPTION 3: Email (Gmail SMTP)
    #   Use an App Password: https://myaccount.google.com/apppasswords
    #
    "email_enabled":   False,
    "smtp_server":     "smtp.gmail.com",
    "smtp_port":       587,
    "smtp_user":       "",           # your-email@gmail.com
    "smtp_pass":       "",           # 16-char app password
    "alert_to":        "",           # recipient email

    # OPTION 4: macOS native notifications (no setup needed on Mac)
    "macos_notify":    platform.system() == "Darwin",

    # OPTION 5: Pushover — $5 one-time, very polished iOS/Android app
    "pushover_enabled": False,
    "pushover_user":    "",
    "pushover_token":   "",
}

# ── Target URLs ─────────────────────────────────────────────────────────────
URLS = {
    "live3100pearl_avail":  "https://live3100pearl.com/check-availability/",
    "live3100pearl_plans":  "https://live3100pearl.com/floorplans/",
    "apartments_com":       "https://www.apartments.com/3100-pearl-boulder-co/rycnge1/",
    "apartmentfinder":      "https://www.apartmentfinder.com/Colorado/Boulder-Apartments/3100-Pearl-Apartments-jzcvce5",
}

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
    ),
}

# ╔══════════════════════════════════════════════════════════════════════════╗
# ║  HELPERS                                                                ║
# ╚══════════════════════════════════════════════════════════════════════════╝

def ensure_dirs():
    CONFIG["data_dir"].mkdir(parents=True, exist_ok=True)

def load_json(filename):
    path = CONFIG["data_dir"] / filename
    if path.exists():
        return json.loads(path.read_text())
    return {}

def save_json(filename, data):
    path = CONFIG["data_dir"] / filename
    path.write_text(json.dumps(data, indent=2, default=str))

def parse_price(text):
    if not text:
        return None
    match = re.search(r'\$?([\d,]+)', str(text))
    if match:
        val = int(match.group(1).replace(",", ""))
        if 500 <= val <= 10000:  # sanity check for rent range
            return val
    return None

def parse_sqft(text):
    if not text:
        return None
    match = re.search(r'(\d{3,4})\s*(?:sq\.?\s*ft|sqft|SF)', str(text), re.IGNORECASE)
    return int(match.group(1)) if match else None

def parse_date_from_text(text):
    if not text:
        return None
    text = text.lower().strip()
    if "now" in text or "immediate" in text or "today" in text:
        return date.today().isoformat()

    for pattern, fmt in [
        (r'(\d{1,2})[/\-](\d{1,2})[/\-](\d{4})', None),
        (r'(\d{1,2})[/\-](\d{1,2})[/\-](\d{2})', None),
    ]:
        m = re.search(pattern, text)
        if m:
            raw = m.group(0).replace("-", "/")
            for f in ["%m/%d/%Y", "%m/%d/%y"]:
                try:
                    return datetime.strptime(raw, f).date().isoformat()
                except ValueError:
                    continue

    month_pat = r'(jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|jun(?:e)?|jul(?:y)?|aug(?:ust)?|sep(?:tember)?|oct(?:ober)?|nov(?:ember)?|dec(?:ember)?)\s+(\d{1,2})?,?\s*(\d{4})'
    m = re.search(month_pat, text, re.IGNORECASE)
    if m:
        for fmt in ["%B %d, %Y", "%B %d %Y", "%b %d, %Y", "%b %d %Y", "%B %Y", "%b %Y"]:
            try:
                return datetime.strptime(m.group(0).strip().title(), fmt).date().isoformat()
            except ValueError:
                continue

    # Short date without year: "Apr 07", "May 20", etc. — assume current year
    short_pat = r'(jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|jun(?:e)?|jul(?:y)?|aug(?:ust)?|sep(?:tember)?|oct(?:ober)?|nov(?:ember)?|dec(?:ember)?)\s+(\d{1,2})'
    m = re.search(short_pat, text, re.IGNORECASE)
    if m:
        year = date.today().year
        for fmt in ["%b %d %Y", "%B %d %Y"]:
            try:
                return datetime.strptime(f"{m.group(0).strip().title()} {year}", fmt).date().isoformat()
            except ValueError:
                continue

    return None

def is_target_type(type_str):
    if not type_str:
        return False
    t = type_str.lower().strip()
    return any(target in t for target in CONFIG["target_types"])

def is_valid_move_in(date_str):
    if not date_str or not CONFIG["min_move_in"]:
        return True
    try:
        return date.fromisoformat(date_str) >= date.fromisoformat(CONFIG["min_move_in"])
    except (ValueError, TypeError):
        return True

def unit_hash(u):
    key = f"{u.get('unit','')}-{u.get('floor_plan','')}-{u.get('price','')}-{u.get('source','')}"
    return hashlib.md5(key.encode()).hexdigest()[:12]

def budget_tier(price):
    if not price:
        return "unknown"
    if price <= CONFIG["preferred_rent"]:
        return "preferred"
    if price <= CONFIG["max_rent"]:
        return "acceptable"
    return "over"

# ╔══════════════════════════════════════════════════════════════════════════╗
# ║  PLAYWRIGHT SCRAPERS                                                    ║
# ╚══════════════════════════════════════════════════════════════════════════╝

def get_browser():
    """Initialize Playwright and return browser + page."""
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("Installing Playwright...")
        subprocess.check_call([sys.executable, "-m", "pip", "install",
                               "playwright", "--break-system-packages", "-q"])
        subprocess.check_call([sys.executable, "-m", "playwright", "install", "chromium"])
        from playwright.sync_api import sync_playwright

    pw = sync_playwright().start()
    browser = pw.chromium.launch(headless=CONFIG["headless"])
    context = browser.new_context(
        user_agent=HEADERS["User-Agent"],
        viewport={"width": 1280, "height": 900},
    )
    page = context.new_page()
    return pw, browser, page


def scrape_with_playwright(page, url, source_name):
    """Load a page with full JS rendering and extract unit data."""
    units = []
    try:
        print(f"    Loading {source_name}...")
        page.goto(url, wait_until="networkidle", timeout=CONFIG["timeout_ms"])
        page.wait_for_timeout(CONFIG["wait_after_load"])

        # ── Strategy 1: Intercept any JSON data in the page ──────────
        # Many RentCafe sites embed unit data in script tags or window vars
        json_data = page.evaluate("""() => {
            const results = [];

            // Check for RentCafe/Yardi embedded data
            const scripts = document.querySelectorAll('script');
            for (const s of scripts) {
                const text = s.textContent || '';
                // Look for unit/pricing arrays
                const patterns = [
                    /(?:units|floorplans|apartments|availableUnits)\\s*[:=]\\s*(\\[[\\s\\S]*?\\]);/i,
                    /(?:window\.__data__|window\.pageData)\s*=\s*(\{[\s\S]*?\});/i,
                    /JSON\.parse\('(.*?)'\)/g,
                ];
                for (const pat of patterns) {
                    const m = pat.exec(text);
                    if (m) {
                        try {
                            results.push(JSON.parse(m[1]));
                        } catch(e) {}
                    }
                }
            }

            // Check for structured data
            const ldScripts = document.querySelectorAll('script[type="application/ld+json"]');
            for (const s of ldScripts) {
                try {
                    results.push(JSON.parse(s.textContent));
                } catch(e) {}
            }

            return results;
        }""")

        for data in json_data:
            units.extend(_extract_from_json(data, source_name, url))

        # ── Strategy 2: Parse the rendered DOM ───────────────────────
        html = page.content()
        soup = BeautifulSoup(html, "html.parser")
        units.extend(_extract_from_dom(soup, source_name, url))

        # ── Strategy 3: Target specific RentCafe patterns ────────────
        units.extend(_extract_rentcafe_units(page, source_name, url))

        print(f"    ✓ {source_name}: {len(units)} raw listings extracted")

    except Exception as e:
        print(f"    ⚠ {source_name} error: {e}")

    return units


def _extract_from_json(data, source, url):
    """Extract units from embedded JSON data."""
    units = []

    if isinstance(data, list):
        for item in data:
            units.extend(_extract_from_json(item, source, url))
        return units

    if not isinstance(data, dict):
        return units

    # JSON-LD ApartmentComplex
    if data.get("@type") in ("ApartmentComplex", "Apartment", "Product"):
        catalog = data.get("hasOfferCatalog", {})
        for item in catalog.get("itemListElement", []):
            offer = item.get("item", item)
            price = None
            if "offers" in offer:
                price = parse_price(offer["offers"].get("price") or offer["offers"].get("lowPrice"))
            units.append({
                "source": source, "url": url,
                "floor_plan": offer.get("name", ""),
                "unit": "", "type": offer.get("name", ""),
                "price": price,
                "sqft": offer.get("floorSize", {}).get("value") if isinstance(offer.get("floorSize"), dict) else None,
                "available_date": None,
            })

    # Generic unit arrays
    for key in ("units", "floorplans", "apartments", "availableUnits", "results"):
        if key in data and isinstance(data[key], list):
            for item in data[key]:
                if isinstance(item, dict):
                    units.append({
                        "source": source, "url": url,
                        "floor_plan": item.get("FloorplanName", item.get("floorplan", item.get("name", ""))),
                        "unit": item.get("UnitNumber", item.get("unit", item.get("apartmentNumber", ""))),
                        "type": item.get("FloorplanName", item.get("Beds", item.get("bedrooms", ""))),
                        "price": parse_price(item.get("MinimumRent", item.get("rent", item.get("price")))),
                        "sqft": parse_sqft(str(item.get("MinimumSQFT", item.get("sqft", item.get("area", ""))))),
                        "available_date": parse_date_from_text(
                            str(item.get("AvailableDate", item.get("availableDate", item.get("moveIn", ""))))
                        ),
                    })

    return units


def _extract_from_dom(soup, source, url):
    """Extract units from rendered HTML DOM."""
    units = []

    # Wide net: any card/row that contains pricing info
    selectors = [
        '[class*="pricingGridItem"]', '[class*="floorplan"]', '[class*="unitContainer"]',
        '[class*="unit-card"]', '[class*="listing-card"]', '[class*="result-card"]',
        '[class*="fpGroup"]', '[class*="availabilityRow"]', '[class*="modelContainer"]',
        'tr[class*="unit"]', 'tr[class*="avail"]',
        '[data-unit]', '[data-floorplan]',
    ]

    seen_texts = set()
    for sel in selectors:
        for card in soup.select(sel):
            text = card.get_text(" ", strip=True)
            text_key = text[:100]
            if text_key in seen_texts:
                continue
            seen_texts.add(text_key)

            plan_name = ""
            price = None
            sqft = None
            avail = None
            unit_num = ""

            # Extract plan name
            for name_sel in ['[class*="Name"]', '[class*="title"]', 'h3', 'h4', '.name']:
                el = card.select_one(name_sel)
                if el:
                    plan_name = el.get_text(strip=True)
                    break

            # Extract price
            for price_sel in ['[class*="rice"]', '[class*="ent"]', '[class*="cost"]']:
                el = card.select_one(price_sel)
                if el:
                    price = parse_price(el.get_text())
                    if price:
                        break
            if not price:
                price = parse_price(text)

            # Extract sqft
            sqft = parse_sqft(text)

            # Extract availability date
            for date_sel in ['[class*="vail"]', '[class*="oveIn"]', '[class*="date"]']:
                el = card.select_one(date_sel)
                if el:
                    avail = parse_date_from_text(el.get_text())
                    if avail:
                        break

            # Extract unit number
            for unit_sel in ['[class*="nit"]', '[class*="apt"]']:
                el = card.select_one(unit_sel)
                if el:
                    t = el.get_text(strip=True)
                    if re.match(r'^[A-Z]?\d{1,4}[A-Z]?$', t, re.IGNORECASE):
                        unit_num = t
                        break

            if plan_name or price:
                units.append({
                    "source": source, "url": url,
                    "floor_plan": plan_name, "unit": unit_num,
                    "type": plan_name, "price": price,
                    "sqft": sqft, "available_date": avail,
                })

    return units


def _extract_rentcafe_units(page, source, url):
    """Target RentCafe-specific DOM patterns common in Kairoi properties."""
    units = []
    try:
        data = page.evaluate("""() => {
            const units = [];

            // RentCafe availability tables
            const rows = document.querySelectorAll(
                '.availabilityTable tr, .fp-group-row, .unit-row, ' +
                '[class*="AvailableUnit"], [class*="unitRow"], [class*="unit-item"]'
            );
            for (const row of rows) {
                const cells = row.querySelectorAll('td, .cell, [class*="col"]');
                const text = row.textContent || '';
                const priceMatch = text.match(/\\$([\\d,]+)/);
                const sqftMatch = text.match(/(\\d{3,4})\\s*(?:sq|SF)/i);
                const dateMatch = text.match(/(\\d{1,2}\\/\\d{1,2}\\/\\d{2,4})/);
                const unitMatch = text.match(/(?:unit|apt)\\s*#?\\s*([A-Z]?\\d{1,4}[A-Z]?)/i);

                if (priceMatch) {
                    units.push({
                        text: text.substring(0, 200),
                        price: priceMatch[1],
                        sqft: sqftMatch ? sqftMatch[1] : null,
                        date: dateMatch ? dateMatch[1] : null,
                        unit: unitMatch ? unitMatch[1] : '',
                    });
                }
            }

            // RentCafe pricing cards
            const cards = document.querySelectorAll(
                '.fp-card, .floor-plan-card, [class*="floorPlan"], [class*="pricingCard"]'
            );
            for (const card of cards) {
                const name = (card.querySelector('h2, h3, h4, .fp-name, [class*="planName"]') || {}).textContent || '';
                const priceEl = card.querySelector('[class*="price"], [class*="rent"], .fp-price');
                const sqftEl = card.querySelector('[class*="sqft"], [class*="area"], .fp-sqft');
                const dateEl = card.querySelector('[class*="avail"], [class*="date"], .fp-avail');

                units.push({
                    text: name,
                    price: priceEl ? priceEl.textContent : null,
                    sqft: sqftEl ? sqftEl.textContent : null,
                    date: dateEl ? dateEl.textContent : null,
                    unit: '',
                });
            }

            // JD FloorPlans unit cards (Kairoi/RealPage widget)
            const jdCards = document.querySelectorAll('[data-jd-fp-selector="unit-card"]');
            for (const card of jdCards) {
                const allSpans = card.querySelectorAll('span');
                const spanTexts = [];
                for (const s of allSpans) {
                    const t = s.textContent.trim();
                    if (t && t.length < 50) spanTexts.push(t);
                }

                const unitEl = card.querySelector('.jd-fp-card-info__title--large');
                const priceEl = card.querySelector('[data-jd-fp-adp="display"]');
                const availEl = card.querySelector('.jd-fp-card-info__text--brand');
                const imgEl = card.querySelector('img');

                // Extract fields from spans
                let bedType = '';
                let bathCount = '';
                let sqft = null;
                let planName = '';
                for (const t of spanTexts) {
                    if (/studio/i.test(t)) bedType = 'Studio';
                    else if (/\\d+\\s*bed/i.test(t)) bedType = t;
                    if (/\\d+\\s*bath/i.test(t)) bathCount = t;
                    const sqftM = t.match(/(\\d{3,4})\\s*sq/i);
                    if (sqftM) sqft = sqftM[1];
                    // Plan name is typically first span, short uppercase like "A2R", "S1R"
                    if (/^[A-Z][A-Z0-9]{1,4}R?$/i.test(t) && !planName) planName = t;
                }

                if (priceEl) {
                    const unitNum = unitEl ? unitEl.textContent.trim().replace(/^#/, '') : '';
                    // Derive floor from unit number (e.g. B-121 -> floor 1, C-305 -> floor 3)
                    const floorMatch = unitNum.match(/[A-Z]-?(\\d)/i);
                    const floor = floorMatch ? floorMatch[1] : null;

                    units.push({
                        text: bedType,
                        planName: planName,
                        beds: bedType,
                        baths: bathCount,
                        price: priceEl.textContent,
                        sqft: sqft,
                        date: availEl ? availEl.textContent.replace(/available\\s*/i, '').trim() : null,
                        unit: unitNum,
                        floor: floor,
                        image: imgEl ? imgEl.src : null,
                    });
                }
            }

            // Also grab from any iframes (some RentCafe sites use these)
            try {
                const iframes = document.querySelectorAll('iframe');
                for (const iframe of iframes) {
                    const doc = iframe.contentDocument;
                    if (!doc) continue;
                    const iRows = doc.querySelectorAll('tr, .unit-row');
                    for (const row of iRows) {
                        const text = row.textContent || '';
                        const priceMatch = text.match(/\\$([\\d,]+)/);
                        if (priceMatch) {
                            units.push({
                                text: text.substring(0, 200),
                                price: priceMatch[1],
                                sqft: null, date: null, unit: ''
                            });
                        }
                    }
                }
            } catch(e) {}

            return units;
        }""")

        for item in data:
            price = parse_price(item.get("price"))
            if not price:
                continue
            units.append({
                "source": source, "url": url,
                "floor_plan": item.get("planName") or item.get("text", "").strip()[:60],
                "unit": item.get("unit", ""),
                "type": item.get("text", ""),
                "beds": item.get("beds", ""),
                "baths": item.get("baths", ""),
                "floor": item.get("floor"),
                "price": price,
                "sqft": parse_sqft(item.get("sqft") or ""),
                "available_date": parse_date_from_text(item.get("date") or ""),
                "image_url": item.get("image"),
            })

    except Exception as e:
        print(f"    ⚠ RentCafe extraction error: {e}")

    return units

# ╔══════════════════════════════════════════════════════════════════════════╗
# ║  NOTIFICATION SYSTEM                                                    ║
# ╚══════════════════════════════════════════════════════════════════════════╝

def notify(title, message, units=None, priority="default"):
    """Send notification via all enabled channels."""
    sent = []

    if CONFIG["ntfy_enabled"]:
        if _notify_ntfy(title, message, priority, units):
            sent.append("ntfy")

    if CONFIG["twilio_enabled"]:
        if _notify_twilio(title, message):
            sent.append("SMS")

    if CONFIG["email_enabled"]:
        if _notify_email(title, message, units):
            sent.append("email")

    if CONFIG["macos_notify"]:
        _notify_macos(title, message)
        sent.append("macOS")

    if CONFIG["pushover_enabled"]:
        if _notify_pushover(title, message, priority):
            sent.append("Pushover")

    if sent:
        print(f"  📬 Notified via: {', '.join(sent)}")
    else:
        print(f"  ⚠ No notification channels configured/working")

    return sent


def _notify_ntfy(title, message, priority="default", units=None):
    """
    Send push notification via ntfy.sh.
    FREE, no signup. Install the ntfy app on your phone and
    subscribe to your topic to receive alerts.
    Sends one notification per unit (with floor plan image) or a single
    summary if no image URLs are available.
    """
    try:
        url = f"{CONFIG['ntfy_server']}/{CONFIG['ntfy_topic']}"
        success = False

        # Collect units that have images for individual notifications
        units_with_images = [u for u in (units or []) if u.get("image_url")]
        units_without_images = [u for u in (units or []) if not u.get("image_url")]

        # Send individual notifications with floor plan images
        for u in units_with_images:
            p = f"${u['price']:,}/mo" if u.get("price") else "Price TBD"
            lines = []
            if u.get("beds"):
                bed_bath = u["beds"]
                if u.get("baths"):
                    bed_bath += f", {u['baths']}"
                lines.append(bed_bath)
            if u.get("sqft"):
                lines.append(f"{u['sqft']} sq ft")
            if u.get("floor"):
                lines.append(f"Floor {u['floor']}")
            if u.get("available_date"):
                lines.append(f"Available: {u['available_date']}")
            if u.get("floor_plan"):
                lines.append(f"Plan: {u['floor_plan']}")
            body = "\n".join(lines)

            resp = requests.post(url, headers={
                "Title": f"Unit {u.get('unit', '?')} - {p}",
                "Priority": priority,
                "Tags": "house,mag",
                "Click": URLS["live3100pearl_avail"],
                "Actions": f"view, Open 3100 Pearl, {URLS['live3100pearl_avail']}",
                "Attach": u["image_url"],
                "Filename": "floorplan.svg",
            }, data=body.encode("utf-8"), timeout=10)
            if resp.status_code == 200:
                success = True

        # Send summary for any units without images
        if units_without_images or not units_with_images:
            remaining_msg = message if not units_with_images else format_unit_summary(units_without_images)
            resp = requests.post(url, headers={
                "Title": title,
                "Priority": priority,
                "Tags": "house,mag",
                "Click": URLS["live3100pearl_avail"],
                "Actions": f"view, Open 3100 Pearl, {URLS['live3100pearl_avail']}",
            }, data=remaining_msg.encode("utf-8"), timeout=10)
            if resp.status_code == 200:
                success = True

        return success
    except Exception as e:
        print(f"    ⚠ ntfy error: {e}")
        return False


def _notify_twilio(title, message):
    """Send SMS via Twilio."""
    try:
        url = f"https://api.twilio.com/2010-04-01/Accounts/{CONFIG['twilio_sid']}/Messages.json"
        body = f"🏠 {title}\n\n{message}"
        if len(body) > 1500:
            body = body[:1497] + "..."
        resp = requests.post(url, auth=(CONFIG["twilio_sid"], CONFIG["twilio_token"]), data={
            "From": CONFIG["twilio_from"],
            "To": CONFIG["twilio_to"],
            "Body": body,
        }, timeout=10)
        return resp.status_code in (200, 201)
    except Exception as e:
        print(f"    ⚠ Twilio error: {e}")
        return False


def _notify_email(title, message, units=None):
    """Send email alert via SMTP."""
    try:
        msg = MIMEMultipart()
        msg["From"] = CONFIG["smtp_user"]
        msg["To"] = CONFIG["alert_to"]
        msg["Subject"] = f"🏠 {title}"

        body = message
        if units:
            body += "\n\n" + "=" * 40
            for u in units:
                p = f"${u['price']:,}" if u.get("price") else "TBD"
                body += f"\n\n{u.get('floor_plan','?')} — {p}/mo"
                body += f"\n  {u.get('type','')}"
                if u.get('sqft'):
                    body += f" · {u['sqft']} SF"
                if u.get('available_date'):
                    body += f"\n  Available: {u['available_date']}"
                body += f"\n  Source: {u.get('source','')}"
            body += f"\n\n{'=' * 40}"
            body += f"\n\nCheck availability: {URLS['live3100pearl_avail']}"

        msg.attach(MIMEText(body, "plain"))
        with smtplib.SMTP(CONFIG["smtp_server"], CONFIG["smtp_port"]) as server:
            server.starttls()
            server.login(CONFIG["smtp_user"], CONFIG["smtp_pass"])
            server.send_message(msg)
        return True
    except Exception as e:
        print(f"    ⚠ Email error: {e}")
        return False


def _notify_macos(title, message):
    """macOS native notification center."""
    try:
        msg_escaped = message.replace('"', '\\"').replace("'", "\\'")[:200]
        title_escaped = title.replace('"', '\\"')
        subprocess.run([
            "osascript", "-e",
            f'display notification "{msg_escaped}" with title "{title_escaped}" sound name "Glass"'
        ], timeout=5, capture_output=True)
    except Exception:
        pass


def _notify_pushover(title, message, priority="default"):
    """Send via Pushover (pushover.net)."""
    prio_map = {"min": -2, "low": -1, "default": 0, "high": 1, "urgent": 2}
    try:
        resp = requests.post("https://api.pushover.net/1/messages.json", data={
            "token": CONFIG["pushover_token"],
            "user": CONFIG["pushover_user"],
            "title": title,
            "message": message,
            "priority": prio_map.get(priority, 0),
            "url": URLS["live3100pearl_avail"],
            "url_title": "Check Availability",
            "sound": "cashregister",
        }, timeout=10)
        return resp.status_code == 200
    except Exception as e:
        print(f"    ⚠ Pushover error: {e}")
        return False

# ╔══════════════════════════════════════════════════════════════════════════╗
# ║  CORE LOGIC                                                             ║
# ╚══════════════════════════════════════════════════════════════════════════╝

def filter_units(units):
    """Filter and deduplicate units matching our criteria."""
    filtered = []
    seen = set()

    for u in units:
        h = unit_hash(u)
        if h in seen:
            continue
        seen.add(h)

        type_str = u.get("type", "") or u.get("floor_plan", "")
        if not is_target_type(type_str):
            continue

        price = u.get("price")
        if price and price > CONFIG["max_rent"]:
            continue

        if not is_valid_move_in(u.get("available_date")):
            continue

        u["tier"] = budget_tier(price)
        u["hash"] = h
        filtered.append(u)

    # Remove plan-only entries (no price, no unit number) — these are just
    # floor plan overview cards, not actual available units
    filtered = [u for u in filtered if u.get("price") or u.get("unit")]

    return filtered


def detect_changes(current):
    """Compare with last scan, detect new and removed units."""
    last_seen = load_json("last_seen.json")
    prev_hashes = set(last_seen.get("hashes", []))
    curr_hashes = {u["hash"] for u in current}

    new = [u for u in current if u["hash"] not in prev_hashes]
    removed_hashes = prev_hashes - curr_hashes

    return new, removed_hashes


def format_unit_summary(units):
    """Format units into a notification-friendly string."""
    if not units:
        return "No matching units."

    lines = []
    for u in sorted(units, key=lambda x: x.get("price") or 99999):
        p = f"${u['price']:,}" if u.get("price") else "TBD"
        emoji = "🟢" if u.get("tier") == "preferred" else "🟡"
        line = f"{emoji} {u.get('floor_plan','?')} — {p}/mo"
        if u.get("sqft"):
            line += f" · {u['sqft']}SF"
        if u.get("available_date"):
            line += f" (avail {u['available_date']})"
        if u.get("unit"):
            line += f" [Unit {u['unit']}]"
        lines.append(line)

    return "\n".join(lines)


def print_results(matches, new_units, removed_count):
    """Pretty-print to terminal."""
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"\n{'═' * 60}")
    print(f"  🏠 3100 PEARL AVAILABILITY MONITOR v2")
    print(f"  📅 {now}")
    move_in_str = f" | {CONFIG['min_move_in']}+ move-in" if CONFIG["min_move_in"] else ""
    print(f"  🔍 Studio/1BR | ≤${CONFIG['max_rent']:,}/mo{move_in_str}")
    print(f"{'═' * 60}")

    if not matches:
        print(f"\n  ❌ No matching units found this scan.\n")
        print(f"  → Check manually: {URLS['live3100pearl_avail']}")
        print(f"{'═' * 60}\n")
        return

    new_hashes = {u["hash"] for u in new_units}

    for u in sorted(matches, key=lambda x: x.get("price") or 99999):
        is_new = u["hash"] in new_hashes
        price_str = f"${u['price']:,}/mo" if u.get("price") else "Price TBD"
        tier = u.get("tier", "unknown")

        icon = {"preferred": "🟢", "acceptable": "🟡", "unknown": "⚪"}.get(tier, "⚪")
        label = {"preferred": "SWEET SPOT", "acceptable": "IN BUDGET", "unknown": "PRICE TBD"}.get(tier)
        new_tag = " 🆕 NEW!" if is_new else ""

        print(f"\n  {icon} {u.get('floor_plan', 'Unknown')}{new_tag}")
        print(f"     💰 {price_str}  ({label})")
        if u.get("beds"):
            bed_bath = f"     🛏  {u['beds']}"
            if u.get("baths"):
                bed_bath += f", {u['baths']}"
            print(bed_bath)
        if u.get("sqft"):
            print(f"     📐 {u['sqft']} sq ft")
        if u.get("floor"):
            print(f"     🏢 Floor {u['floor']}")
        if u.get("available_date"):
            print(f"     📅 Available: {u['available_date']}")
        if u.get("unit"):
            print(f"     🔑 Unit: {u['unit']}")
        print(f"     🌐 {u.get('source', '')}")

    print(f"\n{'─' * 60}")
    pref_count = sum(1 for u in matches if u.get("tier") == "preferred")
    print(f"  Total: {len(matches)} | 🟢 ≤$1,800: {pref_count} | 🆕 New: {len(new_units)} | ❌ Removed: {removed_count}")
    print(f"{'═' * 60}\n")


def run_scan():
    """Run a full scan with Playwright."""
    ensure_dirs()
    print(f"\n⏳ Starting Playwright scan...")

    pw, browser, page = get_browser()
    all_units = []

    try:
        # Scrape all sources
        for name, url in URLS.items():
            print(f"\n  → {name}")
            units = scrape_with_playwright(page, url, name)
            all_units.extend(units)

        print(f"\n  📊 Total raw listings: {len(all_units)}")

    finally:
        browser.close()
        pw.stop()

    # Filter
    matches = filter_units(all_units)
    new_units, removed_hashes = detect_changes(matches)

    # Save state
    save_json("last_seen.json", {
        "hashes": [u["hash"] for u in matches],
        "last_scan": datetime.now().isoformat(),
        "count": len(matches),
    })

    # Save history
    history = load_json("history.json")
    scan_key = datetime.now().strftime("%Y-%m-%d_%H:%M")
    history[scan_key] = {
        "matches": len(matches),
        "new": len(new_units),
        "removed": len(removed_hashes),
        "units": matches,
    }
    # Keep last 500 scans
    if len(history) > 500:
        keys = sorted(history.keys())
        for k in keys[:-500]:
            del history[k]
    save_json("history.json", history)

    # Save latest for dashboard
    save_json("latest.json", {
        "scan_time": datetime.now().isoformat(),
        "matches": matches,
        "new_units": new_units,
    })

    # Print results
    print_results(matches, new_units, len(removed_hashes))

    # Notify on new units
    if new_units:
        title = f"{len(new_units)} New Unit{'s' if len(new_units)>1 else ''} at 3100 Pearl!"
        summary = format_unit_summary(new_units)
        priority = "high" if any(u.get("tier") == "preferred" for u in new_units) else "default"
        notify(title, summary, new_units, priority)
    elif not matches:
        # Optionally notify on zero matches (disabled by default to avoid spam)
        pass

    return matches, new_units


def test_notifications():
    """Send a test notification to verify setup."""
    print("\n🔔 Sending test notifications...\n")
    test_units = [{
        "floor_plan": "S1R (TEST)", "type": "Studio", "price": 1745,
        "sqft": 573, "available_date": "2025-07-01", "unit": "108",
        "source": "TEST", "tier": "preferred",
    }]
    notify(
        "Test Alert — 3100 Pearl Monitor",
        "🟢 S1R (TEST) — $1,745/mo · 573SF (avail 2025-07-01)\n\nThis is a test notification.",
        test_units,
        "default",
    )
    print("\n✅ Done. Check your devices.\n")


def watch_mode(interval_min=30):
    """Continuously poll."""
    print(f"👁  Watch mode: scanning every {interval_min} min (Ctrl+C to stop)\n")
    while True:
        try:
            run_scan()
            next_scan = datetime.now().strftime("%H:%M")
            print(f"💤 Next scan at ~{next_scan} + {interval_min}min\n")
            time.sleep(interval_min * 60)
        except KeyboardInterrupt:
            print("\n\n👋 Monitor stopped.")
            sys.exit(0)
        except Exception as e:
            print(f"\n⚠ Scan error: {e}")
            print(f"  Retrying in {interval_min} min...\n")
            time.sleep(interval_min * 60)


# ╔══════════════════════════════════════════════════════════════════════════╗
# ║  MAIN                                                                   ║
# ╚══════════════════════════════════════════════════════════════════════════╝

if __name__ == "__main__":
    if "--test-notify" in sys.argv:
        test_notifications()
    elif "--watch" in sys.argv:
        idx = sys.argv.index("--watch")
        interval = int(sys.argv[idx + 1]) if len(sys.argv) > idx + 1 else 30
        watch_mode(interval)
    else:
        run_scan()
