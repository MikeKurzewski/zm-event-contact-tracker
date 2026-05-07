from __future__ import annotations

import csv
import html
import argparse
import json
import random
import re
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Dict, Iterable, List, Tuple
from urllib.parse import urljoin, urlparse

import bs4
import requests


ROOT = Path(__file__).resolve().parents[1]
EVENTS_DIR = ROOT / "events"
DEFAULT_EVENT_SLUG = "hannover-messe"
DEFAULT_EVENT_NAME = "Hannover Messe"
DEFAULT_EXPORT_URL = "https://www.hannovermesse.de/en/application/exhibitor-index/csvExport?rt=ex&sort=AZ"

EVENT_DIR = EVENTS_DIR / DEFAULT_EVENT_SLUG
DATA_DIR = EVENT_DIR / "data"
OUTPUT_DIR = EVENT_DIR / "output"
CACHE_PATH = DATA_DIR / "profile_cache.json"
WEBSITE_CACHE_PATH = DATA_DIR / "website_profile_cache.json"
RAW_EXPORT_PATH = DATA_DIR / "hannover_exhibitors_raw.csv"
ENRICHED_PATH = DATA_DIR / "hannover_exhibitors_enriched.csv"
RELEVANT_PATH = OUTPUT_DIR / "zetamotion_relevant_companies.csv"
MANUFACTURERS_PATH = OUTPUT_DIR / "zetamotion_manufacturer_targets.csv"
PARTNERS_PATH = OUTPUT_DIR / "zetamotion_partner_targets.csv"
PRIORITY_PATH = OUTPUT_DIR / "zetamotion_priority_meeting_targets.csv"

EXPORT_URL = DEFAULT_EXPORT_URL
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/135.0.0.0 Safari/537.36"
)

ABOUT_LINK_HINTS = [
    "about",
    "about-us",
    "company",
    "our-company",
    "who-we-are",
    "corporate",
    "profile",
    "ueber-uns",
    "uber-uns",
    "unternehmen",
]

ABOUT_PATH_GUESSES = [
    "/about",
    "/about-us",
    "/company",
    "/our-company",
    "/who-we-are",
    "/en/about",
    "/en/about-us",
    "/company/profile",
]

WEBSITE_EMPTY = {
    "website_home_url": "",
    "website_home_title": "",
    "website_home_meta_description": "",
    "website_home_headings": "",
    "website_about_url": "",
    "website_about_title": "",
    "website_about_meta_description": "",
    "website_about_headings": "",
}


