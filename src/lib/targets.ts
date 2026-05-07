import fs from "node:fs/promises";
import path from "node:path";

import { parse } from "csv-parse/sync";

import { compactUrl, slugify } from "@/lib/utils";

export type DatasetKey =
  | "priority"
  | "manufacturers"
  | "partners"
  | "relevant"
  | "crm";

export type ScoutTarget = {
  id: string;
  dataset: DatasetKey;
  companyName: string;
  country: string;
  booth: string;
  hallNumbers: string[];
  standNumbers: string[];
  score: number | null;
  targetType: string;
  category: string;
  overview: string;
  website: string;
  websiteLabel: string;
  profileUrl: string;
  countryPriority: string;
  outreachAngle: string;
  confidence: string;
  crmSource: string;
  crmCompanyName: string;
  crmListName: string;
  crmPriority: string;
  crmLeadSource: string;
  crmIndustry: string;
  crmProduct: string;
  crmCountry: string;
  crmWebsite: string;
  crmCardUrl: string;
  crmLastActivityDate: string;
  companySiteAbout: string;
  companySiteHome: string;
  officialOverview: string;
  matchedKeywords: string[];
  negativeKeywords: string[];
  matchReason: string;
};

export type DatasetSummary = {
  key: DatasetKey;
  label: string;
  description: string;
  targets: ScoutTarget[];
};

export type ScoutEvent = {
  slug: string;
  name: string;
  description: string;
  datasets: DatasetSummary[];
  totalTargets: number;
  updatedAt: string;
};

type EventManifest = {
  name?: string;
  description?: string;
};

const EVENTS_DIR = "events";
const DEFAULT_EVENT_SLUG = "hannover-messe";

const DATASET_FILES: Record<
  DatasetKey,
  { file: string; label: string; description: string }
> = {
  priority: {
    file: "zetamotion_priority_meeting_targets.csv",
    label: "Priority Meetings",
    description: "Top-ranked targets for immediate booth outreach."
  },
  manufacturers: {
    file: "zetamotion_manufacturer_targets.csv",
    label: "Manufacturers",
    description: "Likely end-customer manufacturers for direct inspection conversations."
  },
  partners: {
    file: "zetamotion_partner_targets.csv",
    label: "Partners",
    description: "Integrators, metrology vendors, AI inspection companies, and hardware partners."
  },
  relevant: {
    file: "zetamotion_relevant_companies.csv",
    label: "All Relevant",
    description: "Broad shortlist of scored Hannover exhibitors worth considering."
  },
  crm: {
    file: "crm_hannovermesse_accounts_matches.csv",
    label: "CRM Matches",
    description: "Existing CRM accounts that also appear in the Hannover exhibitor data."
  }
};

function humanizeSlug(value: string) {
  return value
    .split("-")
    .filter(Boolean)
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join(" ");
}

function eventDir(eventSlug: string) {
  return path.join(process.cwd(), EVENTS_DIR, eventSlug);
}

function eventOutputDir(eventSlug: string) {
  return path.join(eventDir(eventSlug), "output");
}

async function pathExists(filePath: string) {
  try {
    await fs.access(filePath);
    return true;
  } catch {
    return false;
  }
}

async function readEventManifest(eventSlug: string): Promise<EventManifest> {
  const manifestPath = path.join(eventDir(eventSlug), "event.json");
  if (!(await pathExists(manifestPath))) {
    return {};
  }

  try {
    return JSON.parse(await fs.readFile(manifestPath, "utf-8")) as EventManifest;
  } catch {
    return {};
  }
}

async function discoverEventSlugs() {
  const eventsPath = path.join(process.cwd(), EVENTS_DIR);
  if (!(await pathExists(eventsPath))) {
    return [];
  }

  const entries = await fs.readdir(eventsPath, { withFileTypes: true });
  return entries
    .filter((entry) => entry.isDirectory())
    .map((entry) => entry.name)
    .sort((left, right) => left.localeCompare(right, undefined, { sensitivity: "base" }));
}

function asArray(value: string | undefined) {
  return (value ?? "")
    .split(",")
    .map((part) => part.trim())
    .filter(Boolean);
}

function pickOverview(row: Record<string, string>) {
  return (
    row.website_home_meta_description ||
    row.website_about_meta_description ||
    row.profile_meta_description ||
    row.hannover_profile_meta_description ||
    row.website_home_headings ||
    row.website_about_headings ||
    ""
  );
}

type BoothEntry = {
  raw: string;
  hallNumber: string;
  standNumber: string;
};

function uniqueStrings(values: Array<string | undefined>) {
  return [...new Set(values.map((value) => value?.trim()).filter(Boolean) as string[])];
}

function compareNaturally(left: string, right: string) {
  return left.localeCompare(right, undefined, {
    numeric: true,
    sensitivity: "base"
  });
}

