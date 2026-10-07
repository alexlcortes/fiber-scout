# Business Research Checklist (Draft)

## Before researching

- Use the supplied CSV address as-is. Do not modify any input column.
- Research only Florida addresses provided in the input.
- The owner has confirmed that supplied addresses are serviceable. Treat this
  as user-provided information, not as independently verified coverage.
- Keep secrets in `.env`; never copy credentials into source files, output
  data, or logs.

## Find businesses at the address

- Search for businesses operating at the exact supplied address.
- Check whether the address is a multi-tenant property.
- For a multi-tenant property, list every business found; do not select or
  guess a single intended tenant.
- For each business, capture enough detail to distinguish it from other
  businesses at the same address.
- If the business has multiple locations, treat each supplied address as its
  own prospect/account.

## Research each business

Try to find:

- Business name
- Owner or manager
- Website
- Main phone number
- General email address
- Contact name and relevant decision-maker role, if findable
- Industry
- Estimated employee count
- Evidence-based profile of likely internet needs
- Evidence relevant to need, feasibility, and reachability for scoring

For decision-makers, consider a pastor at a church; a tenant decision-maker
and property/building manager or landlord at an MTU; IT/procurement or a
relevant municipal role at a government prospect; and owner, IT, operations,
or procurement roles at other businesses. These are roles to investigate,
not assumed identities.

## Evidence rules

- Never invent or infer a phone number, email, contact, employee count, or
  other business fact.
- If a fact cannot be found, write `not found` rather than guessing.
- Record a source URL and confidence (`high`, `medium`, or `low`) for every
  key researched fact.
- Prefer sources that directly support the fact. Do not treat a search-result
  snippet as confirmation when the underlying source can be checked.
- Keep the source attached to the fact it supports; do not use one URL as
  blanket evidence for unrelated claims.
- Do not claim that a business needs a particular speed or static IP unless
  evidence supports that assessment.
- Separate observed facts from analysis and recommendations in the
  `needs_profile` and notes.

## Before completing a business

- Verify that the business and its address match the supplied location.
- Check for duplicate or conflicting business details and retain uncertainty
  instead of silently choosing a result.
- Confirm that each populated key fact has its source URL and confidence.
- Set missing facts to `not found`.
- Record the fit-score inputs and evidence; Python will compute the weighted
  score from the rubric.
- Update status according to the processing outcome. Mark a row `done` only
  when research for that row is complete; do not mark incomplete or failed
  work as `done`.
- Preserve all original input columns exactly.