POSITIVE_KEYWORDS = {
    "flat_product": {
        "keywords": [
            "flat rolled",
            "flat-rolled",
            "sheet metal",
            "sheet steel",
            "steel sheet",
            "sheet",
            "coil",
            "slit coil",
            "strip",
            "wide strip",
            "plate",
            "foil",
            "film",
            "membrane",
            "flat panel",
            "flat panels",
            "wall panel",
            "wall panels",
            "door panel",
            "door panels",
            "cabinet panel",
            "cabinet panels",
            "laminated panel",
            "laminated panels",
            "decorative panel",
            "decorative panels",
            "sandwich panel",
            "sandwich panels",
            "laminate",
            "laminated",
            "coil coated",
            "coil-coated",
            "galvanized",
            "galvanised",
            "cold rolled",
            "cold-rolled",
            "hot rolled",
            "hot-rolled",
            "blank",
            "blanks",
            "blanking",
            "slitting",
            "nonwoven",
            "woven",
            "textile",
            "fabric",
            "coated fabric",
            "coated fabrics",
            "laminated fabric",
            "laminated fabrics",
            "web inspection",
        ],
        "weight": 6,
        "cap": 30,
    },
    "metals": {
        "keywords": [
            "metalworking",
            "metal processing",
            "metal",
            "steel",
            "aluminum",
            "aluminium",
            "copper",
            "stainless",
            "forging",
            "forged",
            "stamping",
            "press tools",
            "pressing",
            "roll forming",
            "rolling mill",
            "pickling",
            "machined parts",
            "semi-finished",
            "slab",
            "slabs",
            "flat bar",
            "flat bars",
            "wire mesh",
        ],
        "weight": 4,
        "cap": 24,
    },
    "composites_textiles": {
        "keywords": [
            "composite",
            "composites",
            "lightweight",
            "carbon fiber",
            "carbon fibre",
            "glass fiber",
            "glass fibre",
            "fiberglass",
            "technical textile",
            "fiber-reinforced",
            "fibre-reinforced",
            "prepreg",
            "pre-preg",
            "pultrusion",
            "pullwinding",
            "filament winding",
            "resin transfer moulding",
            "resin transfer molding",
            "rtm",
            "sheet moulding compound",
            "sheet molding compound",
            "smc",
            "bulk moulding compound",
            "bulk molding compound",
            "bmc",
            "gfrp",
            "cfrp",
            "frp",
            "woven roving",
            "woven rovings",
            "glass mat",
            "carbon fabric",
            "glass fabric",
            "technical fabric",
            "technical fabrics",
            "filtration fabric",
            "filtration fabrics",
            "coating carrier",
            "coating carriers",
            "scrim",
            "scrims",
            "needle punched",
            "needle-punched",
            "needle felt",
            "needlefelt",
            "spunlace",
            "spunlaced",
            "spunbond",
            "hydroentanglement",
            "air through bonding",
            "air-through bonding",
            "woven mesh",
            "calendering",
            "calendaring",
            "nonwoven",
            "nonwovens",
            "fabric",
            "textile",
            "laminate",
        ],
        "weight": 5,
        "cap": 28,
    },
    "furniture_casework": {
        "keywords": [
            "cabinet door",
            "cabinet doors",
            "drawer front",
            "drawer fronts",
            "casework",
            "millwork",
            "architectural woodwork",
            "furniture component",
            "furniture components",
            "furniture panel",
            "furniture panels",
            "decorative laminate",
            "thermally fused laminate",
            "tfl",
            "hpdl",
            "hpl",
            "mdf",
            "particleboard",
            "plywood",
            "veneer panel",
            "veneer panels",
            "face veneer",
            "panel layup",
            "edgebanding",
            "edge banding",
            "laminated board",
            "laminated boards",
        ],
        "weight": 5,
        "cap": 24,
    },
    "specialty_glass": {
        "keywords": [
            "architectural glass",
            "decorative glass",
            "facade glazing",
            "flat glass",
            "glass panel",
            "glass panels",
            "insulating glass",
            "laminated glass",
            "lighting panel",
            "lighting panels",
            "photovoltaic module",
            "photovoltaic panel",
            "pv module",
            "solar glass",
            "solar panel",
            "solar panels",
        ],
        "weight": 6,
        "cap": 30,
    },
    "roofing_building": {
        "keywords": [
            "roofing",
            "roofing products",
            "roof tile",
            "roof tiles",
            "roof panel",
            "roof panels",
            "roof membrane",
            "roofing sheet",
            "metal roofing",
            "asphalt shingle",
            "asphalt shingles",
            "bitumen shingle",
            "bitumen shingles",
            "composite shingle",
            "composite shingles",
            "sandwich panel",
            "shingle",
            "shingles",
            "standing seam",
            "clay tile",
            "concrete tile",
            "corrugated sheet",
        ],
        "weight": 5,
        "cap": 24,
    },
    "inspection_metrology": {
        "keywords": [
            "inspection",
            "visual inspection",
            "quality control",
            "quality assurance",
            "surface inspection",
            "metrology",
            "measurement",
            "testing",
            "test equipment",
            "analysis equipment",
            "camera",
            "machine vision",
            "vision system",
            "scanner",
            "sensor",
            "x-ray",
            "ndt",
            "sorting machine",
        ],
        "weight": 5,
        "cap": 30,
    },
    "automation_station_builders": {
        "keywords": [
            "automation",
            "robotic",
            "robotics",
            "machine builder",
            "special machine",
            "turnkey",
            "production line",
            "assembly automation",
            "test bench",
            "equipment manufacturer",
        ],
        "weight": 3,
        "cap": 18,
    },
    "ai_inspection": {
        "keywords": [
            "ai inspection",
            "artificial intelligence",
            "computer vision",
            "defect detection",
            "visual intelligence",
            "image processing",
            "industrial ai",
            "quality analytics",
            "predictive quality",
            "machine learning",
        ],
        "weight": 5,
        "cap": 25,
    },
}

NEGATIVE_KEYWORDS = [
    "consulting",
    "service provider",
    "sap service provider",
    "erp",
    "crm",
    "cloud",
    "digital transformation",
    "enterprise software",
    "business process",
    "business processes",
    "saas platform",
    "investment office",
    "ministry",
    "association",
    "chamber of commerce",
    "chambers of commerce",
    "trade promotion",
    "chamber of commerce",
    "university",
    "research center",
    "research centre",
    "institute",
    "law firm",
    "media",
    "newsletter",
]

SYNTHETIC_DATA_COMPETITOR_KEYWORDS = [
    "synthetic data",
    "synthetic dataset",
    "synthetic datasets",
]

AI_COMPETITOR_KEYWORDS = [
    "ai",
    "artificial intelligence",
    "machine learning",
    "computer vision",
    "industrial ai",
]

