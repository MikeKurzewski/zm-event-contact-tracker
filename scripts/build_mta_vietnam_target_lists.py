from __future__ import annotations

import argparse
import csv
import json
import re
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Dict, Iterable, List, Tuple
from urllib.parse import quote

import bs4
import requests

import build_target_lists as common


ROOT = Path(__file__).resolve().parents[1]
EVENTS_DIR = ROOT / "events"
DEFAULT_EVENT_SLUG = "mta-vietnam-2026"
DEFAULT_EVENT_NAME = "MTA Vietnam 2026"
LIST_URL = "https://exhibitors.informamarkets-info.com/event/MTV26/en-US"
API_URL = "https://exhibitors.informamarkets-info.com/api"
USER_AGENT = common.USER_AGENT

DATA_FILE_NAMES = {
    "raw_json": "mta_vietnam_exhibitors_raw.json",
    "raw_csv": "mta_vietnam_exhibitors_raw.csv",
    "enriched": "hannover_exhibitors_enriched.csv",
    "website_cache": "website_profile_cache.json",
}

OUTPUT_FILE_NAMES = {
    "relevant": "zetamotion_relevant_companies.csv",
    "manufacturers": "zetamotion_manufacturer_targets.csv",
    "partners": "zetamotion_partner_targets.csv",
    "priority": "zetamotion_priority_meeting_targets.csv",
}

API_PARAMS = {
    "fn": "getExhibitor",
    "orderfields": '["FeaturedExhibitor","ExhibitorNameEn","StandNoStr","CountryEn"]',
    "filter[country]": "",
    "filter[companyprefix]": "",
    "filter[productcategory]": "",
    "filter[hashtags]": "",
    "filter[businessnature]": "",
    "filter[exhibitortype]": "",
    "filter[venue]": "",
    "filter[fairlocation]": "",
    "HideEmptyProducts": "0",
    "filter[new]": "",
    "filter[sustainable]": "",
    "filter[besustainable]": "",
    "order[0][column]": "0",
    "order[0][dir]": "desc",
    "order[1][column]": "1",
    "order[1][dir]": "asc",
    "start": "0",
    "length": "10000",
    "draw": "1",
    "dt": "1",
    "SearchLog": "1",
    "FairID": "qPprQcI0aXdA2T+aXW9C2A==",
    "FairCode": "G8xYPijumKY6yba9/s0ZQA==",
    "UseOldCountry": "True",
    "MyList": "0",
    "Email": "",
    "Url": LIST_URL,
}

MTA_POSITIVE_KEYWORDS = {
    "inspection_metrology": {
        "keywords": [
            "inspection",
            "quality control",
            "quality assurance",
            "testing",
            "calibration",
            "metrology",
            "measurement",
            "measuring",
            "coordinate measuring",
            "cmm",
            "gauge",
            "gauges",
            "scanner",
            "3d scanner",
            "sensor",
            "camera",
            "machine vision",
            "vision",
            "traceability",
        ],
        "weight": 6,
        "cap": 36,
    },
    "automation_robotics": {
        "keywords": [
            "automation",
            "robot",
            "robotics",
            "system integration",
            "system integrator",
            "turnkey",
            "smart factory",
            "industrial iot",
            "iot",
            "plc",
            "mes",
            "factory management",
            "agv",
            "amr",
            "conveyor",
            "production line",
        ],
        "weight": 5,
        "cap": 30,
    },
    "metalworking_machinery": {
        "keywords": [
            "cnc",
            "machining",
            "machining centre",
            "machining center",
            "lathe",
            "lathes",
            "milling",
            "grinding",
            "edm",
            "wire-cut",
            "laser cutting",
            "laser",
            "sheet metal",
            "bending",
            "punching",
            "stamping",
            "presses",
            "shears",
            "welding",
            "cutting tools",
            "tooling",
            "jigs",
            "fixtures",
            "mould",
            "mold",
            "die",
        ],
        "weight": 4,
        "cap": 28,
    },
    "parts_components": {
        "keywords": [
            "precision mechanical parts",
            "mechanical parts",
            "industrial components",
            "electronics",
            "industrial supporting components",
            "fasteners",
            "hardware",
            "casting",
            "forging",
            "fabrication",
            "fabricated",
            "components",
            "parts",
            "mould and die",
            "mold and die",
        ],
        "weight": 5,
        "cap": 28,
    },
    "ai_digital": {
        "keywords": [
            "ai",
            "ai-based",
            "ai-driven",
            "artificial intelligence",
            "machine learning",
            "software",
            "cad",
            "cam",
            "cae",
            "rapid prototyping",
            "predictive maintenance",
            "digital",
            "data management",
        ],
        "weight": 4,
        "cap": 24,
    },
    "target_industries": {
        "keywords": [
            "automotive",
            "aerospace",
            "medical",
            "electronics",
            "precision machinery",
            "industrial equipment",
            "railway",
            "construction machinery",
            "packaging",
            "semiconductor",
        ],
        "weight": 3,
        "cap": 18,
    },
}

