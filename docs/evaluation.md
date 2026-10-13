# Prototype verification

Verified locally on Python 3.11.17 with the original supplied evaluator. The harness and evaluation inputs were byte-compared against the participant archive: all 12 files were unchanged.

| Measurement | Starter | Prototype |
| --- | ---: | ---: |
| Public QA score | 0.093 | 0.9574 |
| Public questions | 40 | 40 |
| Stale-value traps | 0 | 0 |
| Evaluation errors | 0 | 0 |
| Repeated-answer consistency | 1.0 | 1.0 |
| Answer p95 | 0.12 s | 0.09 s |
| Ingestion | <0.1 s | 4.1 s |

The latest public-evaluator rerun (October 13, 2026), after the root-directory cleanup, is in the ignored `results/tree-cleanup/evaluation/` directory. The earlier document-based HTTP comparison remains in `results/document-check/`, and the initial implementation report remains in `results/prototype/`. The public evaluator rounds latency to hundredths of a second. Performance numbers are measurements on this machine, not a deployment guarantee.

All 40 supplied questions were also submitted to the running HTTP app. All 40 responses exactly matched the evaluator's answer text, confidence, sources, and conflict notes; HTTP p95 was 0.042 seconds. The status endpoint reported ready with five snapshots, and the conflict endpoint returned 122 entries. Browser checks of public questions dup-016 (current auto-loan APR), dup-006 (May certificate APY), and dup-145 (unpublished ARM rate) showed the expected results. The historical answer displayed and cited the May 19 snapshot.

## Focused checks

112 backend tests pass on Python 3.11. They cover worker-thread contract identity; snapshot boundaries, date precedence and removed pages; repeated ingestion; authority resolution and unresolved ties; tiers and APR/APY distinctions; effective and expiry dates; conflict deduplication; paraphrases; branch closures and named hours; narrative contradictions and ordinary historical changes; HTTP validation and readiness; static asset delivery; safe kit loading; and a renamed, portable submission directory. New coverage includes 25 date cases, 11 lowest-rate cases, 18 query-guard cases, and 16 inline-feedback cases.

Seven account-comparison regressions cover the reported “what account has the highest interest rate” question and alternative wording, savings-only scope, deposit minimums, exclusion of calculator examples and business accounts from personal comparisons, and missing deposit evidence. After this fix, the full public evaluator remains at 0.9574 with no stale-value hits or errors; that run is saved in `results/deposit-comparison/`.

Twenty additional live HTTP cases passed their expected supported-answer, clarification, refusal, or validation-error checks. They include invalid dates, future predictions, foreign institutions, negative amounts, contradictory terms, mixed topics, prompt injection, script text, heavy typos, Spanish, blank input, and historical year versus vehicle model year. Initial observations and final responses are saved in `results/edge-cases/initial.json` and `results/edge-cases/final.json`. Unrecognized language or heavy typos remain uncertain rather than being translated or corrected automatically.

TypeScript checking and the Vite production build pass. The simplified question → answer interface was tested against the local API at desktop and 320-pixel mobile widths. Browser checks covered a current auto-loan answer, a May certificate answer selected with the optional native date control and a date in the question, visible answer dates and confidence, direct excerpts inside the evidence disclosure, disagreement search and its empty state, preserved answers on return, an unsupported 99-year mortgage question, keyboard focus and keyboard submission, and recovery after an intentional server restart. The question was retained through the connection failure. Mobile content width matched the 320-pixel viewport without horizontal page overflow.

The inline helper was also verified in the actual browser: optional missing-detail hints, blocking unavailable history, date-selection refresh, replacement of stale hints, clearing the field, and keyboard submission both blocked and successful. Its message uses a polite accessible live region. At 320 pixels it wraps without horizontal overflow; the question remains editable and optional hints leave the primary action enabled.

## Repository and container checks

The packaging changes add 11 publication-guard tests and four private-kit import cases, bringing the passing suite to 127 tests. The guard checks the exact staged content and every outgoing commit; Git excludes snapshots, official evaluation files, the starter, assignment documents, archives, credentials, and local results. The Docker context uses a default-deny allowlist.

The multi-stage Docker build passed, including TypeScript and Vite compilation. A synthetic-data smoke test verified frontend assets, API readiness, a supported answer, inline validation, and conflict serialization. A separate local Compose run imported the private kit with networking disabled and loaded all five snapshots. Runtime checks confirmed UID 10001, read-only root and snapshot mount, a healthy status, and host binding only to 127.0.0.1:8080. No private data or container image was pushed.

GitHub rejected server-side protection for the private repository because the account requires GitHub Pro. A local direct-main push guard and CI are installed, but they cannot substitute for enforced repository protection. See [CONTRIBUTING.md](CONTRIBUTING.md) for the intended policy and feature-branch workflow.

## Monorepo layout

The application now lives in `backend/` and `frontend/`. Backend application tests are in `backend/tests/`; `tools/tests/` exercises repository tooling. Run `python -m pytest -c backend/pyproject.toml -q` from the repository root to collect both suites. Run the official evaluator from the repository root with `--submission backend/submission`; its private inputs and generated results remain at the root in ignored locations.

After the root-directory cleanup, all 127 tests passed, including the standalone evaluator-folder test and HTTP/static-asset tests. The original evaluator ran in isolated standard-library-only Python mode against `backend/submission`, preserving 0.9574 QA and 1.0 repeat consistency with no errors or stale-value hits. The new Docker build passed frontend type checking and compilation, and the synthetic container smoke test passed with the new package paths. Moving the code does not resolve the correctness gaps listed below.

## Limits of these results

A subsequent requirements audit reproduced three failures with independent synthetic fixtures: conflicting contact-update policies can produce a confident first-match answer; rates with the same effective date in separate snapshots are not reported as a conflict; and an explicit list of all savings APYs can omit products. These remain open implementation gaps. The public score must not be interpreted as complete assignment coverage.

The judge-free public scorer awards zero to its broad certificate-list question because the item has no required-token criteria. The actual answer was manually reviewed: it lists the extracted standard and jumbo terms with rates, minimums, and a saved-source citation. Remaining small score deductions are source-URL preference penalties, not incorrect expected numeric values.

The public paraphrase groups do not contain meaningful alternate-question pairs; the independent synthetic paraphrase test supplies that coverage. The hidden conflict gold set is unavailable. The prototype reports 122 deduplicated disagreements across the supplied snapshots; synthetic tests establish targeted behavior, not hidden-set precision or recall. Structured narrative conflict tests cover routing numbers, same-branch hours, and institution counts for the same period. Different branches and ordinary changes between periods are kept separate.

No paid LLM judge or live website retrieval was used.
