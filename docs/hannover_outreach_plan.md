# Hannover Messe Outreach Plan

## Objective

Build a targeted Hannover Messe outreach list for Zetamotion ahead of the fair week of 20-24 April 2026. The goal is to identify exhibitors worth meeting in person for:

- Inline or stand-alone defect inspection deployments.
- Component verification on production lines.
- Flat-product inspection use cases.
- Partnerships with manual inspection hardware builders, semi-automated inspection machine builders, metrology vendors, and AI inspection firms.

## Zetamotion Fit

Working assumptions from Zetamotion public pages:

- Zetamotion positions around AI quality inspection for manufacturing.
- Synthetic data is a core wedge when defects are rare, expensive to label, or product variation is high.
- Existing fit is strongest where product surfaces or repeated geometries are visually inspectable and integration can happen with existing line hardware or dedicated stations.
- Public pages explicitly point to composites and industrial vision, and the product pages point to surface-heavy materials such as laminated glass.

Useful source pages:

- https://zetamotion.com/data-curation-and-ai/
- https://zetamotion.com/succeeding-with-synthetic-data-in-industrial-vision-applications/
- https://zetamotion.com/zetamotion-at-jec-forum-dach-2025-showcasing-spectron-ai-for-composite-quality-inspection/
- https://zetamotion.com/product/laminated-glass/

## Hannover Messe Site Findings

### Exhibitor data source

The public reactive search page is useful for validation but awkward for bulk extraction because pagination is POST-backed and stateful:

- https://www.hannovermesse.de/en/search/?category=ep

I validated this with Playwright CLI. Pagination changes the visible results, but the page uses opaque POST endpoints and does not expose clean page URLs.

The better source is the exhibitor short index and its official CSV export:

- Short index: https://www.hannovermesse.de/en/expo/exhibitor-short-index/index-2
- Official exhibitor CSV export: https://www.hannovermesse.de/en/application/exhibitor-index/csvExport?rt=ex&sort=AZ

The CSV export gives the stable master list:

- hit type
- exhibitor name
- country
- city / region
- company website
- booth
- exhibitor presentation URL

### Relevant attendee and market context

Useful Hannover Messe pages for targeting context:

- Visitor hub: https://www.hannovermesse.de/en/for-visitors/
- 2026 manufacturing / startup / research clustering: https://www.hannovermesse.de/en/press/press-releases/hannover-messe/hannover-messe-where-research-and-manufacturing-meet-2
- Industrial Supply / lightweight / smart materials / surface finishing visitor context: https://www.hannovermesse.de/en/press/press-releases/hannover-messe/lightweight-construction-smart-materials-and-surface-finishing-soluti

Important takeaways from Hannover Messe pages:

- The exhibitor directory currently shows 2,861 exhibitors on the official search page.
- The search page groups 1,606 entries under `Industrial Supply & Engineering Solutions`.
- The search page groups 1,083 entries under `Manufacturing industry/production` and 102 under `Construction/construction industry`.
- Hannover Messe describes visitors as spanning manufacturing, automation, energy, and research.
- Their Industrial Supply coverage explicitly calls out lightweight construction, smart materials, surface finishing, parts, components, semi-finished products, metals, aluminum, composites, and measurement / testing / analysis equipment.

## Targeting Approach

### Primary target buckets

1. Manufacturers of flat or surface-driven products.
2. Metals and sheet / strip / plate / coil producers or processors.
3. Composites, fiber, textile, fabric, nonwoven, laminate, and surface-material producers.
4. Roofing and adjacent building-material exhibitors where surface inspection or component verification could fit.

### Secondary target buckets

1. Inspection hardware and metrology vendors.
2. Machine builders for manual or semi-automated inspection stations.
3. Vision, QA, testing, or measurement integrators.
4. AI inspection, defect detection, computer vision, or synthetic-data adjacent partners.

### Exclusions or down-ranking

- Pure consultants.
- ERP / cloud / general software vendors with no inspection angle.
- Government, chambers, associations, universities, media, and investment offices.
- Generic digital transformation vendors without a manufacturing QA hook.

## Extraction Method

1. Download the official exhibitor CSV export as the master source.
2. Fetch each exhibitor presentation page from the official Hannover Messe profile URL.
3. Pull the profile meta description from each profile page as the enrichment text.
4. Score exhibitors using keyword groups tied to Zetamotion's ICP:
   - flat products
   - metals / sheet metal / steel / aluminum
   - composites / fibers / textiles / nonwovens
   - roofing / building envelopes / membranes / panels
   - inspection / metrology / testing / measurement
   - AI inspection / defect detection / computer vision / quality control
5. Down-rank exhibitors with negative signals such as consulting-only, association, ministry, investment, or research-only.
6. Produce CSV outputs for:
   - all scored relevant exhibitors
   - manufacturer-first targets
   - partner / hardware / AI targets

## Output Files

Expected files in this repo:

- `data/hannover_exhibitors_raw.csv`
- `data/hannover_exhibitors_enriched.csv`
- `output/zetamotion_relevant_companies.csv`
- `output/zetamotion_manufacturer_targets.csv`
- `output/zetamotion_partner_targets.csv`

## Outreach Strategy

Use the final CSVs in two waves.

### Wave 1: high-conviction manufacturers

Prioritize exhibitors where the profile strongly indicates:

- sheet metal or repeatable metal parts
- composite or textile surfaces
- laminates, panels, membranes, coated products, or similar flat goods
- strong need for defect detection, appearance inspection, or component verification

Message angle:

- Zetamotion will be on-site next week.
- We help manufacturers deploy visual QA faster using synthetic data and line-side integration.
- We are especially interested in flat products, surface defects, and component verification.
- Ask for a 15-minute conversation at their booth.

### Wave 2: partners and integrators

Prioritize:

- machine vision suppliers
- measurement and test equipment providers
- station builders and automation integrators
- AI inspection vendors that may need synthetic data or deployment support

Message angle:

- Explore integration or channel partnership rather than only end-customer deployment.

## Questions To Tighten The List

These are useful but not blocking:

- Which geographies matter most for follow-up after the event?
- Does the CEO want only booth meetings with exhibitors, or also attendee-side partner meetings?
- Are there industries to avoid entirely beyond the current focus areas?