MANUFACTURING_HINTS = [
    "manufacturer",
    "manufacture",
    "manufactures",
    "manufacturing",
    "production",
    "producer",
    "factory",
    "plant",
    "fabrication",
    "fabricator",
    "machining",
    "casting",
    "forging",
    "assembly",
    "processing",
]

NEGATIVE_KEYWORDS = [
    "training",
    "consulting",
    "certification services",
    "association",
    "university",
    "institute",
    "media",
    "publisher",
    "press",
    "trade promotion",
    "government",
    "distribution & logistics services",
    "business community",
    "industrial park",
    "trade organization",
    "marketplace",
    "directory",
]

INSTITUTION_EXCLUSION_KEYWORDS = [
    "jetro",
    "business community",
    "industrial park",
    "association",
    "chamber of commerce",
    "trade promotion",
    "marketplace",
    "directory",
]

PARTS_COMPONENT_CATEGORY_HINTS = [
    "precision mechanical parts",
    "casting, forging",
    "fabrication part",
    "electronics & industrial components",
    "industrial supporting components",
    "fasteners",
    "hardware",
]

EXCLUDED_COUNTRY_TERMS = {
    "china",
    "hong kong",
    "hong kong sar",
    "hong kong, china",
    "macau",
    "macao",
}

OTHER_OVERSEAS_PRIORITY = {
    "japan",
    "taiwan",
    "south korea",
    "korea",
    "singapore",
    "thailand",
    "malaysia",
    "indonesia",
    "india",
    "germany",
    "italy",
    "switzerland",
    "united states",
    "united states of america",
    "usa",
}


