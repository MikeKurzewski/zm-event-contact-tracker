from __future__ import annotations

import argparse
import csv
import json
import re
from collections import defaultdict
from pathlib import Path
from typing import Dict, Iterable, List, Tuple
from urllib.parse import urlparse


ROOT = Path(__file__).resolve().parents[1]
EVENTS_DIR = ROOT / "events"
DEFAULT_EVENT_SLUG = "hannover-messe"
DEFAULT_EVENT_NAME = "Hannover Messe"
ACCOUNTS_PATH = ROOT / "docs" / "existing-crm-companies" / "accounts.csv"
LEADS_PATH = ROOT / "docs" / "existing-crm-companies" / "leads.csv"
EVENT_DIR = EVENTS_DIR / DEFAULT_EVENT_SLUG
DATA_DIR = EVENT_DIR / "data"
OUTPUT_DIR = EVENT_DIR / "output"
EXHIBITORS_PATH = DATA_DIR / "hannover_exhibitors_enriched.csv"
OUTPUT_PATH = OUTPUT_DIR / "crm_hannovermesse_matches.csv"
ACCOUNTS_OUTPUT_PATH = OUTPUT_DIR / "crm_hannovermesse_accounts_matches.csv"
LEADS_OUTPUT_PATH = OUTPUT_DIR / "crm_hannovermesse_lead_matches.csv"

COMPANY_SUFFIXES = {
    "ab",
    "ag",
    "as",
    "a/s",
    "bv",
    "co",
    "co.",
    "company",
    "corp",
    "corporation",
    "gmbh",
    "holding",
    "holdings",
    "inc",
    "inc.",
    "kg",
    "kgaa",
    "limited",
    "llc",
    "ltd",
    "ltd.",
    "nv",
    "oy",
    "oyj",
    "plc",
    "pte",
    "sa",
    "s.a.",
    "sl",
    "s.l",
    "s.l.",
    "spa",
    "srl",
}

GENERIC_BRAND_TOKENS = {
    "automation",
    "digital",
    "group",
    "industrial",
    "industries",
    "industry",
    "international",
    "machine",
    "machinery",
    "manufacturing",
    "precision",
    "power",
    "process",
    "robotics",
    "service",
    "services",
    "smart",
    "solutions",
    "systems",
    "technology",
    "technologies",
    "tools",
}


