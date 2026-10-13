# Approach and boundaries

The browser and harness use one MVC knowledge core. Ingestion produces snapshot-specific evidence and indexes; the controller interprets a question, selects the historical state, resolves candidate facts, and asks a presenter to create the supplied harness dataclasses. The HTTP layer does not choose facts or reformat answers.

The monorepo keeps React presentation in `frontend/` and Python application code in `backend/`. `backend/server/` delivers HTTP, while `backend/submission/` retains the portable grader entrypoint and its MVC package. The evaluator loads that directory directly; the browser calls the same controller through FastAPI. The published contract dataclasses live in `backend/harness/contract.py`. Shared repository tooling lives in `tools/`, and project guidance and verification records live in `docs/`. Moving the packages changes their paths, not their source-selection rules.

## Sources and dates

Each snapshot represents the whole website at that time. Page membership is kept separately for every snapshot, so a removed page is not silently carried forward. Unchanged content can share parsed representations without losing snapshot provenance.

An explicit `as_of` argument takes precedence over a historical date in the question. Otherwise the latest snapshot is current. For a date between crawls, the system uses the most recent available snapshot on or before that date; it does not interpolate unknown changes. Dates before the first snapshot have no evidence. Requests beyond available coverage are qualified using the latest available evidence. A crawl timestamp is not an offer's effective date.

Financial facts retain their table headings and row qualifiers. Term, balance band, loan amount, model year, personal/business, standard/jumbo, introductory/standard, and rate/APR/APY identify different facts. Product aliases and normalization rules are shared by extraction and query interpretation. Values come from snapshot content, not from the practice-answer file.

Highest-rate account questions compare APY across published savings, checking, and certificate tiers. These comparisons exclude calculator examples and educational passages, preserve term and balance qualifications, and filter minimum deposits when the question supplies an amount. Personal accounts and non-introductory offers are the default; the answer labels its comparison scope. A missing comparison result stays uncertain instead of falling back to a debt-advice keyword match.

Lowest-rate questions use the same qualified comparison rules and keep APR, APY, and nominal interest separate. Historical wording such as “in 2025” selects that year's evidence; “2025 model-year car” selects a vehicle qualifier. Impossible calendar dates are rejected, and a request to predict future rates is not answered using today's rate.

The controller shares query preparation between inline guidance and answers. It asks for clarification for recognized conflicting terms, negative amounts, multiple topics, missing product scope, or another institution. Optional qualifier hints do not prevent intentionally broad comparisons. The browser debounces validation by 600 ms and discards stale responses; a helper connection failure does not disable answering. These are deterministic grammar checks, not a guarantee that every ambiguous phrase is recognized.

Official rate tables outrank illustrative calculator defaults for advertised rates. Branch-specific information and explicit closure announcements outrank generic hours or old counts. Policies use relevant official product/help content; historical questions use appropriately dated material. Qualifiers and applicability are checked before authority. An unresolved disagreement should produce uncertainty. Rejected values belong in a conflict explanation, not the main answer.

Structured narrative claims also retain the branch or applicable period. Routing numbers, named-branch hours, and institution counts can therefore participate in conflict resolution without treating different branches or ordinary changes over time as contradictions.

## Offline operation

No language model, external API, vector service, paid API, or key is used. The core is standard-library Python, and query-time operations use precomputed local indexes. All frontend assets are bundled locally. The user may choose to open a citation link in their own browser, but the application never fetches that website to answer a question.

## Prototype limitations

This is a deterministic extractor and query interpreter, not an unrestricted conversational model. Unrecognized wording, an unsupported product, incomplete evidence, or unusual Markdown can lead to a refusal. New domains may require an additional focused extractor or intent rule. Such rules should recognize content structure and terminology, never memorize expected answers.

The requirements audit identified three unresolved gaps: general policy contradictions can return a first matching passage confidently; contradictory claims with the same applicability period in different snapshots are not compared across snapshots; and explicit lists of savings products can be narrowed incorrectly to Share Savings. These need dedicated fixes and regression tests before claiming complete assignment coverage. Narrative conflict detection currently covers routing numbers, branch hours, and branch counts in addition to financial facts.

The evaluator's public paraphrase groups contain no meaningful multi-question paraphrase comparisons. Independent paraphrase tests are therefore included. Its judge-free scoring also cannot fully evaluate the broad certificate-list question; that answer must be reviewed separately. Final conflict gold labels are not supplied, so public results do not establish hidden conflict precision or recall.

The in-memory index is rebuilt when the local server restarts. There is no persistent question history, public hosting, or multi-user access control. The supplied website data must remain local and excluded from version control.