def slugify_event(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", (value or "").strip().lower()).strip("-")
    if not slug:
        raise ValueError("Event slug cannot be empty.")
    return slug


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build MTA Vietnam event-scoped scouting CSVs.")
    parser.add_argument("--event-slug", default=DEFAULT_EVENT_SLUG)
    parser.add_argument("--event-name", default=DEFAULT_EVENT_NAME)
    parser.add_argument("--list-url", default=LIST_URL)
    parser.add_argument("--api-url", default=API_URL)
    parser.add_argument(
        "--skip-website-enrichment",
        action="store_true",
        help="Only use the official exhibitor records; do not fetch exhibitor websites.",
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
        "description": "CSV-driven scouting dashboard for booth-side outreach at MTA Vietnam 2026.",
    }
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    return {
        "event": event_dir,
        "data": data_dir,
        "output": output_dir,
        "raw_json": data_dir / DATA_FILE_NAMES["raw_json"],
        "raw_csv": data_dir / DATA_FILE_NAMES["raw_csv"],
        "enriched": data_dir / DATA_FILE_NAMES["enriched"],
        "website_cache": data_dir / DATA_FILE_NAMES["website_cache"],
    }


def make_session() -> requests.Session:
    session = requests.Session()
    session.headers.update(
        {
            "User-Agent": USER_AGENT,
            "Accept": "application/json, text/javascript, */*; q=0.01",
            "Referer": LIST_URL,
            "X-Requested-With": "XMLHttpRequest",
        }
    )
    return session


def strip_html(value: str) -> str:
    soup = bs4.BeautifulSoup(value or "", "html.parser")
    return common.normalize_space(soup.get_text(" ", strip=True))


def normalize_country(value: str) -> str:
    return common.normalize_space(value).lower()


def is_china_or_chinese_company(row: Dict[str, str]) -> bool:
    country_values = [
        row.get("CountryEn", ""),
        row.get("Country", ""),
        row.get("CountryChs", ""),
        row.get("CountryCht", ""),
    ]
    normalized_countries = [normalize_country(value) for value in country_values if value]
    if any(country in EXCLUDED_COUNTRY_TERMS or "china" in country for country in normalized_countries):
        return True
    if any(value in {"中国", "中國"} for value in country_values):
        return True

    address = normalize_country(row.get("Field01", ""))
    return bool(re.search(r"\b(p\.?r\.?\s*china|people'?s republic of china)\b", address))


def country_priority(country: str) -> Tuple[str, int]:
    normalized = normalize_country(country)
    if normalized == "vietnam":
        return "priority_vietnam", 18
    if normalized in OTHER_OVERSEAS_PRIORITY:
        return "priority_overseas", 6
    if normalized:
        return "priority_other_non_china", 3
    return "", 0


def profile_url(row: Dict[str, str], list_url: str) -> str:
    exhibitor_id = row.get("ExhibitorID", "")
    company = row.get("ExhibitorNameEn", "") or row.get("ExhibitorNameCht", "")
    slug = re.sub(r"[\s,.&/+%*]+", "-", company.lower()).strip("-")
    return f"{list_url.rstrip('/')}/exhibitor/{exhibitor_id}/{quote(slug)}" if exhibitor_id else list_url


def booth_label(value: str) -> str:
    entries = []
    for part in (value or "").split("|"):
        bits = [common.normalize_space(bit) for bit in part.split("~")]
        bits = [bit for bit in bits if bit]
        if len(bits) >= 3:
            entries.append(f"{bits[0]} Hall {bits[1]} Stand {bits[2]}")
        elif bits:
            entries.append(" ".join(bits))
    return " | ".join(entries)


def official_overview(row: Dict[str, str]) -> str:
    parts = [
        "MTA Vietnam 2026 exhibitor.",
        f"Country: {row.get('country')}." if row.get("country") else "",
        f"Booth: {row.get('booth')}." if row.get("booth") else "",
        f"Categories: {row.get('product_categories')}." if row.get("product_categories") else "",
        row.get("description", ""),
        f"Address: {row.get('address')}." if row.get("address") else "",
        f"Pavilion: {row.get('pavilion')}." if row.get("pavilion") else "",
        f"Agents/company reps: {row.get('agents_company')}." if row.get("agents_company") else "",
        f"Agent countries: {row.get('agents_country')}." if row.get("agents_country") else "",
    ]
    return common.normalize_space(" ".join(part for part in parts if part))


def download_records(session: requests.Session, api_url: str, list_url: str) -> List[Dict[str, str]]:
    params = dict(API_PARAMS)
    params["Url"] = list_url
    response = session.get(api_url, params=params, timeout=60)
    response.raise_for_status()
    payload = response.json()
    if not payload.get("status"):
        raise ValueError(f"Informa API returned unsuccessful status: {payload!r}")
    records = payload.get("data") or []
    if not isinstance(records, list):
        raise ValueError("Informa API did not return a list under data.")
    return records


def normalize_rows(records: List[Dict[str, str]], list_url: str) -> List[Dict[str, str]]:
    rows = []
    for record in records:
        row = {
            "hit_type": "Exhibitor",
            "company_name": common.normalize_space(record.get("ExhibitorNameEn") or record.get("ExhibitorNameCht") or ""),
            "country": common.normalize_space(record.get("CountryEn") or record.get("Country") or ""),
            "zip_code": "",
            "city": "",
            "federal_state": "",
            "website": common.normalize_website(record.get("LinkEn") or record.get("LinkCht") or ""),
            "booth": booth_label(record.get("StandNoStr", "")) or common.normalize_space(record.get("StandNo", "")),
            "profile_url": profile_url(record, list_url),
            "exhibitor_id": record.get("ExhibitorID", ""),
            "product_categories": common.normalize_space(record.get("ProductCategoryEn", "")),
            "product_category_ids": common.normalize_space(record.get("ProductCategory", "")),
            "description": strip_html(record.get("DescEn") or record.get("DescCht") or record.get("DescChs") or ""),
            "address": common.normalize_space(record.get("Field01", "")),
            "pavilion": common.normalize_space(record.get("Field02", "")),
            "hashtags": common.normalize_space(record.get("Field03", "")),
            "principals_company": common.normalize_space(record.get("Field04", "")),
            "agents_company": common.normalize_space(record.get("Field05", "")),
            "principals_country": common.normalize_space(record.get("Field06", "")),
            "agents_country": common.normalize_space(record.get("Field07", "")),
            "sales_office": common.normalize_space(record.get("Field08", "")),
            "brochure": common.normalize_space(record.get("Field10", "")),
            "photo_url": common.normalize_space(record.get("PhotoURL", "")),
            "linkedin_url": common.normalize_space(record.get("LinkedinURL", "")),
            "facebook_url": common.normalize_space(record.get("FacebookURL", "")),
            "profile_title": common.normalize_space(record.get("ExhibitorNameEn") or ""),
            "profile_headings": "",
        }
        row["profile_meta_description"] = official_overview(row)
        if is_china_or_chinese_company(record):
            row["excluded_source_reason"] = "china_or_chinese_company"
        else:
            row["excluded_source_reason"] = ""
        rows.append(row)
    return rows


def load_json_cache(path: Path) -> Dict[str, Dict[str, str]]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def save_json_cache(path: Path, cache: Dict[str, Dict[str, str]]) -> None:
    path.write_text(json.dumps(cache, ensure_ascii=False, indent=2), encoding="utf-8")


def preliminary_fetch_candidate(row: Dict[str, str]) -> bool:
    if not common.normalize_website(row.get("website", "")):
        return False
    scored = score_row(dict(row), include_company_website=False)
    if scored.get("category") == "excluded":
        return False
    return bool(scored.get("matched_keywords")) or int(scored.get("score", "0")) >= 14


def enrich_company_websites(rows: List[Dict[str, str]], cache_path: Path, max_workers: int = 8) -> List[Dict[str, str]]:
    cache = load_json_cache(cache_path)
    candidate_urls = sorted(
        {
            common.normalize_website(row.get("website", ""))
            for row in rows
            if preliminary_fetch_candidate(row)
        }
    )
    missing_urls = [url for url in candidate_urls if url and url not in cache]

    if missing_urls:
        print(f"Fetching {len(missing_urls)} company websites for MTA Vietnam context...")
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


def has_parts_component_category(row: Dict[str, str]) -> bool:
    categories = row.get("product_categories", "").lower()
    return any(hint in categories for hint in PARTS_COMPONENT_CATEGORY_HINTS)


def derive_category(row: Dict[str, str], hit_map: Dict[str, List[str]], manufacturing_hits: List[str]) -> Tuple[str, str]:
    if hit_map["parts_components"] and manufacturing_hits and has_parts_component_category(row):
        return "manufacturer_target", "precision_parts_or_component_manufacturer"
    if hit_map["inspection_metrology"]:
        return "partner_target", "inspection_metrology_or_qa_partner"
    if hit_map["ai_digital"] and (hit_map["automation_robotics"] or hit_map["inspection_metrology"]):
        return "partner_target", "ai_or_smart_factory_partner"
    if hit_map["automation_robotics"]:
        return "partner_target", "automation_robotics_or_system_integrator"
    if hit_map["metalworking_machinery"]:
        return "partner_target", "machine_tool_tooling_or_process_equipment"
    if hit_map["parts_components"]:
        return "review_target", "parts_components_manual_review"
    return "review_target", "general_mta_industrial_fit"


def build_outreach_angle(category: str, subcategory: str) -> str:
    if subcategory == "precision_parts_or_component_manufacturer":
        return "Qualify direct inspection needs for precision parts, fabricated components, casting, forging, machining, or assembly QA."
    if subcategory == "inspection_metrology_or_qa_partner":
        return "Explore partnership around inspection hardware, metrology workflows, QA stations, computer vision, or traceability."
    if subcategory == "ai_or_smart_factory_partner":
        return "Explore collaboration around AI, smart factory data, production traceability, or automated inspection workflows."
    if subcategory == "automation_robotics_or_system_integrator":
        return "Explore OEM or integration partnership for automated inspection cells and factory QA systems."
    if subcategory == "machine_tool_tooling_or_process_equipment":
        return "Qualify whether their machine-tool, tooling, or process-equipment customers need integrated inspection or defect detection."
    if subcategory == "parts_components_manual_review":
        return "Manual review recommended because parts/component signals are present but the company is not clearly a manufacturer."
    return "Manual review recommended before outreach."


def score_row(row: Dict[str, str], include_company_website: bool = True) -> Dict[str, str]:
    text_parts = [
        row.get("company_name", ""),
        row.get("country", ""),
        row.get("product_categories", ""),
        row.get("description", ""),
        row.get("address", ""),
        row.get("pavilion", ""),
        row.get("principals_company", ""),
        row.get("agents_company", ""),
        row.get("principals_country", ""),
        row.get("agents_country", ""),
        row.get("profile_meta_description", ""),
    ]
    if include_company_website:
        text_parts.extend(
            [
                row.get("website_home_title", ""),
                row.get("website_home_meta_description", ""),
                row.get("website_home_headings", ""),
                row.get("website_about_title", ""),
                row.get("website_about_meta_description", ""),
                row.get("website_about_headings", ""),
            ]
        )
    full_text = common.normalize_space(" ".join(text_parts))

    hit_map: Dict[str, List[str]] = {}
    score = 0
    matched_keywords: List[str] = []
    for bucket, spec in MTA_POSITIVE_KEYWORDS.items():
        hits = keyword_hits(full_text, spec["keywords"])
        hit_map[bucket] = hits
        score += min(len(hits) * spec["weight"], spec["cap"])
        matched_keywords.extend(hits)

    manufacturing_hits = keyword_hits(full_text, MANUFACTURING_HINTS)
    if manufacturing_hits:
        score += 5

    negative_hits = keyword_hits(full_text, NEGATIVE_KEYWORDS)
    score -= min(len(negative_hits) * 4, 16)
    institution_hits = keyword_hits(
        common.normalize_space(" ".join([row.get("company_name", ""), row.get("description", ""), row.get("pavilion", "")])),
        INSTITUTION_EXCLUSION_KEYWORDS,
    )

    country_priority_bucket, country_boost = country_priority(row.get("country", ""))
    score += country_boost

    if row.get("agents_country", "").lower().find("vietnam") >= 0:
        score += 4
        if not country_priority_bucket:
            country_priority_bucket = "priority_vietnam_agent"

    category, subcategory = derive_category(row, hit_map, manufacturing_hits)

    if row.get("excluded_source_reason") == "china_or_chinese_company":
        row["score"] = str(score - 999)
        row["priority_band"] = ""
        row["category"] = "excluded"
        row["subcategory"] = "excluded_china_or_chinese_company"
        row["matched_keywords"] = ", ".join(sorted(dict.fromkeys(matched_keywords)))
        row["negative_keywords"] = ", ".join(sorted(dict.fromkeys(negative_hits + ["china/chinese company"])))
        row["country_priority_bucket"] = "excluded_china"
        row["country_priority_boost"] = "-999"
        row["outreach_angle"] = "Excluded from outreach because the exhibitor appears to be China/Hong Kong/Macau based or Chinese-origin."
        return row

    if negative_hits and score < common.PRIORITY_THRESHOLDS["C"]:
        category = "excluded"
        subcategory = "negative_signal"
    if institution_hits:
        category = "excluded"
        subcategory = "institution_or_trade_promotion"
        negative_hits = sorted(dict.fromkeys(negative_hits + institution_hits))

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
    row["country_priority_bucket"] = country_priority_bucket
    row["country_priority_boost"] = str(country_boost)
    row["outreach_angle"] = (
        "Excluded from outreach because this appears to be an institution, trade promotion, community, or other low-fit event listing."
        if subcategory == "institution_or_trade_promotion"
        else "Excluded from outreach because low-fit negative signals outweighed the MTA fit."
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
            0 if row.get("country_priority_bucket") == "priority_vietnam" else 1,
            row.get("company_name", ""),
        ),
    )


