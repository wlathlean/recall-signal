#!/usr/bin/env python3
"""Build the public Recall Signal dataset from official U.S. government sources."""

from __future__ import annotations

import csv
import html
import io
import json
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "public" / "data" / "tracker.json"
USER_AGENT = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 RecallSignal/0.1"

STATE_NAMES = {
    "Alabama": "AL", "Alaska": "AK", "Arizona": "AZ", "Arkansas": "AR",
    "California": "CA", "Colorado": "CO", "Connecticut": "CT", "Delaware": "DE",
    "Florida": "FL", "Georgia": "GA", "Hawaii": "HI", "Idaho": "ID",
    "Illinois": "IL", "Indiana": "IN", "Iowa": "IA", "Kansas": "KS",
    "Kentucky": "KY", "Louisiana": "LA", "Maine": "ME", "Maryland": "MD",
    "Massachusetts": "MA", "Michigan": "MI", "Minnesota": "MN", "Mississippi": "MS",
    "Missouri": "MO", "Montana": "MT", "Nebraska": "NE", "Nevada": "NV",
    "New Hampshire": "NH", "New Jersey": "NJ", "New Mexico": "NM", "New York": "NY",
    "North Carolina": "NC", "North Dakota": "ND", "Ohio": "OH", "Oklahoma": "OK",
    "Oregon": "OR", "Pennsylvania": "PA", "Rhode Island": "RI", "South Carolina": "SC",
    "South Dakota": "SD", "Tennessee": "TN", "Texas": "TX", "Utah": "UT",
    "Vermont": "VT", "Virginia": "VA", "Washington": "WA", "West Virginia": "WV",
    "Wisconsin": "WI", "Wyoming": "WY", "District of Columbia": "DC",
}
STATE_CODES = set(STATE_NAMES.values())
ALLERGENS = {
    "milk": ("milk", "dairy"), "egg": ("egg",), "fish": ("fish",),
    "shellfish": ("shellfish", "shrimp", "crab", "lobster"),
    "tree nuts": ("tree nut", "almond", "cashew", "walnut", "pistachio", "pecan", "hazelnut", "macadamia"),
    "peanut": ("peanut",), "wheat": ("wheat",), "soy": ("soy",), "sesame": ("sesame",),
}
RETAILERS = [
    "Amazon", "Costco", "Walmart", "Target", "H-E-B", "HEB", "Kroger", "QFC",
    "Fred Meyer", "Safeway", "Albertsons", "WinCo", "Trader Joe's", "Trader Joe’s",
]


def fetch(url: str, params: dict[str, str] | None = None) -> bytes:
    if params:
        url = f"{url}?{urllib.parse.urlencode(params)}"
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": "application/json,text/csv,text/html"})
    with urllib.request.urlopen(request, timeout=60) as response:
        return response.read()


def fetch_json(url: str, params: dict[str, str] | None = None):
    return json.loads(fetch(url, params).decode("utf-8-sig"))


def clean(value) -> str:
    value = html.unescape(str(value or ""))
    value = re.sub(r"<[^>]+>", " ", value)
    return re.sub(r"\s+", " ", value).strip()


def iso_date(value: str) -> str:
    digits = re.sub(r"\D", "", str(value or ""))
    if len(digits) >= 8:
        return f"{digits[:4]}-{digits[4:6]}-{digits[6:8]}"
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00")).date().isoformat()
    except ValueError:
        return str(value or "")[:10]


def states_from(text: str) -> list[str]:
    source = clean(text)
    lower = source.lower()
    if any(word in lower for word in ("nationwide", "throughout the united states", "all 50 states")):
        return ["US"]
    states = set()
    for name, code in STATE_NAMES.items():
        if re.search(rf"\b{re.escape(name)}\b", source, re.I):
            states.add(code)
    for token in re.findall(r"\b[A-Z]{2}\b", source):
        if token in STATE_CODES:
            states.add(token)
    return sorted(states)


