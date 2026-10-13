# Development and review

Keep changes small enough to review by responsibility. Use `codex/<topic>` branches and conventional commit messages such as `feat(core): resolve qualified snapshot facts`, `test(api): cover request validation`, and `docs(docker): explain local startup`.

## Initial pull-request stack

| Branch | Base | Responsibility |
| --- | --- | --- |
| `codex/knowledge-core` | `main` | Offline MVC engine, evaluator contract, synthetic backend tests, source-selection notes |
| `codex/local-browser` | `codex/knowledge-core` | FastAPI delivery, React interface, inline question guidance |
| `codex/docker-local-runtime` | `codex/local-browser` | Container build, private local kit import, container smoke check, complete setup documentation |

Review and merge in that order. After merging a parent pull request, retarget its dependent pull request to `main` if GitHub has not already done so, update the branch, and wait for checks again. Do not force-push or merge a dependent branch while its parent is still under review. Open pull requests are review proposals; creating them does not merge the implementation into `main`.

## Main-branch policy

The intended GitHub protection requires a pull request, one approving review, dismissal of stale approvals, resolved review conversations, an up-to-date passing `quality` check, and linear history. It applies to administrators and blocks branch deletion and force pushes. Repository settings are authoritative; a policy file alone cannot enforce protection. Squash merging keeps each reviewed change coherent.

## Publication checks

Before every push, run:

```sh
python3 scripts/check_publication.py
```

This checks tracked/index content for restricted paths and recognizable credentials without printing their values. Review `git diff --cached --stat` and the staged diff as well. Use explicit file paths with `git add`; never force-add ignored participant materials. No automated scan can recognize every possible secret.

Never commit `.env` files, API keys, credentials, archives, website snapshots, practice evaluation data, local result files, or the supplied assignment documents. The only included participant interface is `harness/contract.py`; import the rest of the official kit locally using the documented setup. Tests and CI use synthetic data. Do not upload private data as workflow artifacts or bake it into a container image.

Use GitHub's noreply address for commit authorship if you do not want a personal email in Git history. Do not put secrets in commit messages, branch names, pull-request descriptions, or workflow logs.

## Pull-request descriptions

Describe the problem and resulting behavior, relevant validation, any dependent pull request, and known limitations. Keep raw snapshot excerpts and private evaluation files out of descriptions. A high public QA score does not prove hidden-set accuracy or exhaustive conflict detection.