def main() -> None:
    args = parse_args()
    paths = configure_event(args.event_slug, args.event_name)
    session = make_session()

    print("Downloading MTA Vietnam exhibitor API data...")
    records = download_records(session, args.api_url, args.list_url)
    paths["raw_json"].write_text(json.dumps(records, ensure_ascii=False, indent=2), encoding="utf-8")
    rows = normalize_rows(records, args.list_url)
    write_csv(paths["raw_csv"], rows)
    excluded_count = sum(1 for row in rows if row.get("excluded_source_reason") == "china_or_chinese_company")
    print(f"Parsed {len(rows)} exhibitors from Informa; marked {excluded_count} China/Chinese-company records for exclusion.")

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

    time.sleep(0.05)

    print(f"Wrote {paths['enriched']}")
    print(f"Wrote {paths['output'] / OUTPUT_FILE_NAMES['relevant']} ({len(relevant_rows)} rows)")
    print(f"Wrote {paths['output'] / OUTPUT_FILE_NAMES['manufacturers']} ({len(manufacturer_rows)} rows)")
    print(f"Wrote {paths['output'] / OUTPUT_FILE_NAMES['partners']} ({len(partner_rows)} rows)")
    print(f"Wrote {paths['output'] / OUTPUT_FILE_NAMES['priority']} ({min(len(relevant_rows), 30)} rows)")


if __name__ == "__main__":
    main()
