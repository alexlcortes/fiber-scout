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

## Using what's implemented

The current data and research tools are Python functions, not a complete
prospecting agent yet. Run commands from the repository root. To run the
offline test suite:

```bash
PYTHONPATH=src ./.venv/bin/python -m unittest discover -s tests -v
```

### CSV data layer

`fiber_scout.data.read_csv(path)` reads CSV rows,
`select_pending_rows(rows, limit=20)` returns the zero-based indexes of rows
not marked `done`, and `write_results(csv_path, updates, output_path=...)`
writes updates only to agent-owned columns. Each update must include a
non-empty `status`. Supplying `output_path` writes to a separate file and
leaves the source file unchanged; without it, the source CSV is updated.

### Places nearby search

`fiber_scout.places.search_nearby(latitude, longitude, radius_meters=...)`
searches for candidate places near coordinates. Set `GOOGLE_MAPS_API_KEY` in
the environment before calling it. If you do not already have a `.env` file,
create one from `.env.example` with `cp .env.example .env`, then add your key.
For a local `.env` file in macOS/Linux, load its values into the current shell
with:

```bash
set -a
source .env
set +a
```

Places requests use Google Maps Platform and may be billable. A result is a
discovery lead, not independently verified proof of a business at an address.

### Website fetch and text extraction

`fiber_scout.website.fetch_website(url)` retrieves a public HTML page and
returns its title, readable text, final URL, and whether the response was
truncated. `extract_html_text(html)` extracts title and visible text from an
HTML string without making a network request. The tool accepts standard
HTTP(S) ports only and limits response size and request time.

### Optional Sunbiz corporate data lookup

`fiber_scout.sunbiz.search_sunbiz(name, data_files, limit=20)` searches
locally downloaded corporate data files. It does not need an API key or make
requests to the search website. Obtain the quarterly corporate data archive
from the Florida Division of Corporations'
[data downloads page](https://dos.fl.gov/sunbiz/other-services/data-downloads/quarterly-data/),
then pass the ZIP archive or extracted fixed-width `.txt` files. Quarterly
corporate archives are very large; the parser streams their text records and
follows the official [corporate file definitions](https://dos.sunbiz.org/data-definitions/cor.html).
The data may not reflect the latest filing information, and a corporate
record does not establish that a business occupies a researched property.

### Hunter contact enrichment

Set `HUNTER_API_KEY` in `.env` and call
`fiber_scout.hunter.search_domain_contacts(domain)` with a business domain.
This uses Hunter's [Domain Search API](https://hunter.io/api-documentation/v2#domain-search),
which may consume provider credits. Results include Hunter's confidence score
and available source URLs; they are provider-supplied leads, not guaranteed
current or verified contacts.

### Current implementation boundary

The CSV functions and four research tools are implemented, but they are not
yet connected to an agent loop or an end-to-end command-line run. The later
development stages will add the agent, scoring, evaluation, and improvements.
The tests use sample data and mocked provider responses; they do not make live
Places or Hunter API requests.

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