def allergens_from(text: str) -> list[str]:
    lower = clean(text).lower()
    return [name for name, needles in ALLERGENS.items() if any(re.search(rf"\b{re.escape(n)}", lower) for n in needles)]


def retailers_from(text: str) -> list[str]:
    lower = clean(text).lower()
    found = []
    for retailer in RETAILERS:
        canonical = "H-E-B" if retailer == "HEB" else "Trader Joe's" if "Trader Joe" in retailer else retailer
        if retailer.lower() in lower and canonical not in found:
            found.append(canonical)
    return found


def severity_from(classification: str, text: str = "") -> int:
    combined = f"{classification} {text}".lower()
    if "class i" in combined or any(x in combined for x in ("death", "hospital", "botul", "listeria", "e. coli")):
        return 4
    if "class ii" in combined or any(x in combined for x in ("salmonella", "injury", "fire", "choking")):
        return 3
    if "class iii" in combined:
        return 2
    return 2


def action_for(section: str, reason: str, remedy: str = "") -> str:
    if remedy:
        return clean(remedy)
    lower = reason.lower()
    if section in ("food", "pet_food"):
        if "allergen" in lower or "undeclared" in lower:
            return "Do not consume if the allergen applies. Check the affected codes, then return or discard the product as directed."
        return "Do not consume or serve the affected product. Check the affected codes and follow the official disposal or return instructions."
    if "fire" in lower or "burn" in lower or "injur" in lower:
        return "Stop using the affected product and follow the official repair, replacement, or refund instructions."
    return "Stop using the affected product and follow the official recall instructions."


def product_category(text: str) -> str:
    lower = text.lower()
    groups = [
        ("Baby & child", ("baby", "infant", "child", "toddler", "stroller", "crib", "toy", "car seat")),
        ("Sports & outdoors", ("sport", "hockey", "helmet", "bike", "bicycle", "exercise", "pool", "camp", "outdoor")),
        ("Tools & power equipment", ("tool", "saw", "drill", "mower", "generator", "battery pack", "power equipment")),
        ("Appliances & electronics", ("appliance", "charger", "television", "electronic", "refrigerator", "oven", "range", "air fryer")),
        ("Furniture & home", ("furniture", "chair", "table", "dresser", "bed", "mattress", "candle", "home")),
        ("Cosmetics & personal care", ("cosmetic", "lotion", "shampoo", "cream", "makeup", "personal care")),
        ("Pet products", ("pet", "dog", "cat", "animal")),
    ]
    for label, needles in groups:
        if any(needle in lower for needle in needles):
            return label
    return "Other consumer products"


def fda_records(kind: str, start: str, end: str) -> list[dict]:
    endpoint = f"https://api.fda.gov/{kind}/enforcement.json"
    records = []
    skip = 0
    while True:
        try:
            payload = fetch_json(endpoint, {
                "search": f"report_date:[{start.replace('-', '')} TO {end.replace('-', '')}]",
                "limit": "1000", "skip": str(skip),
            })
        except urllib.error.HTTPError as error:
            if error.code == 404:
                break
            raise
        page = payload.get("results", [])
        records.extend(page)
        if len(page) < 1000:
            break
        skip += len(page)
    return records


def is_pet_food(text: str) -> bool:
    """Require pet-food context instead of matching animal names by themselves."""
    return bool(re.search(
        r"\b(?:pet food|animal feed|veterinary diet|"
        r"(?:dog|cat|pet) (?:food|treats?|chews?|supplements?)|"
        r"(?:food|treats?|chews?|supplements?) for (?:dogs?|cats?|pets?))\b",
        text,
        re.I,
    ))