MANUFACTURING_CONFIRMATION_KEYWORDS = [
    "manufacturer",
    "manufacturers",
    "manufacture",
    "manufactures",
    "manufactured",
    "manufacturing",
    "production",
    "producer",
    "producers",
    "produces",
    "produced",
    "factory",
    "factories",
    "fabrication",
    "fabricator",
    "fabricators",
    "fabricating",
    "fabricated",
    "production facility",
    "production facilities",
    "production plant",
    "production plants",
    "industrial producer",
    "oem",
    "rolling mill",
    "cold rolling",
    "hot rolling",
    "coil coating",
    "slitting",
    "blanking",
    "pultrusion",
    "filament winding",
    "resin transfer moulding",
    "resin transfer molding",
    "sheet moulding compound",
    "sheet molding compound",
    "press moulding",
    "press molding",
    "weaving",
    "knitting",
    "nonwovens production",
    "lamination",
    "laminating",
    "coating",
    "coated",
    "impregnated",
    "machining",
    "panel layup",
    "edgebanding",
]

MANUAL_EXCLUDED_COMPANIES = {
    "24 VISION a.s.": "Clear AI visual inspection competitor rather than a partner target.",
    "AMA Digital Networks GmbH": "Media publisher, not an inspection hardware or manufacturing target.",
    "ANTICIPATE GmbH": "Clear AI quality inspection competitor rather than a partner target.",
    "Aeon Robotics GmbH": "General robotics company, not a strong inspection-specific target.",
    "Ai-Innovate Solution Inc.": "Clear AI machine vision inspection competitor.",
    "Automation Steeg und Hoffmeyer GmbH": "Automation and machine builder for composites, not a target manufacturer.",
    "Brandenburgische Technische Universität Cottbus-Senftenberg +4930912075": "University/science park entry, not an exhibitor target account.",
    "Camara de Comercio de Gipuzkoa": "Chamber of commerce / supplier matching service, not a manufacturer target.",
    "Coriolis Group SAS": "Composite production automation vendor, not a target manufacturer.",
    "Dataguess Teknoloji San. ve Tic. A.S.": "AI/computer vision inspection software competitor.",
    "Dell Technologies Inc.": "Generic industrial AI infrastructure vendor, too broad for this target list.",
    "Deutsche Messe AG": "Trade fair organizer / academy content, not an outreach target.",
    "Duatic AG": "Robotics company, not a target manufacturer.",
    "Ehrt - Maschinenbau GmbH & Co. KG": "Machine builder, not a target manufacturer.",
    "Follow Inspiration, S.A.": "Robotics automation company, not an inspection-focused target.",
    "Fraunhofer-Institut für Fertigungstechnik und Angewandte Materialforschung IFAM": "Research institute, not a commercial outreach target.",
    "Generative Robotics BV": "General robotics automation company, not an inspection-focused target.",
    "Gestalt Automation GmbH": "AI-powered inspection systems competitor.",
    "Gräbener Maschinentechnik GmbH & Co. KG": "Manufacturing process and machine developer, not a target manufacturer.",
    "IndustrialMind.ai INC.": "Generic manufacturing AI platform, not a focused inspection target.",
    "Infinite Uptime Inc.": "Industrial AI maintenance/reliability platform, not a manufacturing or inspection target.",
    "Instituto de Soldadura e Qualidade, ISQ": "Inspection/testing/training services organization, not a product partner target.",
    "Invisible AI Inc.": "Production visibility analytics company, not a focused inspection target.",
    "Kurokesu UAB": "Generic imaging/mechatronics supplier across robotics and research, not a focused inspection target.",
    "Ma.ia Solutions Ltda.": "AI/computer vision inspection SaaS competitor.",
    "Mztec - Servicos em Tecnologia Ltda": "AI-driven visual inspection software competitor.",
    "NanoSen GmbH": "Generic force sensor company, not a focused inspection/metrology target for this list.",
    "Panni e Lazzarini srl": "Industrial assembly services company, not a core inspection partner target.",
    "RealSense, Inc.": "General robot perception/depth sensing platform, not a focused inspection target.",
    "Robert Bosch GmbH": "Too broad and generic as a conglomerate-level target.",
    "Steiner Elektronik EOOD": "EMS / PCB assembly provider, not a core inspection partner target.",
    "Stierli-Bieger AG": "Machine builder, not a target manufacturer.",
    "Termica Solutions Engenharia Ltda": "AI-driven quality-control software competitor.",
    "Vaski Group Oy": "Metalworking machinery and production-line supplier, not a target manufacturer.",
    "Virtek Vision International Inc.": "Inspection systems vendor misclassified as a manufacturer target.",
    "ZET Redüktör Sanayi ve Ticaret A.S.": "Gearbox manufacturer misclassified as an inspection/metrology target.",
    "dp-Consultec e.K.": "Consulting / representative company, not a manufacturer target.",
    "psps business abroad b.v.": "Trade promotion / export support company, not a direct target.",
}

PRIORITY_THRESHOLDS = {"A": 36, "B": 26, "C": 18}

EXCLUDED_COUNTRIES = {
    "china",
    "hong kong",
    "hong kong sar",
    "hong kong, china",
}

