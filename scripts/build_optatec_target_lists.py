from __future__ import annotations

import argparse
import csv
import json
import re
import time
import unicodedata
import zipfile
import xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Dict, Iterable, List, Tuple
from urllib.parse import urljoin

import bs4
import requests

import build_target_lists as common


ROOT = Path(__file__).resolve().parents[1]
EVENTS_DIR = ROOT / "events"
DEFAULT_EVENT_SLUG = "optatec"
DEFAULT_EVENT_NAME = "Optatec 2026"
LIST_URL = "https://www.optatec-messe.de/en/list-of-exhibitors/"
AJAX_URL = "https://www.optatec-messe.de/wp-admin/admin-ajax.php"
USER_AGENT = common.USER_AGENT

DATA_FILE_NAMES = {
    "raw": "optatec_exhibitors_raw.xlsx",
    "raw_csv": "optatec_exhibitors_raw.csv",
    "enriched": "hannover_exhibitors_enriched.csv",
    "profile_cache": "profile_cache.json",
    "website_cache": "website_profile_cache.json",
}

OUTPUT_FILE_NAMES = {
    "relevant": "zetamotion_relevant_companies.csv",
    "manufacturers": "zetamotion_manufacturer_targets.csv",
    "partners": "zetamotion_partner_targets.csv",
    "priority": "zetamotion_priority_meeting_targets.csv",
}

OPTATEC_POSITIVE_KEYWORDS = {
    "optical_components": {
        "keywords": [
            "optical component",
            "optical components",
            "optics",
            "lens",
            "lenses",
            "aspheric",
            "spherical",
            "cylindrical lens",
            "prism",
            "prisms",
            "mirror",
            "beam splitter",
            "beamsplitter",
            "window",
            "optical window",
            "filter",
            "optical filter",
            "polariser",
            "polarizer",
            "diffractive",
            "micro-optics",
            "freeform",
        ],
        "weight": 5,
        "cap": 30,
    },
    "optical_materials": {
        "keywords": [
            "optical glass",
            "technical glass",
            "quartz",
            "sapphire",
            "crystal",
            "ceramic",
            "glass ceramic",
            "precision blank",
            "optical material",
            "optical materials",
            "infrared optics",
            "ir optics",
            "uv optics",
        ],
        "weight": 5,
        "cap": 25,
    },
    "coatings": {
        "keywords": [
            "coating",
            "coatings",
            "ar coating",
            "hr coating",
            "thin film",
            "dielectric",
            "interference filter",
            "laser coating",
            "metallic coating",
            "vacuum coating",
        ],
        "weight": 4,
        "cap": 22,
    },
    "manufacturing_process": {
        "keywords": [
            "manufacturing",
            "production",
            "grinding",
            "lapping",
            "polishing",
            "diamond turning",
            "ultraprecision",
            "ultra precision",
            "machining",
            "centring",
            "centering",
            "sawing",
            "cutting",
            "cleaning",
            "vacuum technology",
            "thin-film technology",
            "processing",
        ],
        "weight": 4,
        "cap": 24,
    },
    "metrology_inspection": {
        "keywords": [
            "measurement",
            "measuring",
            "metrology",
            "test instrument",
            "testing",
            "inspection",
            "surface measuring",
            "surface measurement",
            "interferometer",
            "interferometric",
            "spectrometer",
            "goniometer",
            "laser measuring",
            "image processing",
            "machine vision",
            "camera",
            "sensor",
        ],
        "weight": 5,
        "cap": 30,
    },
    "automation_positioning": {
        "keywords": [
            "positioning",
            "assembly system",
            "beam positioning",
            "optomechanical",
            "motion control",
            "automation",
            "robotic",
            "handling",
            "manufacturing system",
            "production system",
        ],
        "weight": 3,
        "cap": 18,
    },
    "laser_fiber": {
        "keywords": [
            "laser",
            "fiber optic",
            "fibre optic",
            "light guide",
            "beam guide",
            "laser diode",
            "fiber laser",
            "fibre laser",
            "optical transmission",
        ],
        "weight": 3,
        "cap": 15,
    },
}

NEGATIVE_KEYWORDS = [
    "publisher",
    "press",
    "media",
    "magazine",
    "institution",
    "university",
    "hochschule",
    "fraunhofer",
    "research institute",
    "trade fair",
    "exhibition organizer",
    "consulting",
    "software only",
]

MANUFACTURER_HINTS = [
    "manufacturer",
    "manufacture",
    "manufacturing",
    "production",
    "producer",
    "factory",
    "fabrication",
    "supplier",
    "optical components and materials",
    "optical components",
    "optical coatings",
    "manufacturing systems",
    "machining",
    "polishing",
    "grinding",
]