function parseBoothEntries(value: string) {
  return value
    .split(/\s+\|\s+|\n+/)
    .map((part) => part.trim())
    .filter(Boolean)
    .map((raw) => {
      const hallNumber = raw.match(/hall\s+(\d+)/i)?.[1] ?? "";
      const standNumber = raw.match(/stand\s+([^,|]+)/i)?.[1]?.trim() ?? "";

      return {
        raw,
        hallNumber,
        standNumber
      } satisfies BoothEntry;
    });
}

function collectBoothEntries(values: string[]) {
  return [...new Map(values.flatMap(parseBoothEntries).map((entry) => [entry.raw.toLowerCase(), entry])).values()].sort(
    (left, right) => {
      if (left.hallNumber && right.hallNumber && left.hallNumber !== right.hallNumber) {
        return compareNaturally(left.hallNumber, right.hallNumber);
      }
      if (left.standNumber && right.standNumber && left.standNumber !== right.standNumber) {
        return compareNaturally(left.standNumber, right.standNumber);
      }
      return compareNaturally(left.raw, right.raw);
    }
  );
}

function pickLongestText(values: Array<string | undefined>) {
  return uniqueStrings(values).sort((left, right) => right.length - left.length)[0] ?? "";
}

function joinDistinct(values: Array<string | undefined>, separator = " | ") {
  return uniqueStrings(values).join(separator);
}

function pickFirst(values: Array<string | undefined>) {
  return uniqueStrings(values)[0] ?? "";
}

function pickConfidence(values: Array<string | undefined>) {
  const ranking = new Map([
    ["high", 3],
    ["medium", 2],
    ["low", 1]
  ]);

  return uniqueStrings(values).sort((left, right) => (ranking.get(right) ?? 0) - (ranking.get(left) ?? 0))[0] ?? "";
}

function buildBaseId(dataset: DatasetKey, row: Record<string, string>) {
  const companyName = row.company_name || row.hannover_company_name || row.crm_company_name || "";
  return `${dataset}-${slugify(companyName) || "target"}`;
}

function normalizeTarget(dataset: DatasetKey, row: Record<string, string>): ScoutTarget {
  const companyName = row.company_name || row.hannover_company_name || row.crm_company_name || "";
  const website = row.website || row.hannover_website || "";
  const overview = pickOverview(row);
  const booth = row.booth || row.hannover_booths || "";
  const boothEntries = collectBoothEntries([booth]);

  return {
    id: buildBaseId(dataset, row),
    dataset,
    companyName,
    country: row.country || row.hannover_country || "",
    booth,
    hallNumbers: uniqueStrings(boothEntries.map((entry) => entry.hallNumber)).sort(compareNaturally),
    standNumbers: uniqueStrings(boothEntries.map((entry) => entry.standNumber)).sort(compareNaturally),
    score: row.score || row.hannover_score ? Number(row.score || row.hannover_score) : null,
    targetType: row.subcategory || row.hannover_subcategory || row.match_reason || "general",
    category: row.category || row.hannover_category || "",
    overview,
    website,
    websiteLabel: compactUrl(website),
    profileUrl: row.profile_url || row.hannover_profile_url || "",
    countryPriority: row.country_priority_bucket || "",
    outreachAngle: row.outreach_angle || "",
    confidence: row.match_confidence || "",
    crmSource: row.crm_source || "",
    crmCompanyName: row.crm_company_name || "",
    crmListName: row.crm_list_name || "",
    crmPriority: row.crm_priority || "",
    crmLeadSource: row.crm_lead_source || "",
    crmIndustry: row.crm_industry || "",
    crmProduct: row.crm_product || "",
    crmCountry: row.crm_country || "",
    crmWebsite: row.crm_website || "",
    crmCardUrl: row.crm_card_url || "",
    crmLastActivityDate: row.crm_last_activity_date || "",
    companySiteAbout: row.website_about_meta_description || "",
    companySiteHome: row.website_home_meta_description || "",
    officialOverview: row.profile_meta_description || row.hannover_profile_meta_description || "",
    matchedKeywords: asArray(row.matched_keywords),
    negativeKeywords: asArray(row.negative_keywords),
    matchReason: row.match_reason || ""
  };
}