EUROPE_PRIORITY_COUNTRIES = {
    "austria",
    "belgium",
    "bulgaria",
    "croatia",
    "czech republic",
    "denmark",
    "estonia",
    "finland",
    "france",
    "germany",
    "greece",
    "hungary",
    "iceland",
    "ireland",
    "italy",
    "latvia",
    "liechtenstein",
    "lithuania",
    "luxembourg",
    "netherlands",
    "norway",
    "poland",
    "portugal",
    "romania",
    "slovakia",
    "slovenia",
    "spain",
    "sweden",
    "switzerland",
}

MIDDLE_EAST_PRIORITY_COUNTRIES = {
    "bahrain",
    "israel",
    "jordan",
    "kuwait",
    "lebanon",
    "oman",
    "qatar",
    "saudi arabia",
    "turkey",
    "turkiye",
    "türkiye",
    "united arab emirates",
}

COUNTRY_BOOSTS = [
    ("priority_uk", {"united kingdom", "uk", "great britain"}, 8),
    ("priority_usa", {"united states", "united states of america", "usa"}, 8),
    ("priority_vietnam", {"vietnam"}, 8),
    ("priority_middle_east", MIDDLE_EAST_PRIORITY_COUNTRIES, 7),
    ("priority_europe", EUROPE_PRIORITY_COUNTRIES, 6),
]


