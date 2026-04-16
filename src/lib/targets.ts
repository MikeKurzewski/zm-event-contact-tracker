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

function buildBaseId(dataset: DatasetKey, row: Record<string, string>) {
  const companyName = row.company_name || row.hannover_company_name || row.crm_company_name || "";
  const booth = row.booth || row.hannover_booths || "na";
  return `${dataset}-${slugify(companyName)}-${slugify(booth)}`;
}

function normalizeTarget(dataset: DatasetKey, row: Record<string, string>): ScoutTarget {
  const companyName = row.company_name || row.hannover_company_name || row.crm_company_name || "";
  const website = row.website || row.hannover_website || "";
  const overview = pickOverview(row);

  return {
    id: buildBaseId(dataset, row),
    dataset,
    companyName,
    country: row.country || row.hannover_country || "",
    booth: row.booth || row.hannover_booths || "",
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

async function readCsv(fileName: string) {
  const filePath = path.join(process.cwd(), "output", fileName);
  const content = await fs.readFile(filePath, "utf-8");
  return parse(content, {
    columns: true,
    skip_empty_lines: true
  }) as Record<string, string>[];
}

export async function loadDatasets(): Promise<DatasetSummary[]> {
  const entries = await Promise.all(
    Object.entries(DATASET_FILES).map(async ([key, meta]) => {
      const rows = await readCsv(meta.file);
      const seenIds = new Map<string, number>();
      const targets = rows.map((row) => {
        const target = normalizeTarget(key as DatasetKey, row);
        const occurrence = (seenIds.get(target.id) ?? 0) + 1;
        seenIds.set(target.id, occurrence);

        if (occurrence === 1) {
          return target;
        }

        return {
          ...target,
          // Some CSVs contain repeated exhibitor+booth combinations.
          id: `${target.id}-${occurrence}`
        };
      });
      return {
        key: key as DatasetKey,
        label: meta.label,
        description: meta.description,
        targets
      };
    })
  );

  return entries;
}
