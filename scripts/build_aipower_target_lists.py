from __future__ import annotations

import argparse
import csv
import json
import re
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Dict, Iterable, List, Tuple

import bs4
import requests

import build_target_lists as common


ROOT = Path(__file__).resolve().parents[1]
EVENTS_DIR = ROOT / "events"
DEFAULT_EVENT_SLUG = "ai-plus-power-2026"
DEFAULT_EVENT_NAME = "AI+ Power 2026"
LIST_URL = "https://www.aipluspower.com/exhibitor-list"
USER_AGENT = common.USER_AGENT

DATA_FILE_NAMES = {
    "raw_html": "aipower_exhibitor_list.html",
    "raw_csv": "aipower_exhibitors_raw.csv",
    "enriched": "hannover_exhibitors_enriched.csv",
    "website_cache": "website_profile_cache.json",
}

OUTPUT_FILE_NAMES = {
    "relevant": "zetamotion_relevant_companies.csv",
    "manufacturers": "zetamotion_manufacturer_targets.csv",
    "partners": "zetamotion_partner_targets.csv",
    "priority": "zetamotion_priority_meeting_targets.csv",
}

AIPOWER_POSITIVE_KEYWORDS = {
    "vision_inspection": {
        "keywords": [
            "computer vision",
            "machine vision",
            "image recognition",
            "image processing",
            "video analytics",
            "visual inspection",
            "defect detection",
            "quality inspection",
            "ocr",
            "camera",
            "imaging",
            "vision ai",
        ],
        "weight": 7,
        "cap": 35,
    },
    "industrial_ai": {
        "keywords": [
            "industrial ai",
            "manufacturing",
            "factory",
            "production",
            "quality control",
            "automation",
            "robotics",
            "iot",
            "edge ai",
            "digital twin",
            "logistics",
            "supply chain",
        ],
        "weight": 5,
        "cap": 30,
    },
    "enterprise_ai": {
        "keywords": [
            "ai solution",
            "ai solutions",
            "artificial intelligence",
            "machine learning",
            "generative ai",
            "large language model",
            "llm",
            "ai agent",
            "automation platform",
            "workflow automation",
            "analytics",
            "data intelligence",
        ],
        "weight": 4,
        "cap": 24,
    },
    "platform_infrastructure": {
        "keywords": [
            "ai infrastructure",
            "cloud",
            "data platform",
            "gpu",
            "cybersecurity",
            "blockchain",
            "api",
            "integration",
            "platform",
            "database",
        ],
        "weight": 2,
        "cap": 12,
    },
    "industry_end_user": {
        "keywords": [
            "manufacturer",
            "manufacturing",
            "food",
            "beverage",
            "caterer",
            "catering",
            "consumer goods",
            "camera",
            "printer",
            "electronics",
            "retail",
            "insurance",
        ],
        "weight": 3,
        "cap": 15,
    },
}

NEGATIVE_KEYWORDS = [
    "university",
    "education",
    "school",
    "journal",
    "media",
    "press",
    "venture",
    "investment",
    "award",
    "association",
    "government",
    "trade promotion",
    "caterers",
]

HARD_NEGATIVE_KEYWORDS = {
    "university",
    "education",
    "school",
    "journal",
    "media",
    "press",
    "venture",
    "investment",
    "association",
    "government",
    "trade promotion",
}


