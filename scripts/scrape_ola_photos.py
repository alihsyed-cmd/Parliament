#!/usr/bin/env python3
"""
One-time script: scrape MPP and cabinet photo URLs from ola.org.

Reads the two Ontario CSVs, fetches each MPP's profile page, extracts the
photo URL, and writes a new column `photo_url` to each CSV.

This is intentionally a one-off utility — Phase 4 will replace it with
API-first ingestion via OpenNorth's Represent API. Don't make this elegant
or general-purpose; just make it work for this dataset, then delete.

Usage:
    python3 scripts/scrape_ola_photos.py

Outputs:
    Updates data/provincial/ontario/Contacts of all Ontario members.csv (adds photo_url column)
    Updates data/provincial/ontario/cabinet.csv (adds photo_url column)
    Logs successes/failures to stdout
"""

import csv
import re
import sys
import time
from pathlib import Path
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

REPO_ROOT = Path(__file__).resolve().parent.parent
MPP_CSV = REPO_ROOT / "data" / "provincial" / "ontario" / "Contacts of all Ontario members.csv"
CABINET_CSV = REPO_ROOT / "data" / "provincial" / "ontario" / "cabinet.csv"

USER_AGENT = "ParliamentApp/1.0 (civic tech project; one-time data sync)"
DELAY_SECONDS = 1.0  # politeness — don't hammer ola.org


def slugify(first: str, last: str) -> str:
    """Construct ola.org URL slug from name. e.g. 'Peter', 'Bethlenfalvy' -> 'peter-bethlenfalvy'."""
    name = f"{first} {last}".lower().strip()
    # Remove accents and special characters
    name = re.sub(r"[^\w\s-]", "", name)
    # Replace spaces and underscores with hyphens
    name = re.sub(r"[\s_]+", "-", name)
    return name


def extract_photo_url(html: str, page_url: str) -> str | None:
    """Extract the MPP photo URL from a profile page.

    ola.org profile pages typically contain an <img> tag inside a div with
    a class like 'member-photo' or similar. We look for the largest image
    that's not a logo/icon, falling back to og:image meta if needed.
    """
    soup = BeautifulSoup(html, "html.parser")

    # Strategy 1: og:image meta tag (most reliable for "main image of this page")
    og_image = soup.find("meta", property="og:image")
    if og_image and og_image.get("content"):
        url = og_image["content"]
        if "logo" not in url.lower() and "favicon" not in url.lower():
            return urljoin(page_url, url)

    # Strategy 2: look for an img with member/photo/portrait in src or class
    for img in soup.find_all("img"):
        src = img.get("src", "")
        css_class = " ".join(img.get("class", []))
        alt = img.get("alt", "")
        combined = f"{src} {css_class} {alt}".lower()
        if any(keyword in combined for keyword in ["member", "portrait", "photo", "headshot"]):
            if "logo" not in combined and "icon" not in combined:
                return urljoin(page_url, src)

    return None


def fetch_photo(profile_url: str) -> tuple[str | None, str | None]:
    """Fetch a profile page and extract the photo URL.

    Returns (photo_url, error_message). On success, error_message is None.
    """
    try:
        response = requests.get(
            profile_url,
            headers={"User-Agent": USER_AGENT},
            timeout=15,
        )
        if response.status_code == 404:
            return None, f"404 Not Found: {profile_url}"
        if response.status_code != 200:
            return None, f"HTTP {response.status_code}: {profile_url}"

        photo_url = extract_photo_url(response.text, profile_url)
        if not photo_url:
            return None, f"No photo found in page: {profile_url}"

        return photo_url, None
    except requests.RequestException as e:
        return None, f"Request failed: {e}"


def update_cabinet_csv():
    """Add photo_url column to cabinet.csv. Uses existing profile_url column."""
    print(f"\n=== Processing {CABINET_CSV.name} ===")

    with open(CABINET_CSV, newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))

    if not rows:
        print("Empty CSV, skipping")
        return

    updated_rows = []
    success_count = 0
    fail_count = 0

    for row in rows:
        profile_url = row.get("profile_url")
        name = row.get("full_name", "?")

        if not profile_url:
            print(f"  SKIP {name}: no profile_url in CSV")
            row["photo_url"] = ""
            updated_rows.append(row)
            fail_count += 1
            continue

        photo_url, error = fetch_photo(profile_url)
        if photo_url:
            print(f"  OK   {name}: {photo_url}")
            row["photo_url"] = photo_url
            success_count += 1
        else:
            print(f"  FAIL {name}: {error}")
            row["photo_url"] = ""
            fail_count += 1

        updated_rows.append(row)
        time.sleep(DELAY_SECONDS)

    # Write back with new column
    fieldnames = list(rows[0].keys())
    if "photo_url" not in fieldnames:
        fieldnames.append("photo_url")

    with open(CABINET_CSV, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(updated_rows)

    print(f"\n  Cabinet CSV: {success_count} succeeded, {fail_count} failed")


def update_mpp_csv():
    """Add photo_url column to MPP CSV. Constructs URLs from name fields."""
    print(f"\n=== Processing {MPP_CSV.name} ===")

    with open(MPP_CSV, newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))

    if not rows:
        print("Empty CSV, skipping")
        return

    # The MPP CSV has many rows per MPP (different office types).
    # Build a unique-by-name set so we only fetch each profile once.
    seen_slugs: dict[str, str] = {}  # slug -> photo_url
    success_count = 0
    fail_count = 0

    for row in rows:
        first = row.get("First name", "").strip()
        last = row.get("Last name", "").strip()
        if not first or not last:
            row["photo_url"] = ""
            continue

        slug = slugify(first, last)

        if slug in seen_slugs:
            row["photo_url"] = seen_slugs[slug]
            continue

        profile_url = f"https://www.ola.org/en/members/all/{slug}"
        photo_url, error = fetch_photo(profile_url)

        if photo_url:
            print(f"  OK   {first} {last}: {photo_url}")
            seen_slugs[slug] = photo_url
            row["photo_url"] = photo_url
            success_count += 1
        else:
            print(f"  FAIL {first} {last}: {error}")
            seen_slugs[slug] = ""
            row["photo_url"] = ""
            fail_count += 1

        time.sleep(DELAY_SECONDS)

    # Write back
    fieldnames = list(rows[0].keys())
    if "photo_url" not in fieldnames:
        fieldnames.append("photo_url")

    with open(MPP_CSV, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    unique = len(seen_slugs)
    print(f"\n  MPP CSV: {success_count} unique MPPs succeeded, {fail_count} failed (out of {unique} unique names)")


if __name__ == "__main__":
    print("Scraping ola.org photo URLs...")
    print(f"Politeness delay: {DELAY_SECONDS}s between requests")

    update_cabinet_csv()
    update_mpp_csv()

    print("\nDone.")
