# Fiber Scout

## Project Goal

Build a prospecting research agent that takes a spreadsheet of commercial
property addresses and researches the businesses at each address. For each
business, the agent tries to find its:

- Website
- Main phone number
- General email address
- Decision-maker, if findable
- Industry
- Estimated employee count
- Likely internet needs, summarized in a short profile

The agent then produces a fit score for selling business fiber internet.

## Later Phases

Buy-signal scanning and outreach drafts are planned for later phases and are
not part of the current scope.

## Input Data

The initial input is a CSV. Google Sheets support may be added later.

### Existing Input Columns

The exact input columns are **to be confirmed**. Possible examples include
`address`, `city`, `zip`, `latitude`, `longitude`, and `property_type`; these
are not yet a confirmed schema.

### Agent-Owned Columns

The agent may fill these columns:

- `business_name`
- `owner_or_manager`
- `website`
- `phone`
- `email`
- `contact_name`
- `industry`
- `est_employees`
- `needs_profile`
- `fit_score`
- `source_urls`
- `confidence`
- `status`
- `notes`

The agent must never modify the existing input columns.

## Development Stages

Complete one stage at a time, then stop and wait before beginning the next.

1. **Setup:** Create the folder structure, virtual environment, requirements,
   `.env.example`, and `.gitignore`. Initialize Git only if the project is not
   already a Git repository. Explain what each piece is for.
2. **Playbook files:** First ask questions about the business. Then help draft
   `icp.md`, `scoring-rubric.md` (a 0-100 score with explicit weights for
   need, feasibility, and reachability), and `research-checklist.md`. Explain
   why these are Markdown files rather than hardcoded.
3. **Data layer:** Implement functions to read the CSV, select rows that still
   need work, and write results to agent-owned columns with status updates.
   Explain idempotency and why input columns are protected.
4. **Tools:** Implement each tool one at a time, with its own test script:
   (a) Places lookup near latitude/longitude, (b) website fetching and text
   extraction, (c) optional Florida Sunbiz lookup, and (d) contact enrichment
   via Hunter, Apollo, or another provider. Explain what makes a good tool
   definition.
5. **Agent loop:** Use tool calling with Anthropic, OpenAI, or Azure OpenAI.
   Load the Markdown playbook as instructions and require structured JSON
   output validated against a schema. Explain the agent loop, tool calling,
   and structured output; show how to read a run's trace.
6. **Scoring:** Implement the rubric in code. Explain why the math belongs in
   code rather than the LLM.
7. **Evaluation:** Produce a review file for a 20-row hand check, with columns
   for correct company, working phone, and valid email, plus a script to total
   the percentages. Explain why evaluation comes before scaling.
8. **Improvement:** Use the evaluation results to identify and fix the weakest
   step.

## Project Structure

- `src/fiber_scout/` contains the application package.
- `playbooks/` contains editable research and scoring guidance in Markdown.
- `tests/` contains automated tests.
- `data/input/` is for local source CSVs; Git ignores its contents.
- `data/output/` is for generated files; Git ignores its contents.
- `logs/` is for local run logs; Git ignores its contents.
- `requirements.txt` lists third-party Python packages.
- `.env.example` documents how to start a local `.env` file without storing
  credentials in Git. Keep actual secrets in `.env`.

### Sunbiz corporate data lookup

The optional Sunbiz lookup searches locally downloaded corporate data files;
it does not require an API key or make requests to the search website. Obtain
the quarterly corporate data archive from the Florida Division of
Corporations' [data downloads page](https://dos.fl.gov/sunbiz/other-services/data-downloads/quarterly-data/),
then pass the ZIP archive or extracted fixed-width `.txt` files to
`fiber_scout.sunbiz.search_sunbiz`. Quarterly corporate archives are very
large. The parser streams their text records and follows the official
[corporate file definitions](https://dos.sunbiz.org/data-definitions/cor.html).

### Hunter contact enrichment

Set `HUNTER_API_KEY` in `.env` and call
`fiber_scout.hunter.search_domain_contacts` with a business domain. This tool
uses Hunter's [Domain Search API](https://hunter.io/api-documentation/v2#domain-search),
which may consume provider credits. It returns provider confidence scores and
source URLs without treating the scores as verified facts. Automated tests
mock the API response and do not make billable requests.

## Hard Rules

1. **Do not invent data.** If a fact is not found in a source, record
   `not found`. A blank is better than an incorrect phone number or email.
2. **Source key facts.** Every key fact must include a source URL and a
   confidence level: `high`, `medium`, or `low`.
3. **Handle multi-tenant buildings.** Collect all businesses found at an
   address; do not guess which single business is the intended one.
4. **Protect secrets.** Keep API keys in a `.env` file, never in code or Git.
5. **Calculate scores in Python.** The LLM may provide judgment inputs, such
   as industry, size estimate, and reasoning. Python code must compute the
   fit score from the rubric weights.
6. **Bound each run.** Support `--dry-run`, `--limit N` (starting with 20
   rows), a cap on agent steps per row, and a per-run log of cost and token
   usage.
7. **Make reruns idempotent.** Skip rows whose status is `done`.
