# Prospect Fit Scoring Rubric (Draft)

## Purpose

Score each researched business prospect from 0 to 100 using evidence-based
subcriterion ratings. The language model may suggest ratings and explain its
evidence. Python must calculate the category scores and weighted total; the
model must not perform any scoring arithmetic.

## Weights

| Category | Weight |
|---|---:|
| Need | 40% |
| Feasibility | 35% |
| Reachability | 25% |
| **Total** | **100%** |

Formulas for the later Python implementation:

```text
need_score = bandwidth_need * 0.50
           + connected_systems_need * 0.30
           + product_fit * 0.20

feasibility_score = site_account_clarity * 0.50
                  + approval_path * 0.40
                  + procurement_path * 0.10

reachability_score = decision_maker_identified * 0.50
                   + contact_route * 0.30
                   + buying_path_accessibility * 0.20

fit_score = need_score * 0.40
          + feasibility_score * 0.35
          + reachability_score * 0.25
```

Each category score is from 0 to 100. Round the final result to the nearest
whole number in Python. Do not round intermediate category scores.

## Rating scale

Rate each subcriterion from 0 to 100 using the evidence available:

- **0:** Clear evidence that the prospect is a very poor fit on this
  criterion.
- **25:** Evidence indicates a weak fit.
- **50:** Neutral, mixed, or not established by available research.
- **75:** Evidence indicates a strong fit.
- **100:** Clear evidence of an excellent fit.

Use intermediate values only when evidence supports a position between these
anchors. Do not invent a fact to justify a rating. For unknown or
insufficiently sourced evidence, use 50 as the neutral midpoint and lower
the score's confidence. Record why the criterion is unknown.

## Need (40% of total)

Within the Need category, combine:

| Subcriterion | Share of Need |
|---|---:|
| Evidence of bandwidth-intensive work or data use | 50% |
| Evidence of dependence on cloud, VoIP, video, security, or connected systems | 30% |
| Evidence of fit for available speeds (1/5/10 Gbps) or static IPs | 20% |
| **Total** | **100%** |

Use published business information or other sources to support the rating.
Do not assume a need based only on industry, employee count, or business
name.

## Feasibility (35% of total)

Within the Feasibility category, combine:

| Subcriterion | Share of Feasibility |
|---|---:|
| Clarity of the site-to-account arrangement | 50% |
| Clarity of building access or required approvals | 40% |
| Clarity of the procurement path | 10% |
| **Total** | **100%** |

The owner has confirmed that supplied addresses are serviceable. Treat
serviceability as a user-provided eligibility condition, not a score input.
Do not claim a particular speed or installation capability is available at
an address unless independently verified.

For MTUs, consider whether tenant service requires manager or landlord
approval. A manager's involvement is a research consideration, not an
automatic disqualifier. For a business with multiple locations, assess each
address/account separately.

## Reachability (25% of total)

Within the Reachability category, combine:

| Subcriterion | Share of Reachability |
|---|---:|
| Decision-maker or relevant role identified | 50% |
| Reliable, sourced contact route found | 30% |
| Evidence that the buying/approval path is accessible | 20% |
| **Total** | **100%** |

Churches have been relatively easy to reach based on the owner's experience;
national chain corporations have been harder to sell to. Use sourced
organization-specific evidence about contacts and authority rather than
assigning a score solely from a sector label.

## Confidence and explanation

- Provide a confidence level (`high`, `medium`, or `low`) for the score.
- Lower confidence when important criteria rely on neutral unknowns, weak
  sources, or incomplete evidence.
- Provide a brief explanation tied to the evidence and source URLs.
- Keep criterion ratings, their evidence, and score confidence distinct:
  confidence does not change the arithmetic.
- If a key fact is not found, record `not found`; do not fill the gap with a
  guess.