function mergeTargets(dataset: DatasetKey, targets: ScoutTarget[]) {
  const grouped = new Map<string, ScoutTarget[]>();

  for (const target of targets) {
    const key = slugify(target.companyName) || target.id;
    const group = grouped.get(key) ?? [];
    group.push(target);
    grouped.set(key, group);
  }

  return [...grouped.entries()].map(([key, group]) => {
    const boothEntries = collectBoothEntries(group.map((target) => target.booth));
    const scoreValues = group
      .map((target) => target.score)
      .filter((score): score is number => score !== null);
    const website = pickFirst(group.map((target) => target.website));

    return {
      id: `${dataset}-${key}`,
      dataset,
      companyName: pickFirst(group.map((target) => target.companyName)),
      country: pickFirst(group.map((target) => target.country)),
      booth: boothEntries.map((entry) => entry.raw).join(" | "),
      hallNumbers: uniqueStrings(boothEntries.map((entry) => entry.hallNumber)).sort(compareNaturally),
      standNumbers: uniqueStrings(boothEntries.map((entry) => entry.standNumber)).sort(compareNaturally),
      score: scoreValues.length ? Math.max(...scoreValues) : null,
      targetType: joinDistinct(group.map((target) => target.targetType)),
      category: joinDistinct(group.map((target) => target.category)),
      overview: pickLongestText(group.map((target) => target.overview)),
      website,
      websiteLabel: compactUrl(website),
      profileUrl: pickFirst(group.map((target) => target.profileUrl)),
      countryPriority: pickFirst(group.map((target) => target.countryPriority)),
      outreachAngle: joinDistinct(group.map((target) => target.outreachAngle)),
      confidence: pickConfidence(group.map((target) => target.confidence)),
      crmSource: joinDistinct(group.map((target) => target.crmSource)),
      crmCompanyName: joinDistinct(group.map((target) => target.crmCompanyName)),
      crmListName: joinDistinct(group.map((target) => target.crmListName)),
      crmPriority: joinDistinct(group.map((target) => target.crmPriority)),
      crmLeadSource: joinDistinct(group.map((target) => target.crmLeadSource)),
      crmIndustry: joinDistinct(group.map((target) => target.crmIndustry)),
      crmProduct: joinDistinct(group.map((target) => target.crmProduct)),
      crmCountry: joinDistinct(group.map((target) => target.crmCountry)),
      crmWebsite: joinDistinct(group.map((target) => target.crmWebsite)),
      crmCardUrl: pickFirst(group.map((target) => target.crmCardUrl)),
      crmLastActivityDate: pickFirst(group.map((target) => target.crmLastActivityDate)),
      companySiteAbout: pickLongestText(group.map((target) => target.companySiteAbout)),
      companySiteHome: pickLongestText(group.map((target) => target.companySiteHome)),
      officialOverview: pickLongestText(group.map((target) => target.officialOverview)),
      matchedKeywords: uniqueStrings(group.flatMap((target) => target.matchedKeywords)).sort(compareNaturally),
      negativeKeywords: uniqueStrings(group.flatMap((target) => target.negativeKeywords)).sort(compareNaturally),
      matchReason: joinDistinct(group.map((target) => target.matchReason))
    } satisfies ScoutTarget;
  });
}

async function readCsv(eventSlug: string, fileName: string) {
  const filePath = path.join(eventOutputDir(eventSlug), fileName);
  if (!(await pathExists(filePath))) {
    return [];
  }

  const content = await fs.readFile(filePath, "utf-8");
  return parse(content, {
    columns: true,
    skip_empty_lines: true
  }) as Record<string, string>[];
}

export async function loadDatasets(eventSlug = DEFAULT_EVENT_SLUG): Promise<DatasetSummary[]> {
  const entries = await Promise.all(
    Object.entries(DATASET_FILES).map(async ([key, meta]) => {
      const rows = await readCsv(eventSlug, meta.file);
      if (!rows.length) {
        return null;
      }

      const normalizedTargets = rows.map((row) => normalizeTarget(key as DatasetKey, row));
      const targets = mergeTargets(key as DatasetKey, normalizedTargets);

      return {
        key: key as DatasetKey,
        label: meta.label,
        description: meta.description,
        targets
      };
    })
  );

  return entries.filter((entry): entry is DatasetSummary => entry !== null);
}

export async function loadEvent(eventSlug: string): Promise<ScoutEvent | null> {
  const slugs = await discoverEventSlugs();
  if (!slugs.includes(eventSlug)) {
    return null;
  }

  const manifest = await readEventManifest(eventSlug);
  const datasets = await loadDatasets(eventSlug);
  const outputPath = eventOutputDir(eventSlug);
  let updatedAt = "";

  if (await pathExists(outputPath)) {
    const outputEntries = await fs.readdir(outputPath);
    const stats = await Promise.all(
      outputEntries
        .filter((fileName) => fileName.endsWith(".csv"))
        .map((fileName) => fs.stat(path.join(outputPath, fileName)))
    );
    const latestMtime = Math.max(0, ...stats.map((stat) => stat.mtimeMs));
    updatedAt = latestMtime ? new Date(latestMtime).toISOString() : "";
  }

  return {
    slug: eventSlug,
    name: manifest.name || humanizeSlug(eventSlug),
    description: manifest.description || "",
    datasets,
    totalTargets: datasets.reduce((total, dataset) => total + dataset.targets.length, 0),
    updatedAt
  };
}

export async function loadEvents(): Promise<ScoutEvent[]> {
  const slugs = await discoverEventSlugs();
  const events = await Promise.all(slugs.map((slug) => loadEvent(slug)));
  return events.filter((event): event is ScoutEvent => event !== null);
}

export async function loadDefaultEvent(): Promise<ScoutEvent | null> {
  return loadEvent(DEFAULT_EVENT_SLUG);
}