def normalize_fda(row: dict, kind: str) -> dict:
    product = clean(row.get("product_description"))
    reason = clean(row.get("reason_for_recall"))
    distribution = clean(row.get("distribution_pattern"))
    combined = " ".join((product, reason, distribution))
    pet = kind == "food" and is_pet_food(combined)
    section = "pet_food" if pet else "food" if kind == "food" else "products"
    category = "Medicines & medical devices" if kind in ("drug", "device") else "Pet food & animal products" if pet else "Human food"
    classification = clean(row.get("classification") or "Not yet classified")
    return {
        "id": f"fda-{kind}-{row.get('event_id') or row.get('recall_number')}",
        "section": section,
        "category": category,
        "title": product[:220] or f"{clean(row.get('recalling_firm'))} recall",
        "brand": clean(row.get("recalling_firm")),
        "description": reason,
        "reason": reason,
        "action": action_for(section, reason),
        "date": iso_date(row.get("report_date", "")),
        "status": clean(row.get("status") or "Ongoing"),
        "classification": classification,
        "severity": severity_from(classification, reason),
        "states": states_from(distribution),
        "distribution": distribution,
        "retailers": retailers_from(combined),
        "allergens": allergens_from(reason),
        "codes": clean(" ".join((row.get("code_info", ""), row.get("more_code_info", ""))))[:700],
        "source": f"FDA {kind.title()} Enforcement Report",
        "sourceUrl": "https://www.fda.gov/safety/recalls-market-withdrawals-safety-alerts/enforcement-reports",
        "products": [{"name": product, "codes": clean(" ".join((row.get("code_info", ""), row.get("more_code_info", ""))))[:700], "recallNumber": clean(row.get("recall_number"))}],
    }


def group_fda(raw_rows: list[dict], kind: str) -> list[dict]:
    grouped: dict[str, dict] = {}
    for row in raw_rows:
        item = normalize_fda(row, kind)
        if item["id"] not in grouped:
            grouped[item["id"]] = item
            continue
        current = grouped[item["id"]]
        current["products"].extend(item["products"])
        current["states"] = sorted(set(current["states"] + item["states"]))
        current["retailers"] = sorted(set(current["retailers"] + item["retailers"]))
        current["allergens"] = sorted(set(current["allergens"] + item["allergens"]))
        current["severity"] = max(current["severity"], item["severity"])
        current["date"] = max(current["date"], item["date"])
        if len(item["description"]) > len(current["description"]):
            current["description"] = item["description"]
            current["reason"] = item["reason"]
    for item in grouped.values():
        if len(item["products"]) > 1:
            item["title"] = f"{item['brand']}: {len(item['products'])} recalled products"
            item["codes"] = "See affected products"
    return list(grouped.values())


def normalize_cpsc(row: dict) -> dict:
    title = clean(row.get("Title"))
    description = clean(row.get("Description"))
    hazards = " ".join(clean(item.get("Name")) for item in row.get("Hazards", []))
    remedies = " ".join(clean(item.get("Name")) for item in row.get("Remedies", []))
    retailers = " ".join(clean(item.get("Name")) for item in row.get("Retailers", []))
    companies = row.get("Manufacturers", []) + row.get("Importers", []) + row.get("Distributors", [])
    brand = clean(companies[0].get("Name")) if companies else ""
    combined = " ".join((title, description, hazards, retailers))
    return {
        "id": f"cpsc-{row.get('RecallID') or row.get('RecallNumber')}",
        "section": "products",
        "category": product_category(combined),
        "title": title,
        "brand": brand,
        "description": description[:900],
        "reason": hazards,
        "action": action_for("products", hazards, remedies),
        "date": iso_date(row.get("RecallDate", "")),
        "status": "Active recall",
        "classification": "CPSC recall",
        "severity": severity_from("", hazards),
        "states": ["US"],
        "distribution": retailers,
        "retailers": retailers_from(retailers),
        "allergens": [],
        "codes": ", ".join(clean(item.get("UPC")) for item in row.get("ProductUPCs", []) if item.get("UPC")),
        "source": "U.S. Consumer Product Safety Commission",
        "sourceUrl": row.get("URL") or "https://www.cpsc.gov/Recalls",
        "products": [{"name": clean(item.get("Name")), "codes": clean(item.get("Model")), "recallNumber": clean(row.get("RecallNumber"))} for item in row.get("Products", [])],
    }