def slugify_event(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", (value or "").strip().lower()).strip("-")
    if not slug:
        raise ValueError("Event slug cannot be empty.")
    return slug


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build AI+ Power event-scoped scouting CSVs.")
    parser.add_argument("--event-slug", default=DEFAULT_EVENT_SLUG)
    parser.add_argument("--event-name", default=DEFAULT_EVENT_NAME)
    parser.add_argument("--list-url", default=LIST_URL)
    parser.add_argument(
        "--skip-website-enrichment",
        action="store_true",
        help="Only use the official exhibitor-list records; do not fetch exhibitor websites.",
    )
    return parser.parse_args()


def configure_event(event_slug: str, event_name: str) -> Dict[str, Path]:
    event_dir = EVENTS_DIR / slugify_event(event_slug)
    data_dir = event_dir / "data"
    output_dir = event_dir / "output"
    data_dir.mkdir(parents=True, exist_ok=True)
    output_dir.mkdir(parents=True, exist_ok=True)

    manifest_path = event_dir / "event.json"
    manifest = {
        "name": event_name.strip() or event_dir.name.replace("-", " ").title(),
        "description": "CSV-driven scouting dashboard for booth-side outreach at AI+ Power 2026 in Hong Kong.",
    }
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    return {
        "event": event_dir,
        "data": data_dir,
        "output": output_dir,
        "raw_html": data_dir / DATA_FILE_NAMES["raw_html"],
        "raw_csv": data_dir / DATA_FILE_NAMES["raw_csv"],
        "enriched": data_dir / DATA_FILE_NAMES["enriched"],
        "website_cache": data_dir / DATA_FILE_NAMES["website_cache"],
    }


def make_session() -> requests.Session:
    session = requests.Session()
    session.headers.update({"User-Agent": USER_AGENT})
    return session


def normalize_list(value: object) -> List[str]:
    if isinstance(value, list):
        return [common.normalize_space(str(item)) for item in value if common.normalize_space(str(item))]
    if isinstance(value, str):
        return [common.normalize_space(value)] if common.normalize_space(value) else []
    return []


def extract_exhibitor_records(html_text: str) -> List[Dict[str, object]]:
    soup = bs4.BeautifulSoup(html_text, "html.parser")
    script = soup.find("script", id="wix-warmup-data", type="application/json")
    if not script or not script.string:
        raise ValueError("Could not find Wix warmup data on the exhibitor-list page.")

    data = json.loads(script.string)
    records = (
        data.get("appsWarmupData", {})
        .get("dataBinding", {})
        .get("dataStore", {})
        .get("recordsByCollectionId", {})
        .get("2026ExhibitorList", {})
    )
    if not records:
        raise ValueError("Could not find 2026ExhibitorList records in Wix warmup data.")

    return sorted(records.values(), key=lambda row: int(row.get("refNo") or 99999))


def build_official_overview(row: Dict[str, str]) -> str:
    parts = [
        "AI+ Power 2026 exhibitor.",
        f"Ref {row['ref_no']}." if row.get("ref_no") else "",
        f"Booth {row['booth_ref']}." if row.get("booth_ref") else "",
        f"Main scope: {row['main_scope_of_business']}." if row.get("main_scope_of_business") else "",
        f"Chinese name: {row['company_name_cn']}." if row.get("company_name_cn") else "",
    ]
    return " ".join(part for part in parts if part)


def normalize_rows(records: List[Dict[str, object]], list_url: str) -> List[Dict[str, str]]:
    rows: List[Dict[str, str]] = []
    for record in records:
        company_name = common.normalize_space(str(record.get("companyNameEn") or record.get("logo") or ""))
        booth_ref = common.normalize_space(str(record.get("boothNo") or ""))
        scopes = normalize_list(record.get("mainScopeOfBusiness"))
        row = {
            "hit_type": "Exhibitor",
            "company_name": company_name,
            "company_name_cn": common.normalize_space(str(record.get("companyNameCn") or "")),
            "country": "",
            "zip_code": "",
            "city": "",
            "federal_state": "",
            "website": common.normalize_website(str(record.get("website") or "")),
            "booth": f"Stand {booth_ref}" if booth_ref else "",
            "booth_ref": booth_ref,
            "profile_url": list_url,
            "ref_no": str(record.get("refNo") or ""),
            "main_scope_of_business": ", ".join(scopes),
            "official_image": str(record.get("image") or ""),
            "profile_title": company_name,
            "profile_meta_description": "",
            "profile_headings": "",
        }
        row["profile_meta_description"] = build_official_overview(row)
        rows.append(row)
    return rows


def load_json_cache(path: Path) -> Dict[str, Dict[str, str]]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def save_json_cache(path: Path, cache: Dict[str, Dict[str, str]]) -> None:
    path.write_text(json.dumps(cache, ensure_ascii=False, indent=2), encoding="utf-8")


def should_fetch_website(row: Dict[str, str]) -> bool:
    return bool(common.normalize_website(row.get("website", "")))


def enrich_company_websites(rows: List[Dict[str, str]], cache_path: Path, max_workers: int = 8) -> List[Dict[str, str]]:
    cache = load_json_cache(cache_path)
    urls = sorted(
        {
            common.normalize_website(row.get("website", ""))
            for row in rows
            if should_fetch_website(row)
        }
    )
    missing_urls = [url for url in urls if url and url not in cache]

    if missing_urls:
        print(f"Fetching {len(missing_urls)} company websites for AI+ Power context...")
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_map = {executor.submit(common.fetch_company_website, url): url for url in missing_urls}
            for future in as_completed(future_map):
                url = future_map[future]
                try:
                    cache[url] = future.result()
                except Exception as exc:
                    failed = dict(common.WEBSITE_EMPTY)
                    failed["website_home_url"] = url
                    failed["website_fetch_error"] = str(exc)
                    cache[url] = failed
        save_json_cache(cache_path, cache)

    enriched = []
    for row in rows:
        merged = dict(row)
        merged.update(common.WEBSITE_EMPTY)
        merged.update(cache.get(common.normalize_website(row.get("website", "")), {}))
        enriched.append(merged)
    return enriched


def keyword_hits(text: str, keywords: Iterable[str]) -> List[str]:
    return common.keyword_hits(text, keywords)


def derive_category(hit_map: Dict[str, List[str]], text: str, scopes: str) -> Tuple[str, str]:
    if hit_map["vision_inspection"]:
        return "partner_target", "ai_vision_or_inspection_partner"
    if hit_map["industrial_ai"]:
        return "partner_target", "industrial_ai_or_automation_partner"
    if "AI Solutions" in scopes or "AI+ Applications" in scopes:
        return "partner_target", "ai_solution_partner"
    if hit_map["platform_infrastructure"]:
        return "partner_target", "ai_platform_or_infrastructure"
    if hit_map["industry_end_user"]:
        return "manufacturer_target", "industry_end_user_ai_adopter"
    return "review_target", "general_ai_event_fit"


def build_outreach_angle(category: str, subcategory: str) -> str:
    if subcategory == "ai_vision_or_inspection_partner":
        return "Explore partnership around synthetic data, computer vision, QA automation, or visual inspection workflows."
    if subcategory == "industrial_ai_or_automation_partner":
        return "Explore integration around industrial AI, automation, factory data, or inspection-adjacent workflows."
    if subcategory == "ai_solution_partner":
        return "Qualify whether their AI solution work overlaps with visual QA, inspection, data generation, or enterprise AI deployment."
    if subcategory == "ai_platform_or_infrastructure":
        return "Explore infrastructure or platform partnership for AI model deployment, data pipelines, or customer introductions."
    if subcategory == "industry_end_user_ai_adopter":
        return "Qualify whether their operations include repeatable product, packaging, or component inspection needs."
    return "Manual review recommended before outreach."


def score_row(row: Dict[str, str]) -> Dict[str, str]:
    text = common.normalize_space(
        " ".join(
            [
                row.get("company_name", ""),
                row.get("company_name_cn", ""),
                row.get("main_scope_of_business", ""),
                row.get("profile_meta_description", ""),
                row.get("website_home_title", ""),
                row.get("website_home_meta_description", ""),
                row.get("website_home_headings", ""),
                row.get("website_about_title", ""),
                row.get("website_about_meta_description", ""),
                row.get("website_about_headings", ""),
            ]
        )
    )

    hit_map: Dict[str, List[str]] = {}
    score = 0
    matched_keywords: List[str] = []
    for bucket, spec in AIPOWER_POSITIVE_KEYWORDS.items():
        hits = keyword_hits(text, spec["keywords"])
        hit_map[bucket] = hits
        score += min(len(hits) * spec["weight"], spec["cap"])
        matched_keywords.extend(hits)

    scopes = row.get("main_scope_of_business", "")
    if "AI Solutions" in scopes:
        score += 8
    if "AI+ Applications" in scopes:
        score += 6
    if "AI Infrastructure" in scopes:
        score += 4
    if "Cybersecurity" in scopes:
        score += 2
    if "Blockchain" in scopes:
        score += 1

    negative_hits = keyword_hits(text, NEGATIVE_KEYWORDS)
    score -= min(len(negative_hits) * 5, 20)

    category, subcategory = derive_category(hit_map, text, scopes)
    if category == "partner_target":
        score += 4
    elif category == "manufacturer_target":
        score += 2

    hard_negative = bool(set(negative_hits) & HARD_NEGATIVE_KEYWORDS)
    if hard_negative and score < 26:
        category = "excluded"
        subcategory = "institution_media_or_low_fit"
        score = min(score, 10)
    elif negative_hits and score < 18:
        category = "excluded"
        subcategory = "negative_signal"

    priority = ""
    for band, threshold in common.PRIORITY_THRESHOLDS.items():
        if score >= threshold:
            priority = band
            break
    if not priority and score >= common.PRIORITY_THRESHOLDS["C"]:
        priority = "C"

    row["score"] = str(score)
    row["priority_band"] = priority
    row["category"] = category
    row["subcategory"] = subcategory
    row["matched_keywords"] = ", ".join(sorted(dict.fromkeys(matched_keywords)))
    row["negative_keywords"] = ", ".join(sorted(dict.fromkeys(negative_hits)))
    row["country_priority_bucket"] = ""
    row["country_priority_boost"] = "0"
    row["outreach_angle"] = (
        "Excluded from outreach because the exhibitor appears to be an institution, media, investor, or otherwise low-fit entry."
        if category == "excluded"
        else build_outreach_angle(category, subcategory)
    )
    return row


def write_csv(path: Path, rows: List[Dict[str, str]]) -> None:
    if not rows:
        return
    fields: List[str] = []
    seen = set()
    for row in rows:
        for key in row.keys():
            if key not in seen:
                seen.add(key)
                fields.append(key)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def sort_rows(rows: List[Dict[str, str]]) -> List[Dict[str, str]]:
    return sorted(
        rows,
        key=lambda row: (
            {"A": 0, "B": 1, "C": 2, "": 3}.get(row.get("priority_band", ""), 4),
            -int(row.get("score", "0")),
            row.get("company_name", ""),
        ),
    )


def main() -> None:
    args = parse_args()
    paths = configure_event(args.event_slug, args.event_name)
    session = make_session()

    print("Downloading AI+ Power exhibitor list...")
    response = session.get(args.list_url, timeout=60)
    response.raise_for_status()
    html_text = response.content.decode("utf-8", errors="replace")
    paths["raw_html"].write_text(html_text, encoding="utf-8")

    records = extract_exhibitor_records(html_text)
    rows = normalize_rows(records, args.list_url)
    write_csv(paths["raw_csv"], rows)
    print(f"Parsed {len(rows)} exhibitors from Wix warmup data.")

    if args.skip_website_enrichment:
        rows = [dict(row, **common.WEBSITE_EMPTY) for row in rows]
    else:
        rows = enrich_company_websites(rows, paths["website_cache"])

    scored_rows = sort_rows([score_row(row) for row in rows])
    write_csv(paths["enriched"], scored_rows)

    relevant_rows = [
        row
        for row in scored_rows
        if row.get("category") in {"manufacturer_target", "partner_target", "review_target"}
        and int(row.get("score", "0")) >= common.PRIORITY_THRESHOLDS["C"]
    ]
    manufacturer_rows = [
        row
        for row in relevant_rows
        if row.get("category") == "manufacturer_target" and int(row.get("score", "0")) >= 20
    ]
    partner_rows = [
        row
        for row in relevant_rows
        if row.get("category") == "partner_target" and int(row.get("score", "0")) >= 18
    ]

    write_csv(paths["output"] / OUTPUT_FILE_NAMES["relevant"], relevant_rows)
    write_csv(paths["output"] / OUTPUT_FILE_NAMES["manufacturers"], manufacturer_rows)
    write_csv(paths["output"] / OUTPUT_FILE_NAMES["partners"], partner_rows)
    write_csv(paths["output"] / OUTPUT_FILE_NAMES["priority"], relevant_rows[:30])

    # Keep timestamps distinct for the dashboard's "updated" badge on fast runs.
    time.sleep(0.05)

    print(f"Wrote {paths['enriched']}")
    print(f"Wrote {paths['output'] / OUTPUT_FILE_NAMES['relevant']} ({len(relevant_rows)} rows)")
    print(f"Wrote {paths['output'] / OUTPUT_FILE_NAMES['manufacturers']} ({len(manufacturer_rows)} rows)")
    print(f"Wrote {paths['output'] / OUTPUT_FILE_NAMES['partners']} ({len(partner_rows)} rows)")
    print(f"Wrote {paths['output'] / OUTPUT_FILE_NAMES['priority']} ({min(len(relevant_rows), 30)} rows)")


if __name__ == "__main__":
    main()
