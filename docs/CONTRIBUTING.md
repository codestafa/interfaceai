# Development and review

Keep changes small enough to review by responsibility. Use `codex/<topic>` branches and conventional commit messages such as `feat(core): resolve qualified snapshot facts`, `test(api): cover request validation`, and `docs(docker): explain local startup`.

## Feature-branch workflow

Start each change from an up-to-date `main`, then open a pull request targeting `main`:

```sh
git switch main
git pull --ff-only
git switch -c codex/short-topic
```

Keep commits focused on one responsibility. Run the affected package checks and the publication guard before pushing; CI runs the application tests, frontend build, and synthetic container smoke check. Review the final diff and wait for checks on the final commit before merging. Do not push directly to `main` or force-push shared branches.

If a change must depend on another open pull request, name that dependency in its description. Merge the parent first, retarget the dependent request to `main`, update its branch, and rerun checks before merging. Creating a pull request does not authorize its merge.

The initial implementation was reviewed in three layers: `codex/knowledge-core` for the MVC engine and contract, `codex/local-browser` for the API and React interface, and `codex/docker-local-runtime` for packaging and setup. Those branch names document the original review breakdown; new work should start from `main`.

## Monorepo boundaries

Keep React presentation and frontend dependencies in `frontend/`. Put HTTP delivery, the shared knowledge core, application tests, and Python dependencies in `backend/`. The `backend/submission/` directory must remain independently loadable by the supplied evaluator; do not introduce imports from the HTTP server or frontend into it.

`tools/` contains repository tooling, publication checks, private-kit import, the Dockerfile, local Git hooks, and tooling tests in `tools/tests/`. Compose and CI coordinate both packages. Declare Python dependency versions in `backend/requirements*.txt`; `backend/pyproject.toml` configures both test suites. From the repository root, run `python -m pytest -c backend/pyproject.toml -q`, or add `backend/tests` to run only backend tests. Keep contribution guidance, design notes, and verification records in `docs/`.

## Main-branch policy

The intended GitHub protection requires a pull request, one approving review, dismissal of stale approvals, resolved review conversations, an up-to-date passing `quality` check, and linear history. It applies to administrators and blocks branch deletion and force pushes. Repository settings are authoritative; a policy file alone cannot enforce protection. Squash merging keeps each reviewed change coherent.

**Current status (October 13, 2026):** This repository is public. GitHub reports that `main` is not protected; the policy above has not been enabled. Check repository settings for the current status. A passing workflow and local hooks do not enforce GitHub merge restrictions.

Enable the local pre-push guard in each clone:

```sh
git config core.hooksPath tools/git-hooks
```

The guard rejects direct pushes to `main` and scans every unpublished commit before feature-branch pushes. Hooks can be bypassed and do not protect merges through GitHub, so this is only a local safeguard while server-side protection is not enabled.

## Publication checks

Before every push, run:

```sh
python3 tools/check_publication.py
```

This checks tracked/index content for restricted paths and recognizable credentials without printing their values. Review `git diff --cached --stat` and the staged diff as well. Use explicit file paths with `git add`; never force-add ignored participant materials. No automated scan can recognize every possible secret.

Never commit `.env` files, API keys, credentials, archives, website snapshots, practice evaluation data, local result files, or the supplied assignment documents. The only included participant interface is `backend/harness/contract.py`; import the rest of the official kit locally using the documented setup. Tests and CI use synthetic data. Do not upload private data as workflow artifacts or bake it into a container image.

Use GitHub's noreply address for commit authorship if you do not want a personal email in Git history. Do not put secrets in commit messages, branch names, pull-request descriptions, or workflow logs.

## Pull-request descriptions

Describe the problem and resulting behavior, relevant validation, any dependent pull request, and known limitations. Keep raw snapshot excerpts and private evaluation files out of descriptions. A high public QA score does not prove hidden-set accuracy or exhaustive conflict detection.