def normalize_fsis(row: dict) -> dict:
    lowered = {str(key).lower(): value for key, value in row.items()}
    title = clean(lowered.get("title") or lowered.get("recalltitle") or lowered.get("field_title"))
    reason = clean(lowered.get("reason") or lowered.get("recallreason") or lowered.get("field_recall_reason"))
    products = clean(lowered.get("products") or lowered.get("product") or lowered.get("field_recalled_products"))
    distribution = clean(lowered.get("states") or lowered.get("distribution") or lowered.get("field_states"))
    classification = clean(lowered.get("classification") or lowered.get("risklevel") or lowered.get("field_risk_level"))
    url = clean(lowered.get("url") or lowered.get("recallurl") or lowered.get("field_url"))
    date = lowered.get("date") or lowered.get("recalldate") or lowered.get("field_recall_date") or ""
    combined = " ".join((title, reason, products, distribution))
    return {
        "id": f"fsis-{clean(lowered.get('recallnumber') or lowered.get('id') or title)[:80]}",
        "section": "food", "category": "Human food", "title": title or products[:220],
        "brand": clean(lowered.get("company") or lowered.get("establishment") or ""),
        "description": products, "reason": reason, "action": action_for("food", reason),
        "date": iso_date(date), "status": clean(lowered.get("status") or "Active recall"),
        "classification": classification or "USDA-FSIS alert", "severity": severity_from(classification, reason),
        "states": states_from(distribution), "distribution": distribution,
        "retailers": retailers_from(combined), "allergens": allergens_from(reason), "codes": "",
        "source": "USDA Food Safety and Inspection Service",
        "sourceUrl": url if url.startswith("http") else "https://www.fsis.usda.gov/recalls",
        "products": [{"name": products, "codes": "", "recallNumber": clean(lowered.get("recallnumber"))}],
    }


def cdc_investigations() -> list[dict]:
    url = "https://www.cdc.gov/foodborne-outbreaks/media/files/2024/04/full-outbreak-list.csv"
    text = fetch(url).decode("utf-8-sig")
    rows = csv.DictReader(io.StringIO(text))
    current_year = str(datetime.now(timezone.utc).year)
    items = []
    for index, row in enumerate(rows):
        if row.get("Year") != current_year:
            continue
        raw_food = row.get("Contaminated Food", "")
        match = re.search(r'href="([^"]+)"[^>]*>(.*?)</a>', raw_food)
        link = match.group(1) if match else "/foodborne-outbreaks/outbreaks/"
        food = clean(match.group(2) if match else raw_food)
        germ = clean(row.get("Germ"))
        items.append({
            "id": f"cdc-{current_year}-{index}", "section": "food", "category": "Investigation",
            "title": f"{food} and {germ}", "brand": "", "description": "CDC multistate outbreak notice; a recall may or may not have been issued.",
            "reason": germ, "action": "Review CDC’s current notice for affected products, locations, symptoms, and recommended precautions.",
            "date": f"{current_year}-01-01", "status": "Investigation—not necessarily recalled", "classification": "CDC outbreak notice",
            "severity": 3, "states": ["US"], "distribution": "See the current CDC investigation.", "retailers": [],
            "allergens": allergens_from(food), "codes": "", "source": "Centers for Disease Control and Prevention",
            "sourceUrl": f"https://www.cdc.gov{link}" if link.startswith("/") else link,
            "products": [],
        })
    return items


def month_key(date_value: str) -> str:
    return date_value[:7] if len(date_value) >= 7 else "Unknown"