PARTNER_HINTS = [
    "metrology",
    "measuring",
    "test technology",
    "image processing",
    "camera",
    "sensor",
    "positioning",
    "automation",
    "optomechanical",
    "software",
    "interferometric",
]


def slugify_event(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", (value or "").strip().lower()).strip("-")
    if not slug:
        raise ValueError("Event slug cannot be empty.")
    return slug


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build Optatec event-scoped scouting CSVs.")
    parser.add_argument("--event-slug", default=DEFAULT_EVENT_SLUG)
    parser.add_argument("--event-name", default=DEFAULT_EVENT_NAME)
    parser.add_argument("--list-url", default=LIST_URL)
    return parser.parse_args()


def configure_event(event_slug: str, event_name: str) -> Dict[str, Path]:
    event_dir = EVENTS_DIR / slugify_event(event_slug)
    data_dir = event_dir / "data"
    output_dir = event_dir / "output"
    data_dir.mkdir(parents=True, exist_ok=True)
    output_dir.mkdir(parents=True, exist_ok=True)

    manifest_path = event_dir / "event.json"
    if not manifest_path.exists():
        manifest = {
            "name": event_name.strip() or event_dir.name.replace("-", " ").title(),
            "description": "CSV-driven scouting dashboard for booth-side outreach at Optatec.",
        }
        manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    common.configure_event(event_dir.name, event_name, common.DEFAULT_EXPORT_URL)
    return {
        "event": event_dir,
        "data": data_dir,
        "output": output_dir,
        "raw_xlsx": data_dir / DATA_FILE_NAMES["raw"],
        "raw_csv": data_dir / DATA_FILE_NAMES["raw_csv"],
        "enriched": data_dir / DATA_FILE_NAMES["enriched"],
        "profile_cache": data_dir / DATA_FILE_NAMES["profile_cache"],
        "website_cache": data_dir / DATA_FILE_NAMES["website_cache"],
    }


def make_session() -> requests.Session:
    session = requests.Session()
    session.headers.update({"User-Agent": USER_AGENT})
    return session


def download_raw_xlsx(session: requests.Session, path: Path) -> None:
    response = session.post(
        AJAX_URL,
        data={"action": "ajax_aussteller_download_all_XLSX_function"},
        timeout=60,
    )
    response.raise_for_status()
    path.write_bytes(response.content)


def cell_reference_to_index(reference: str) -> int:
    letters = re.sub(r"[^A-Z]", "", reference.upper())
    index = 0
    for char in letters:
        index = index * 26 + (ord(char) - ord("A") + 1)
    return index - 1


def read_xlsx_rows(path: Path) -> List[List[str]]:
    ns = {"a": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
    with zipfile.ZipFile(path) as archive:
        shared_strings: List[str] = []
        root = ET.fromstring(archive.read("xl/sharedStrings.xml"))
        for item in root.findall("a:si", ns):
            text_parts = [
                text.text or ""
                for text in item.iter("{http://schemas.openxmlformats.org/spreadsheetml/2006/main}t")
            ]
            shared_strings.append("".join(text_parts))

        sheet = ET.fromstring(archive.read("xl/worksheets/sheet1.xml"))
        rows: List[List[str]] = []
        for row in sheet.findall(".//a:sheetData/a:row", ns):
            values: Dict[int, str] = {}
            for cell in row.findall("a:c", ns):
                ref = cell.attrib.get("r", "A")
                value_node = cell.find("a:v", ns)
                value = "" if value_node is None else value_node.text or ""
                if cell.attrib.get("t") == "s" and value:
                    value = shared_strings[int(value)]
                values[cell_reference_to_index(ref)] = value.strip()
            if values:
                width = max(values) + 1
                rows.append([values.get(index, "") for index in range(width)])
        return rows


def rows_from_xlsx(path: Path) -> List[Dict[str, str]]:
    rows = read_xlsx_rows(path)
    header_index = next(
        index for index, row in enumerate(rows) if row and row[0].strip().lower() == "firma"
    )
    headers = rows[header_index]
    output = []
    for row in rows[header_index + 1 :]:
        if not row or not row[0].strip():
            continue
        padded = row + [""] * (len(headers) - len(row))
        output.append(dict(zip(headers, padded)))
    return output


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


def normalize_company(value: str) -> str:
    value = (value or "").strip().lower()
    value = (
        value.replace("ä", "ae")
        .replace("ö", "oe")
        .replace("ü", "ue")
        .replace("ß", "ss")
        .replace("&", " and ")
    )
    value = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode("ascii")
    value = re.sub(r"\b(ltd|gmbh|inc|ag|co|corp|corporation|pte|kg|llc|sro|s r o|bv|ev|e v)\b\.?", "", value)
    return re.sub(r"[^a-z0-9]+", "-", value).strip("-")


def parse_card(card: bs4.Tag) -> Dict[str, str]:
    profile_anchor = card.find("a", href=re.compile(r"/Exhibitor-Index/"))
    profile_url = profile_anchor.get("href", "") if profile_anchor else ""
    title_text = common.normalize_space(profile_anchor.get_text(" ", strip=True) if profile_anchor else "")
    company_name = ""
    booth = ""
    categories = ""
    title_match = re.match(r"(.+?)\s+Hall\s+(.+?)\s+-\s+Stand\s+(.+?)(?:\s{2,}|\s[A-Z].*)?$", title_text)
    if title_match:
        company_name = common.normalize_space(title_match.group(1))
        booth = f"Hall {common.normalize_space(title_match.group(2))} - Stand {common.normalize_space(title_match.group(3))}"

    lines = [common.normalize_space(line) for line in card.get_text("\n", strip=True).splitlines()]
    lines = [line for line in lines if line]
    if not company_name and lines:
        company_name = lines[0]
    if not booth:
        for index, line in enumerate(lines):
            if line.lower() == "hall" and index + 3 < len(lines):
                booth = f"Hall {lines[index + 1]} - Stand {lines[index + 3]}"
                break

    for index, line in enumerate(lines):
        if booth and line == booth and index + 1 < len(lines):
            categories = lines[index + 1]
            break
        if "Optical components" in line or "Manufacturing systems" in line:
            categories = line
            break

    website = ""
    for anchor in card.find_all("a", href=True):
        href = anchor.get("href", "")
        if href.startswith("http") and "/Exhibitor-Index/" not in href and "optatec-messe.de" not in href:
            website = href
            break

    email = ""
    phone = ""
    for line in lines:
        if "@" in line and not email:
            email = line.replace("E-Mail:", "").strip()
        if line.lower().startswith("telefon:"):
            phone = line.replace("Telefon:", "").strip()

    country = ""
    if company_name in lines:
        repeated_index = next(
            (index for index, line in enumerate(lines[1:], start=1) if line == company_name),
            -1,
        )
        if repeated_index >= 0:
            for line in lines[repeated_index + 1 :]:
                lower = line.lower()
                if lower.startswith("telefon:") or lower.startswith("e-mail:") or line.startswith("www."):
                    break
                country = line
            country = country.strip()

    return {
        "company_name": company_name,
        "booth": booth,
        "profile_url": profile_url,
        "website": website,
        "category": categories,
        "country": country,
        "email": email,
        "phone": phone,
    }


def scrape_cards(session: requests.Session, list_url: str) -> Dict[str, Dict[str, str]]:
    first_html = session.get(list_url, timeout=60).text
    first_soup = bs4.BeautifulSoup(first_html, "html.parser")
    total = int(first_soup.select_one("#anzahlAussteller").get("value", "0"))
    pages = max(1, (total + 99) // 100)
    card_map: Dict[str, Dict[str, str]] = {}

    for page in range(1, pages + 1):
        url = list_url if page == 1 else f"{list_url}?pg={page}"
        html_text = first_html if page == 1 else session.get(url, timeout=60).text
        soup = bs4.BeautifulSoup(html_text, "html.parser")
        for card in soup.select(".nfpost.ausstellerprofil"):
            parsed = parse_card(card)
            key = normalize_company(parsed["company_name"])
            if key:
                card_map[key] = parsed
        time.sleep(0.25)

    return card_map


def extract_profile_fields(html_text: str) -> Dict[str, str]:
    soup = bs4.BeautifulSoup(html_text, "html.parser")
    title = soup.title.get_text(" ", strip=True) if soup.title else ""
    meta = soup.find("meta", attrs={"name": "description"})
    meta_description = meta.get("content", "").strip() if meta else ""
    text = soup.get_text("\n", strip=True)
    product_text = ""
    if "Products & Services" in text:
        product_text = text.split("Products & Services", 1)[1].split("Stay up to date", 1)[0]
    product_lines = [
        common.normalize_space(line)
        for line in product_text.splitlines()
        if common.normalize_space(line)
    ]
    return {
        "profile_title": title,
        "profile_meta_description": meta_description,
        "profile_headings": " | ".join(product_lines[:24]),
    }


def load_json_cache(path: Path) -> Dict[str, Dict[str, str]]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def save_json_cache(path: Path, cache: Dict[str, Dict[str, str]]) -> None:
    path.write_text(json.dumps(cache, ensure_ascii=False, indent=2), encoding="utf-8")


def enrich_profiles(session: requests.Session, rows: List[Dict[str, str]], cache_path: Path) -> List[Dict[str, str]]:
    cache = load_json_cache(cache_path)
    urls = sorted({row["profile_url"] for row in rows if row.get("profile_url") and row["profile_url"] not in cache})

    if urls:
        print(f"Fetching {len(urls)} Optatec profiles...")
        with ThreadPoolExecutor(max_workers=8) as executor:
            future_map = {
                executor.submit(lambda url: extract_profile_fields(session.get(url, timeout=30).text), url): url
                for url in urls
            }
            for future in as_completed(future_map):
                url = future_map[future]
                try:
                    cache[url] = future.result()
                except Exception as exc:
                    cache[url] = {
                        "profile_title": "",
                        "profile_meta_description": "",
                        "profile_headings": "",
                        "profile_fetch_error": str(exc),
                    }
        save_json_cache(cache_path, cache)

    enriched = []
    for row in rows:
        merged = dict(row)
        merged.update(cache.get(row.get("profile_url", ""), {}))
        enriched.append(merged)
    return enriched


def should_fetch_website(row: Dict[str, str]) -> bool:
    country_bucket, _ = common.get_country_priority(row.get("country", ""))
    if country_bucket == "excluded_china":
        return False
    return bool(common.normalize_website(row.get("website", "")))


def enrich_company_websites(rows: List[Dict[str, str]], cache_path: Path) -> List[Dict[str, str]]:
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
        print(f"Fetching {len(missing_urls)} company websites for Optatec context...")
        with ThreadPoolExecutor(max_workers=8) as executor:
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


def derive_category(hit_map: Dict[str, List[str]], text: str) -> Tuple[str, str]:
    manufacturer_signal = bool(keyword_hits(text, MANUFACTURER_HINTS))
    partner_signal = bool(keyword_hits(text, PARTNER_HINTS))
    product_signal = bool(
        hit_map["optical_components"]
        or hit_map["optical_materials"]
        or hit_map["coatings"]
        or hit_map["laser_fiber"]
    )

    if product_signal and manufacturer_signal:
        if hit_map["coatings"]:
            return "manufacturer_target", "optical_coatings_or_filters"
        if hit_map["optical_materials"]:
            return "manufacturer_target", "optical_materials_or_glass"
        return "manufacturer_target", "optical_components"
    if hit_map["metrology_inspection"] or partner_signal:
        return "partner_target", "optical_metrology_or_machine_vision"
    if hit_map["manufacturing_process"] or hit_map["automation_positioning"]:
        return "partner_target", "optics_manufacturing_systems"
    if product_signal:
        return "review_target", "optics_product_company"
    return "review_target", "general_optics_fit"


def build_outreach_angle(category: str, subcategory: str) -> str:
    if subcategory == "optical_coatings_or_filters":
        return "Discuss defect detection and surface inspection for optical coatings, filters, mirrors, and coated components."
    if subcategory == "optical_materials_or_glass":
        return "Discuss inspection workflows for optical glass, crystals, blanks, sapphire, quartz, or precision optical materials."
    if subcategory == "optical_components":
        return "Discuss component-level visual inspection for lenses, prisms, mirrors, windows, micro-optics, and precision optical assemblies."
    if subcategory == "optical_metrology_or_machine_vision":
        return "Explore partnership around optical metrology, machine vision, imaging, surface measurement, or inspection hardware."
    if subcategory == "optics_manufacturing_systems":
        return "Explore integration opportunities around optics manufacturing, polishing, grinding, positioning, or process equipment."
    if subcategory == "optics_product_company":
        return "Manual review recommended: optics product fit is visible, but manufacturing or inspection need should be confirmed."
    return "Manual review recommended before outreach."


def score_row(row: Dict[str, str]) -> Dict[str, str]:
    text = common.normalize_space(
        " ".join(
            [
                row.get("company_name", ""),
                row.get("category", ""),
                row.get("profile_meta_description", ""),
                row.get("profile_headings", ""),
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
    for bucket, spec in OPTATEC_POSITIVE_KEYWORDS.items():
        hits = keyword_hits(text, spec["keywords"])
        hit_map[bucket] = hits
        score += min(len(hits) * spec["weight"], spec["cap"])
        matched_keywords.extend(hits)

    country_priority_bucket, country_boost = common.get_country_priority(row.get("country", ""))
    score += country_boost

    negative_hits = keyword_hits(text, NEGATIVE_KEYWORDS)
    score -= min(len(negative_hits) * 7, 21)

    category, subcategory = derive_category(hit_map, text)
    hard_excluded = bool(negative_hits and any(
        hit in {
            "publisher",
            "press",
            "media",
            "magazine",
            "institution",
            "university",
            "hochschule",
            "fraunhofer",
            "research institute",
            "trade fair",
            "exhibition organizer",
        }
        for hit in negative_hits
    ))
    if country_priority_bucket == "excluded_china":
        category = "excluded"
        subcategory = "excluded_country"
        score = min(score, 0)
    elif hard_excluded:
        category = "excluded"
        subcategory = "institution_media_or_research"
        score = min(score, 0)
    elif negative_hits and score < 24:
        category = "excluded"
        subcategory = "negative_signal"

    if category == "manufacturer_target":
        score += 6
    elif category == "partner_target":
        score += 4

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
        "Excluded from outreach because the exhibitor is based in China or Hong Kong."
        if subcategory == "excluded_country"
        else build_outreach_angle(category, subcategory)
    )
    return row


def sort_rows(rows: List[Dict[str, str]]) -> List[Dict[str, str]]:
    return sorted(
        rows,
        key=lambda row: (
            {"A": 0, "B": 1, "C": 2, "": 3}.get(row.get("priority_band", ""), 4),
            -int(row.get("score", "0")),
            row.get("company_name", ""),
        ),
    )


def infer_country(raw_country: str, row: Dict[str, str], card: Dict[str, str]) -> str:
    country = card.get("country") or raw_country
    text = " ".join(
        [
            row.get("Firma", ""),
            row.get("Ort", ""),
            row.get("PLZ", ""),
            card.get("phone", ""),
            card.get("website", ""),
        ]
    ).lower()
    chinese_signals = [
        "+86",
        "changchun",
        "fuzhou",
        "shenzhen",
        "ningbo",
        "zhengzhou",
        "nanyang",
        "jiangxi",
        "hangzhou",
        "dongguan",
        "chengdu",
        "chongqing",
        "guangzhou",
        ".com.cn",
    ]
    if any(signal in text for signal in chinese_signals):
        return "China"
    return country


def normalize_rows(raw_rows: List[Dict[str, str]], card_map: Dict[str, Dict[str, str]]) -> List[Dict[str, str]]:
    normalized = []
    for raw in raw_rows:
        company_name = raw.get("Firma", "").strip()
        key = normalize_company(company_name)
        card = card_map.get(key, {})
        hall = raw.get("Halle", "").strip()
        stand = raw.get("Stand", "").strip()
        booth = card.get("booth") or (f"Hall {hall} - Stand {stand}" if hall or stand else "")
        normalized.append(
            {
                "hit_type": "Exhibitor",
                "company_name": company_name,
                "country": infer_country(raw.get("Land", "").strip(), raw, card),
                "zip_code": raw.get("PLZ", "").strip(),
                "city": raw.get("Ort", "").strip(),
                "federal_state": "",
                "website": card.get("website", ""),
                "booth": booth,
                "profile_url": card.get("profile_url", ""),
                "email": card.get("email", ""),
                "phone": card.get("phone", ""),
                "category": card.get("category", ""),
            }
        )
    return normalized


def main() -> None:
    args = parse_args()
    paths = configure_event(args.event_slug, args.event_name)
    session = make_session()

    print("Downloading official Optatec exhibitor XLSX...")
    download_raw_xlsx(session, paths["raw_xlsx"])
    raw_rows = rows_from_xlsx(paths["raw_xlsx"])
    print(f"Parsed {len(raw_rows)} exhibitors from the official XLSX export.")

    print("Scraping Optatec exhibitor list pages...")
    card_map = scrape_cards(session, args.list_url)
    rows = normalize_rows(raw_rows, card_map)
    write_csv(paths["raw_csv"], rows)

    rows = enrich_profiles(session, rows, paths["profile_cache"])
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

    print(f"Wrote {paths['enriched']}")
    print(f"Wrote {paths['output'] / OUTPUT_FILE_NAMES['relevant']} ({len(relevant_rows)} rows)")
    print(f"Wrote {paths['output'] / OUTPUT_FILE_NAMES['manufacturers']} ({len(manufacturer_rows)} rows)")
    print(f"Wrote {paths['output'] / OUTPUT_FILE_NAMES['partners']} ({len(partner_rows)} rows)")
    print(f"Wrote {paths['output'] / OUTPUT_FILE_NAMES['priority']} ({min(len(relevant_rows), 30)} rows)")


if __name__ == "__main__":
    main()