def slugify_event(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", (value or "").strip().lower()).strip("-")
    if not slug:
        raise ValueError("Event slug cannot be empty.")
    return slug


def configure_event(event_slug: str, event_name: str) -> None:
    global EVENT_DIR
    global DATA_DIR
    global OUTPUT_DIR
    global EXHIBITORS_PATH
    global OUTPUT_PATH
    global ACCOUNTS_OUTPUT_PATH
    global LEADS_OUTPUT_PATH

    normalized_slug = slugify_event(event_slug)
    EVENT_DIR = EVENTS_DIR / normalized_slug
    DATA_DIR = EVENT_DIR / "data"
    OUTPUT_DIR = EVENT_DIR / "output"
    EXHIBITORS_PATH = DATA_DIR / "hannover_exhibitors_enriched.csv"
    OUTPUT_PATH = OUTPUT_DIR / "crm_hannovermesse_matches.csv"
    ACCOUNTS_OUTPUT_PATH = OUTPUT_DIR / "crm_hannovermesse_accounts_matches.csv"
    LEADS_OUTPUT_PATH = OUTPUT_DIR / "crm_hannovermesse_lead_matches.csv"

    EVENT_DIR.mkdir(parents=True, exist_ok=True)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    manifest_path = EVENT_DIR / "event.json"
    if not manifest_path.exists():
        manifest = {
            "name": event_name.strip() or normalized_slug.replace("-", " ").title(),
            "description": "CSV-driven scouting dashboard for booth-side outreach.",
        }
        manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Cross-reference CRM companies against an event export.")
    parser.add_argument(
        "--event-slug",
        default=DEFAULT_EVENT_SLUG,
        help="Folder slug under events/ for this event.",
    )
    parser.add_argument(
        "--event-name",
        default=DEFAULT_EVENT_NAME,
        help="Display name used if the event manifest does not exist yet.",
    )
    return parser.parse_args()


def normalize_name(value: str) -> str:
    value = (value or "").lower().replace("&", " and ")
    value = re.sub(r"[^a-z0-9]+", " ", value)
    tokens = [token for token in value.split() if token and token not in COMPANY_SUFFIXES]
    return " ".join(tokens)


def tokenize_name(value: str) -> List[str]:
    return [token for token in normalize_name(value).split() if len(token) >= 3]


def normalize_domain(value: str) -> str:
    if not value:
        return ""
    value = value.strip().lower()
    if "://" not in value:
        value = "https://" + value
    try:
        host = urlparse(value).netloc.lower()
    except Exception:
        return ""
    host = host.split("@")[-1].split(":")[0]
    if host.startswith("www."):
        host = host[4:]
    return host


def read_crm(source: str, path: Path) -> List[Dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        rows = []
        for row in csv.DictReader(handle):
            row = dict(row)
            row["crm_source"] = source
            row["crm_name_norm"] = normalize_name(row.get("Card Name", ""))
            row["crm_domain_norm"] = normalize_domain(row.get("Website", ""))
            row["crm_tokens"] = " ".join(tokenize_name(row.get("Card Name", "")))
            rows.append(row)
        return rows


def aggregate_exhibitors(path: Path) -> List[Dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))

    grouped: Dict[Tuple[str, str], Dict[str, str]] = {}
    for row in rows:
        name_norm = normalize_name(row.get("company_name", ""))
        domain_norm = normalize_domain(row.get("website", ""))
        key = (name_norm, domain_norm or row.get("company_name", "").lower())
        if key not in grouped:
            grouped[key] = dict(row)
            grouped[key]["name_norm"] = name_norm
            grouped[key]["domain_norm"] = domain_norm
            grouped[key]["booth_list"] = set([row.get("booth", "")]) if row.get("booth") else set()
        else:
            if row.get("booth"):
                grouped[key]["booth_list"].add(row["booth"])
            if not grouped[key].get("website") and row.get("website"):
                grouped[key]["website"] = row["website"]
                grouped[key]["domain_norm"] = domain_norm
            if len(row.get("profile_meta_description", "")) > len(grouped[key].get("profile_meta_description", "")):
                grouped[key]["profile_meta_description"] = row["profile_meta_description"]
            if len(row.get("profile_url", "")) > len(grouped[key].get("profile_url", "")):
                grouped[key]["profile_url"] = row["profile_url"]

    exhibitors = []
    for row in grouped.values():
        row["booths"] = " | ".join(sorted(b for b in row.pop("booth_list") if b))
        exhibitors.append(row)
    return exhibitors


def build_brand_index(exhibitors: List[Dict[str, str]]) -> Dict[str, List[Dict[str, str]]]:
    index: Dict[str, List[Dict[str, str]]] = defaultdict(list)
    for exhibitor in exhibitors:
        tokens = tokenize_name(exhibitor.get("company_name", ""))
        if tokens:
            index[tokens[0]].append(exhibitor)
    return index


def exact_matches(crm_row: Dict[str, str], exhibitors: List[Dict[str, str]]) -> List[Tuple[str, str, Dict[str, str]]]:
    matches: List[Tuple[str, str, Dict[str, str]]] = []
    crm_domain = crm_row["crm_domain_norm"]
    crm_name = crm_row["crm_name_norm"]

    for exhibitor in exhibitors:
        if crm_domain and crm_domain == exhibitor.get("domain_norm", ""):
            matches.append(("high", "exact_domain", exhibitor))
        elif crm_name and crm_name == exhibitor.get("name_norm", ""):
            matches.append(("high", "exact_name", exhibitor))
    return matches


def medium_matches(
    crm_row: Dict[str, str],
    exhibitors: List[Dict[str, str]],
    brand_index: Dict[str, List[Dict[str, str]]],
) -> List[Tuple[str, str, Dict[str, str]]]:
    crm_tokens = tokenize_name(crm_row.get("Card Name", ""))
    if not crm_tokens:
        return []

    first_token = crm_tokens[0]
    candidates = brand_index.get(first_token, [])
    if (
        not candidates
        or len(candidates) > 5
        or len(first_token) < 6
        or first_token in GENERIC_BRAND_TOKENS
    ):
        return []

    matches: List[Tuple[str, str, Dict[str, str]]] = []
    for exhibitor in candidates:
        exhibitor_name_norm = exhibitor.get("name_norm", "")
        exhibitor_tokens = tokenize_name(exhibitor.get("company_name", ""))
        if exhibitor_tokens and exhibitor_tokens[0] == first_token:
            matches.append(("medium", "brand_family_name_overlap", exhibitor))

    return matches


def dedupe_matches(matches: Iterable[Tuple[str, str, Dict[str, str]]]) -> List[Tuple[str, str, Dict[str, str]]]:
    seen = set()
    deduped = []
    for confidence, reason, exhibitor in matches:
        key = (exhibitor.get("company_name", ""), exhibitor.get("website", ""), confidence, reason)
        if key in seen:
            continue
        seen.add(key)
        deduped.append((confidence, reason, exhibitor))
    return deduped


def build_output_rows() -> List[Dict[str, str]]:
    crm_rows = read_crm("accounts", ACCOUNTS_PATH) + read_crm("leads", LEADS_PATH)
    exhibitors = aggregate_exhibitors(EXHIBITORS_PATH)
    brand_index = build_brand_index(exhibitors)

    output_rows: List[Dict[str, str]] = []
    for crm_row in crm_rows:
        matches = exact_matches(crm_row, exhibitors)
        if not matches:
            matches = medium_matches(crm_row, exhibitors, brand_index)
        for confidence, reason, exhibitor in dedupe_matches(matches):
            output_rows.append(
                {
                    "crm_source": crm_row.get("crm_source", ""),
                    "crm_company_name": crm_row.get("Card Name", ""),
                    "crm_card_url": crm_row.get("Card URL", ""),
                    "crm_list_name": crm_row.get("List Name", ""),
                    "crm_priority": crm_row.get("Priority", ""),
                    "crm_lead_source": crm_row.get("Lead Source", ""),
                    "crm_type": crm_row.get("Type", ""),
                    "crm_industry": crm_row.get("Industry", ""),
                    "crm_product": crm_row.get("Product", ""),
                    "crm_region": crm_row.get("Region", ""),
                    "crm_country": crm_row.get("Country", ""),
                    "crm_website": crm_row.get("Website", ""),
                    "crm_last_activity_date": crm_row.get("Last Activity Date", ""),
                    "hannover_company_name": exhibitor.get("company_name", ""),
                    "hannover_country": exhibitor.get("country", ""),
                    "hannover_website": exhibitor.get("website", ""),
                    "hannover_booths": exhibitor.get("booths", exhibitor.get("booth", "")),
                    "hannover_profile_url": exhibitor.get("profile_url", ""),
                    "hannover_score": exhibitor.get("score", ""),
                    "hannover_category": exhibitor.get("category", ""),
                    "hannover_subcategory": exhibitor.get("subcategory", ""),
                    "match_confidence": confidence,
                    "match_reason": reason,
                    "hannover_profile_meta_description": exhibitor.get("profile_meta_description", ""),
                }
            )

    output_rows.sort(
        key=lambda row: (
            {"high": 0, "medium": 1}.get(row["match_confidence"], 2),
            row["crm_source"],
            row["crm_company_name"].lower(),
        )
    )
    return output_rows


def write_output(path: Path, rows: List[Dict[str, str]], fieldnames: List[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        if rows:
            writer.writerows(rows)


def main() -> None:
    args = parse_args()
    configure_event(args.event_slug, args.event_name)
    if not EXHIBITORS_PATH.exists():
        raise FileNotFoundError(
            f"{EXHIBITORS_PATH} does not exist. Run build_target_lists.py for this event first."
        )

    rows = build_output_rows()
    if not rows:
        raise RuntimeError("No CRM-to-Hannover matches found.")

    fieldnames = list(rows[0].keys())
    write_output(OUTPUT_PATH, rows, fieldnames)
    write_output(ACCOUNTS_OUTPUT_PATH, [row for row in rows if row["crm_source"] == "accounts"], fieldnames)
    write_output(LEADS_OUTPUT_PATH, [row for row in rows if row["crm_source"] == "leads"], fieldnames)

    print(f"Wrote {OUTPUT_PATH} ({len(rows)} rows)")
    print(
        f"Wrote {ACCOUNTS_OUTPUT_PATH} "
        f"({sum(1 for row in rows if row['crm_source'] == 'accounts')} rows)"
    )
    print(
        f"Wrote {LEADS_OUTPUT_PATH} "
        f"({sum(1 for row in rows if row['crm_source'] == 'leads')} rows)"
    )


if __name__ == "__main__":
    main()