def main() -> int:
    now = datetime.now(timezone.utc)
    detail_start = (now - timedelta(days=90)).date().isoformat()
    history_start = (now - timedelta(days=730)).date().isoformat()
    end = now.date().isoformat()
    records: list[dict] = []
    history: list[dict] = []
    sources = []

    for kind in ("food", "drug", "device"):
        try:
            raw = fda_records(kind, history_start, end)
            normalized = group_fda(raw, kind)
            history.extend(normalized)
            records.extend(item for item in normalized if item["date"] >= detail_start)
            sources.append({"name": f"FDA {kind.title()}", "ok": True, "records": len(raw), "url": "https://open.fda.gov/apis/"})
        except Exception as error:
            sources.append({"name": f"FDA {kind.title()}", "ok": False, "records": 0, "note": str(error)[:180], "url": "https://open.fda.gov/apis/"})

    try:
        cpsc_raw = fetch_json("https://www.saferproducts.gov/RestWebServices/Recall", {
            "format": "json", "RecallDateStart": history_start, "RecallDateEnd": end,
        })
        cpsc = [normalize_cpsc(row) for row in cpsc_raw]
        history.extend(cpsc)
        records.extend(item for item in cpsc if item["date"] >= detail_start)
        sources.append({"name": "CPSC", "ok": True, "records": len(cpsc), "url": "https://www.cpsc.gov/Recalls"})
    except Exception as error:
        sources.append({"name": "CPSC", "ok": False, "records": 0, "note": str(error)[:180], "url": "https://www.cpsc.gov/Recalls"})

    try:
        fsis_raw = fetch_json("https://www.fsis.usda.gov/fsis/api/recall/v/1", {
            "format": "json", "RecallDateStart": history_start, "RecallDateEnd": end,
        })
        if isinstance(fsis_raw, dict):
            fsis_raw = fsis_raw.get("results") or fsis_raw.get("data") or []
        fsis = [normalize_fsis(row) for row in fsis_raw]
        history.extend(fsis)
        records.extend(item for item in fsis if item["date"] >= detail_start)
        sources.append({"name": "USDA-FSIS", "ok": True, "records": len(fsis), "url": "https://www.fsis.usda.gov/recalls"})
    except Exception as error:
        sources.append({"name": "USDA-FSIS", "ok": False, "records": 0, "note": "Official endpoint unavailable during this refresh; use the linked FSIS page.", "url": "https://www.fsis.usda.gov/recalls"})

    try:
        investigations = cdc_investigations()
        sources.append({"name": "CDC outbreaks", "ok": True, "records": len(investigations), "url": "https://www.cdc.gov/foodborne-outbreaks/outbreaks/"})
    except Exception as error:
        investigations = []
        sources.append({"name": "CDC outbreaks", "ok": False, "records": 0, "note": str(error)[:180], "url": "https://www.cdc.gov/foodborne-outbreaks/outbreaks/"})

    records.extend(investigations)
    unique = {item["id"]: item for item in records if item.get("title")}
    records = sorted(unique.values(), key=lambda item: (item["date"], item["severity"]), reverse=True)

    buckets = defaultdict(lambda: {"food": 0, "pet_food": 0, "products": 0})
    for item in history:
        key = month_key(item["date"])
        if key != "Unknown":
            buckets[key][item["section"]] += 1
    months = []
    cursor = (now.date().replace(day=1) - timedelta(days=700)).replace(day=1)
    while cursor <= now.date().replace(day=1):
        key = cursor.strftime("%Y-%m")
        months.append({"month": key, **buckets[key]})
        cursor = (cursor.replace(day=28) + timedelta(days=4)).replace(day=1)

    output = {
        "schemaVersion": 1,
        "generatedAt": now.isoformat().replace("+00:00", "Z"),
        "detailWindowDays": 90,
        "locations": {"primary": ["98074", "75033"], "radiusMiles": 25, "secondaryStates": ["UT", "CA"]},
        "sources": sources,
        "records": records,
        "trends": months,
    }
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(output, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps({"output": str(OUTPUT), "records": len(records), "sources": sources}, indent=2))
    return 0 if any(source["ok"] for source in sources) else 1


if __name__ == "__main__":
    sys.exit(main())
