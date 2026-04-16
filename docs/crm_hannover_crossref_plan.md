# CRM x Hannover Messe Cross-Reference Plan

## Goal

Find companies already present in Zetamotion's CRM that are also exhibiting at HANNOVER MESSE 2026, so the team can restart conversations and schedule in-person chats.

## Inputs

- CRM accounts: `docs/existing-crm-companies/accounts.csv`
- CRM leads: `docs/existing-crm-companies/leads.csv`
- Full Hannover exhibitor master: `data/hannover_exhibitors_enriched.csv`

## Matching Strategy

Use a conservative matching order to avoid false positives.

1. Aggregate duplicate exhibitor rows first.
   - Hannover has multiple rows for some exhibitors because they appear in multiple halls or contexts.
   - Merge these into a single exhibitor record with combined booth locations.

2. Normalize company names.
   - Lowercase.
   - Remove punctuation.
   - Strip common company suffixes such as `GmbH`, `Ltd`, `Inc`, `Co`, `AG`, etc.
   - Treat `&` as `and`.

3. Normalize website domains.
   - Extract hostname.
   - Remove `www.`.

4. Apply match rules in this order:
   - `high`: exact normalized website domain
   - `high`: exact normalized company name
   - `medium`: same brand / parent-family name with strong token match, typically when the CRM record is a parent brand and Hannover lists a specific subsidiary or division

5. Keep only `high` and `medium` matches in the final output.
   - Include `match_confidence` and `match_reason` in the CSV so the team can judge borderline cases quickly.

## Expected Output

- `output/crm_hannovermesse_matches.csv`

Recommended columns:

- CRM source (`accounts` or `leads`)
- CRM company name
- CRM list / priority / owner / type / industry / product / website
- Exhibitor company name
- Exhibitor website
- Exhibitor booth(s)
- Exhibitor profile URL
- Exhibitor score / category from the Hannover enrichment pass
- Match confidence
- Match reason

## Practical Use

Use `high` confidence matches immediately for outreach.

Use `medium` confidence matches when:

- the CRM record is clearly the same corporate family as the exhibitor
- or the CRM record is a broader company entry and Hannover lists a specific operating division

For these medium-confidence rows, the outreach can be framed as:

- "We noticed your team is exhibiting at Hannover Messe..."
- and then refer to the specific booth/division listed in the exhibitor data.