def slugify_event(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", (value or "").strip().lower()).strip("-")
    if not slug:
        raise ValueError("Event slug cannot be empty.")
    return slug


def configure_event(event_slug: str, event_name: str, export_url: str) -> None:
    global EVENT_DIR
    global DATA_DIR
    global OUTPUT_DIR
    global CACHE_PATH
    global WEBSITE_CACHE_PATH
    global RAW_EXPORT_PATH
    global ENRICHED_PATH
    global RELEVANT_PATH
    global MANUFACTURERS_PATH
    global PARTNERS_PATH
    global PRIORITY_PATH
    global EXPORT_URL

    normalized_slug = slugify_event(event_slug)
    EVENT_DIR = EVENTS_DIR / normalized_slug
    DATA_DIR = EVENT_DIR / "data"
    OUTPUT_DIR = EVENT_DIR / "output"
    CACHE_PATH = DATA_DIR / "profile_cache.json"
    WEBSITE_CACHE_PATH = DATA_DIR / "website_profile_cache.json"
    RAW_EXPORT_PATH = DATA_DIR / "hannover_exhibitors_raw.csv"
    ENRICHED_PATH = DATA_DIR / "hannover_exhibitors_enriched.csv"
    RELEVANT_PATH = OUTPUT_DIR / "zetamotion_relevant_companies.csv"
    MANUFACTURERS_PATH = OUTPUT_DIR / "zetamotion_manufacturer_targets.csv"
    PARTNERS_PATH = OUTPUT_DIR / "zetamotion_partner_targets.csv"
    PRIORITY_PATH = OUTPUT_DIR / "zetamotion_priority_meeting_targets.csv"
    EXPORT_URL = export_url

    EVENT_DIR.mkdir(parents=True, exist_ok=True)
    manifest_path = EVENT_DIR / "event.json"
    if not manifest_path.exists():
        manifest = {
            "name": event_name.strip() or normalized_slug.replace("-", " ").title(),
            "description": "CSV-driven scouting dashboard for booth-side outreach.",
        }
        manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build event-scoped scouting CSVs.")
    parser.add_argument(
        "--event-slug",
        default=DEFAULT_EVENT_SLUG,
        help="Folder slug under events/ for this event.",
    )
    parser.add_argument(
        "--event-name",
        default=DEFAULT_EVENT_NAME,
        help="Display name used on the dashboard event picker.",
    )
    parser.add_argument(
        "--export-url",
        default=DEFAULT_EXPORT_URL,
        help="Hannover-style CSV export URL to scrape.",
    )
    return parser.parse_args()


def ensure_dirs() -> None:
    EVENT_DIR.mkdir(parents=True, exist_ok=True)
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


def make_session() -> requests.Session:
    session = requests.Session()
    session.headers.update({"User-Agent": USER_AGENT})
    return session


def download_export(session: requests.Session) -> str:
    response = session.get(EXPORT_URL, timeout=60)
    response.raise_for_status()
    RAW_EXPORT_PATH.write_bytes(response.content)
    return response.content.decode("iso-8859-1", errors="replace")


def parse_export(csv_text: str) -> List[Dict[str, str]]:
    lines = [line for line in csv_text.splitlines() if line.strip()]
    header_index = next(i for i, line in enumerate(lines) if line.startswith("Hit type;"))
    rows: List[Dict[str, str]] = []
    reader = csv.DictReader(lines[header_index:], delimiter=";")
    for row in reader:
        cleaned = {k.strip(): (v or "").strip() for k, v in row.items() if k}
        if cleaned.get("Hit type") != "Exhibitor":
            continue
        rows.append(
            {
                "hit_type": cleaned.get("Hit type", ""),
                "company_name": cleaned.get("Exhibitor", ""),
                "country": cleaned.get("Country", ""),
                "zip_code": cleaned.get("Zip Code", ""),
                "city": cleaned.get("City", ""),
                "federal_state": cleaned.get("Federal State", ""),
                "website": cleaned.get("Company website", ""),
                "booth": cleaned.get("Booth", ""),
                "profile_url": cleaned.get("Exhibitor presentation", ""),
            }
        )
    return rows


def load_json_cache(path: Path) -> Dict[str, Dict[str, str]]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def save_json_cache(path: Path, cache: Dict[str, Dict[str, str]]) -> None:
    path.write_text(json.dumps(cache, ensure_ascii=False, indent=2), encoding="utf-8")


def extract_profile_fields(html_text: str) -> Dict[str, str]:
    soup = bs4.BeautifulSoup(html_text, "html.parser")
    title = soup.title.get_text(" ", strip=True) if soup.title else ""
    meta = soup.find("meta", attrs={"name": "description"})
    meta_description = meta.get("content", "").strip() if meta else ""
    product_headings = []
    for tag in soup.find_all(["h2", "h3"]):
        text = normalize_space(tag.get_text(" ", strip=True))
        if text and text.lower() != "products":
            product_headings.append(text)
    return {
        "profile_title": title,
        "profile_meta_description": meta_description,
        "profile_headings": " | ".join(product_headings[:10]),
    }


def fetch_profile(url: str) -> Dict[str, str]:
    session = make_session()
    for attempt in range(3):
        try:
            response = session.get(url, timeout=30)
            response.raise_for_status()
            return extract_profile_fields(response.text)
        except Exception:
            if attempt == 2:
                raise
            time.sleep(1.0 + attempt + random.random())
    return {"profile_title": "", "profile_meta_description": "", "profile_headings": ""}


def enrich_profiles(rows: List[Dict[str, str]], max_workers: int = 8) -> List[Dict[str, str]]:
    cache = load_json_cache(CACHE_PATH)
    missing_urls = [row["profile_url"] for row in rows if row["profile_url"] and row["profile_url"] not in cache]

    if missing_urls:
        print(f"Fetching {len(missing_urls)} exhibitor profiles for enrichment...")
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_map = {executor.submit(fetch_profile, url): url for url in missing_urls}
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
        save_json_cache(CACHE_PATH, cache)

    enriched: List[Dict[str, str]] = []
    for row in rows:
        merged = dict(row)
        merged.update(cache.get(row["profile_url"], {}))
        enriched.append(merged)
    return enriched


def normalize_space(value: str) -> str:
    return re.sub(r"\s+", " ", html.unescape(value or "")).strip()


def normalize_country(value: str) -> str:
    return normalize_space(value).lower()


def normalize_website(value: str) -> str:
    value = normalize_space(value)
    if not value:
        return ""
    if "://" not in value:
        value = "https://" + value
    return value


def get_country_priority(country: str) -> Tuple[str, int]:
    normalized = normalize_country(country)
    if normalized in EXCLUDED_COUNTRIES or "china" in normalized:
        return "excluded_china", -999
    for label, countries, boost in COUNTRY_BOOSTS:
        if normalized in countries:
            return label, boost
    return "", 0


def extract_web_fields(html_text: str) -> Dict[str, str]:
    soup = bs4.BeautifulSoup(html_text, "html.parser")
    title = soup.title.get_text(" ", strip=True) if soup.title else ""

    meta_description = ""
    for attrs in (
        {"name": "description"},
        {"property": "og:description"},
        {"name": "twitter:description"},
    ):
        tag = soup.find("meta", attrs=attrs)
        if tag and tag.get("content"):
            meta_description = normalize_space(tag.get("content", ""))
            if meta_description:
                break

    headings = []
    for tag in soup.find_all(["h1", "h2", "h3"]):
        text = normalize_space(tag.get_text(" ", strip=True))
        if text:
            headings.append(text)

    return {
        "title": normalize_space(title),
        "meta_description": meta_description,
        "headings": " | ".join(headings[:8]),
    }


def same_domain(url_a: str, url_b: str) -> bool:
    try:
        host_a = urlparse(url_a).netloc.lower()
        host_b = urlparse(url_b).netloc.lower()
    except Exception:
        return False
    if host_a.startswith("www."):
        host_a = host_a[4:]
    if host_b.startswith("www."):
        host_b = host_b[4:]
    return bool(host_a and host_b and host_a == host_b)


def fetch_page(session: requests.Session, url: str) -> Tuple[str, Dict[str, str], str]:
    response = session.get(url, timeout=25)
    response.raise_for_status()
    content_type = (response.headers.get("content-type") or "").lower()
    if "text/html" not in content_type:
        raise ValueError(f"Unsupported content type: {content_type}")
    return response.url, extract_web_fields(response.text), response.text


def find_about_url(base_url: str, html_text: str) -> str:
    soup = bs4.BeautifulSoup(html_text, "html.parser")
    for anchor in soup.find_all("a", href=True):
        href = normalize_space(anchor.get("href", ""))
        anchor_text = normalize_space(anchor.get_text(" ", strip=True)).lower()
        href_lower = href.lower()
        if not any(hint in href_lower or hint in anchor_text for hint in ABOUT_LINK_HINTS):
            continue
        candidate = urljoin(base_url, href)
        if same_domain(base_url, candidate):
            return candidate
    return ""


def fetch_company_website(website_url: str) -> Dict[str, str]:
    session = make_session()
    normalized_url = normalize_website(website_url)
    if not normalized_url:
        return dict(WEBSITE_EMPTY)

    result = dict(WEBSITE_EMPTY)
    homepage_url, homepage_fields, homepage_html = fetch_page(session, normalized_url)
    result["website_home_url"] = homepage_url
    result["website_home_title"] = homepage_fields["title"]
    result["website_home_meta_description"] = homepage_fields["meta_description"]
    result["website_home_headings"] = homepage_fields["headings"]

    about_url = find_about_url(homepage_url, homepage_html)
    if not about_url:
        for path in ABOUT_PATH_GUESSES:
            candidate = urljoin(homepage_url, path)
            if not same_domain(homepage_url, candidate):
                continue
            try:
                about_url, about_fields, _ = fetch_page(session, candidate)
                result["website_about_url"] = about_url
                result["website_about_title"] = about_fields["title"]
                result["website_about_meta_description"] = about_fields["meta_description"]
                result["website_about_headings"] = about_fields["headings"]
                return result
            except Exception:
                continue
        return result

    try:
        about_url, about_fields, _ = fetch_page(session, about_url)
        result["website_about_url"] = about_url
        result["website_about_title"] = about_fields["title"]
        result["website_about_meta_description"] = about_fields["meta_description"]
        result["website_about_headings"] = about_fields["headings"]
    except Exception:
        pass

    return result


def should_fetch_company_website(row: Dict[str, str]) -> bool:
    website = normalize_website(row.get("website", ""))
    if not website:
        return False

    preliminary = score_row(dict(row), include_company_website=False)
    if preliminary.get("category") == "excluded":
        return False

    positive_signal = bool(preliminary.get("matched_keywords"))
    score = int(preliminary.get("score", "0"))
    return positive_signal or score >= 12


def enrich_company_websites(rows: List[Dict[str, str]], max_workers: int = 6) -> List[Dict[str, str]]:
    cache = load_json_cache(WEBSITE_CACHE_PATH)
    candidate_urls = sorted(
        {
            normalize_website(row.get("website", ""))
            for row in rows
            if should_fetch_company_website(row)
        }
    )
    candidate_urls = [url for url in candidate_urls if url and url not in cache]

    if candidate_urls:
        print(f"Fetching {len(candidate_urls)} company websites for extra context...")
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_map = {executor.submit(fetch_company_website, url): url for url in candidate_urls}
            for future in as_completed(future_map):
                url = future_map[future]
                try:
                    cache[url] = future.result()
                except Exception as exc:
                    failed = dict(WEBSITE_EMPTY)
                    failed["website_home_title"] = ""
                    failed["website_home_meta_description"] = ""
                    failed["website_home_headings"] = ""
                    failed["website_about_title"] = ""
                    failed["website_about_meta_description"] = ""
                    failed["website_about_headings"] = ""
                    failed["website_home_url"] = url
                    failed["website_about_url"] = ""
                    failed["website_fetch_error"] = str(exc)
                    cache[url] = failed
        save_json_cache(WEBSITE_CACHE_PATH, cache)

    enriched: List[Dict[str, str]] = []
    for row in rows:
        merged = dict(row)
        merged.update(WEBSITE_EMPTY)
        merged.update(cache.get(normalize_website(row.get("website", "")), {}))
        enriched.append(merged)
    return enriched


def keyword_hits(text: str, keywords: Iterable[str]) -> List[str]:
    lowered = text.lower()
    hits = []
    for keyword in keywords:
        pattern = r"\b" + re.escape(keyword).replace(r"\ ", r"\s+") + r"\b"
        if re.search(pattern, lowered):
            hits.append(keyword)
    return hits


def derive_category(hit_map: Dict[str, List[str]], has_manufacturing_signal: bool) -> Tuple[str, str]:
    product_signal = bool(
        hit_map["flat_product"]
        or hit_map["metals"]
        or hit_map["composites_textiles"]
        or hit_map["furniture_casework"]
        or hit_map["specialty_glass"]
        or hit_map["roofing_building"]
    )
    manufacturer_signal = product_signal and has_manufacturing_signal

    if hit_map["furniture_casework"] and manufacturer_signal:
        return "manufacturer_target", "furniture_casework_panels"
    if hit_map["roofing_building"] and manufacturer_signal:
        return "manufacturer_target", "roofing_building_materials"
    if hit_map["specialty_glass"] and manufacturer_signal:
        return "manufacturer_target", "specialty_glass_products"
    if hit_map["composites_textiles"] and manufacturer_signal:
        return "manufacturer_target", "composites_textiles_materials"
    if hit_map["flat_product"] and hit_map["metals"] and manufacturer_signal:
        return "manufacturer_target", "flat_metal_products"
    if hit_map["metals"] and manufacturer_signal:
        return "manufacturer_target", "metal_components_or_processing"
    if hit_map["ai_inspection"] and not manufacturer_signal:
        return "partner_target", "ai_inspection_or_data_partner"
    if hit_map["inspection_metrology"] and not manufacturer_signal:
        return "partner_target", "inspection_hardware_or_metrology"
    if hit_map["automation_station_builders"] and not manufacturer_signal:
        return "partner_target", "automation_or_station_builder"
    return "review_target", "general_industrial_fit"


def build_outreach_angle(category: str, subcategory: str) -> str:
    if subcategory == "furniture_casework_panels":
        return "Discuss surface inspection and component verification for cabinet doors, drawer fronts, laminated panels, and furniture casework parts."
    if subcategory == "flat_metal_products":
        return "Discuss inline surface defect inspection and component verification for sheet, strip, plate, or coil-like products."
    if subcategory == "specialty_glass_products":
        return "Discuss surface and defect inspection for specialty glass, lighting panels, solar modules, or architectural glass products."
    if subcategory == "composites_textiles_materials":
        return "Discuss synthetic-data-driven inspection for composites, fabrics, nonwovens, laminates, or lightweight materials."
    if subcategory == "roofing_building_materials":
        return "Discuss surface inspection for roof tiles, shingles, roofing panels, membranes, or related building-product lines."
    if subcategory == "metal_components_or_processing":
        return "Discuss repeatable metal part inspection, defect detection, and station integration for QA."
    if subcategory == "inspection_hardware_or_metrology":
        return "Explore integration with manual or semi-automated inspection hardware, sensors, or metrology equipment."
    if subcategory == "automation_or_station_builder":
        return "Explore OEM or integration partnership around dedicated inspection cells and QA stations."
    if subcategory == "ai_inspection_or_data_partner":
        return "Explore partnership around synthetic data, computer vision, and industrial AI inspection workflows."
    return "Manual review recommended before outreach."


def manual_exclusion_reason(row: Dict[str, str]) -> str:
    return MANUAL_EXCLUDED_COMPANIES.get(row.get("company_name", "").strip(), "")


def should_exclude_partner_competitor(row: Dict[str, str], category: str) -> bool:
    if category != "partner_target":
        return False

    description_text = normalize_space(
        " ".join(
            [
                row.get("profile_meta_description", ""),
                row.get("website_home_meta_description", ""),
                row.get("website_about_meta_description", ""),
            ]
        )
    )
    if not description_text:
        return False

    synthetic_hits = keyword_hits(description_text, SYNTHETIC_DATA_COMPETITOR_KEYWORDS)
    ai_hits = keyword_hits(description_text, AI_COMPETITOR_KEYWORDS)
    return bool(synthetic_hits and ai_hits)


def score_row(row: Dict[str, str], include_company_website: bool = True) -> Dict[str, str]:
    text_parts = [
        row.get("company_name", ""),
        row.get("website", ""),
        row.get("profile_meta_description", ""),
        row.get("profile_title", ""),
        row.get("profile_headings", ""),
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
    full_text = normalize_space(" ".join(text_parts))
    hit_map: Dict[str, List[str]] = {}
    score = 0
    matched_keywords: List[str] = []

    for bucket, spec in POSITIVE_KEYWORDS.items():
        hits = keyword_hits(full_text, spec["keywords"])
        hit_map[bucket] = hits
        bucket_score = min(len(hits) * spec["weight"], spec["cap"])
        score += bucket_score
        matched_keywords.extend(hits)

    # Lift the sectors the user explicitly wants to prioritize so they surface in the shortlist.
    if hit_map["specialty_glass"]:
        score += 6
    if hit_map["roofing_building"]:
        score += 4

    negative_hits = keyword_hits(full_text, NEGATIVE_KEYWORDS)
    score -= min(len(negative_hits) * 6, 18)

    country_priority_bucket, country_boost = get_country_priority(row.get("country", ""))
    score += country_boost

    if "hall 17" in row.get("booth", "").lower() or "hall 26" in row.get("booth", "").lower():
        score += 2

    manufacturing_confirmation_hits = keyword_hits(full_text, MANUFACTURING_CONFIRMATION_KEYWORDS)
    category, subcategory = derive_category(hit_map, bool(manufacturing_confirmation_hits))

    if country_priority_bucket == "excluded_china":
        row["score"] = str(score)
        row["priority_band"] = ""
        row["category"] = "excluded"
        row["subcategory"] = "excluded_country"
        row["matched_keywords"] = ", ".join(sorted(dict.fromkeys(matched_keywords)))
        row["negative_keywords"] = ", ".join(sorted(dict.fromkeys(negative_hits)))
        row["country_priority_bucket"] = country_priority_bucket
        row["country_priority_boost"] = str(country_boost)
        row["outreach_angle"] = "Excluded from outreach because the exhibitor is based in China."
        return row

    manual_reason = manual_exclusion_reason(row)
    if manual_reason:
        category = "excluded"
        subcategory = "manual_curation"
        negative_hits = sorted(dict.fromkeys(negative_hits + ["manual exclusion"]))

    if should_exclude_partner_competitor(row, category):
        category = "excluded"
        subcategory = "ai_synthetic_data_competitor"
        negative_hits = sorted(
            dict.fromkeys(
                negative_hits
                + ["synthetic data competitor", "ai competitor"]
            )
        )

    if negative_hits and score < PRIORITY_THRESHOLDS["C"]:
        category = "excluded"
        subcategory = "negative_signal"

    priority = ""
    for band, threshold in PRIORITY_THRESHOLDS.items():
        if score >= threshold:
            priority = band
            break

    if not priority and score >= PRIORITY_THRESHOLDS["C"]:
        priority = "C"

    row["score"] = str(score)
    row["priority_band"] = priority
    row["category"] = category
    row["subcategory"] = subcategory
    row["matched_keywords"] = ", ".join(sorted(dict.fromkeys(matched_keywords)))
    row["negative_keywords"] = ", ".join(sorted(dict.fromkeys(negative_hits)))
    row["country_priority_bucket"] = country_priority_bucket
    row["country_priority_boost"] = str(country_boost)
    if subcategory == "manual_curation":
        row["outreach_angle"] = manual_reason
    elif subcategory == "ai_synthetic_data_competitor":
        row["outreach_angle"] = (
            "Excluded from partner outreach because the exhibitor describes both synthetic data and AI,"
            " making them more likely to be a direct competitor than a partner."
        )
    elif (
        category == "review_target"
        and (
            hit_map["flat_product"]
            or hit_map["metals"]
            or hit_map["composites_textiles"]
            or hit_map["furniture_casework"]
            or hit_map["specialty_glass"]
            or hit_map["roofing_building"]
        )
        and not manufacturing_confirmation_hits
    ):
        row["outreach_angle"] = (
            "Manual review recommended because product keywords matched, but the description does not clearly say"
            " the exhibitor is a manufacturer or production company."
        )
    else:
        row["outreach_angle"] = build_outreach_angle(category, subcategory)
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
    with path.open("w", newline="", encoding="utf-8") as handle:
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
    configure_event(args.event_slug, args.event_name, args.export_url)
    ensure_dirs()
    session = make_session()

    print(f"Building event CSVs in {EVENT_DIR}")
    print("Downloading official Hannover Messe exhibitor export...")
    raw_csv = download_export(session)
    rows = parse_export(raw_csv)
    print(f"Parsed {len(rows)} exhibitors from the official export.")

    rows = enrich_profiles(rows)
    rows = enrich_company_websites(rows)

    scored_rows = [score_row(row) for row in rows]
    scored_rows = sort_rows(scored_rows)

    write_csv(ENRICHED_PATH, scored_rows)

    relevant_rows = [
        row
        for row in scored_rows
        if row.get("category") in {"manufacturer_target", "partner_target", "review_target"}
        and int(row.get("score", "0")) >= PRIORITY_THRESHOLDS["C"]
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

    write_csv(RELEVANT_PATH, relevant_rows)
    write_csv(MANUFACTURERS_PATH, manufacturer_rows)
    write_csv(PARTNERS_PATH, partner_rows)
    write_csv(PRIORITY_PATH, relevant_rows[:30])

    print(f"Wrote {ENRICHED_PATH}")
    print(f"Wrote {RELEVANT_PATH} ({len(relevant_rows)} rows)")
    print(f"Wrote {MANUFACTURERS_PATH} ({len(manufacturer_rows)} rows)")
    print(f"Wrote {PARTNERS_PATH} ({len(partner_rows)} rows)")
    print(f"Wrote {PRIORITY_PATH} ({min(len(relevant_rows), 30)} rows)")


if __name__ == "__main__":
    main()
