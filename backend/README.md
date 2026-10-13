# Knowledge Desk backend

Python 3.11+, FastAPI, and a deterministic MVC knowledge core. The HTTP app and supplied evaluator use the same controller. No API key or external model is required.

Run these commands from the **repository root**:

```sh
python3.11 -m venv .venv
.venv/bin/python -m pip install -r backend/requirements-dev.txt
.venv/bin/python tools/import_kit.py /path/to/hackathon-knowledge-kit-participant.zip --unpack
.venv/bin/python -m uvicorn backend.server.app:app --host 127.0.0.1 --port 8000 --workers 1
```

The importer keeps the organizer's private data and evaluator files in ignored root paths. To use an existing extracted dataset, set `KNOWLEDGE_SNAPSHOTS` to the directory containing the snapshot folders before starting Uvicorn. The app loads snapshots in the background; `/api/status` reports readiness. Use one worker so the process owns one in-memory index.

For the browser interface, run `npm ci --prefix frontend` and `npm run build --prefix frontend`; FastAPI serves `frontend/dist`. Alternatively, run the frontend's Vite development server alongside this API. [Docker setup](../README.md#run-with-docker) builds and runs both packages together.

## Code boundaries

- `server/`: request validation, readiness, static assets, and local kit loading.
- `submission/solution.py`: evaluator-compatible `build()` entrypoint.
- `submission/knowledge/`: models, parsing and resolution services, controller, presenters, and the contract adapter.
- `harness/contract.py`: published interface dataclasses.
- `tests/`: synthetic knowledge-core and HTTP checks.
- `pyproject.toml`: Python metadata and pytest configuration for application and tooling tests.
- `requirements.txt` and `requirements-dev.txt`: runtime and development dependency versions.

Keep `submission/` portable: the evaluator can load it independently of the HTTP server. Business rules belong in the knowledge core and are shared by HTTP answers, inline guidance, and evaluator calls.

## Verify

```sh
.venv/bin/python -m pytest -c backend/pyproject.toml backend/tests -q
.venv/bin/python harness/run_eval.py --submission backend/submission --eval eval/public_eval.jsonl --out results/prototype
```

The evaluator requires a locally imported participant kit and does not require a running server. Use `.venv/bin/python -m pytest -c backend/pyproject.toml -q` from the root to include repository-tooling tests. Evaluation outputs remain in ignored `results/`; do not commit private source material, evaluation answers, or credentials. See [recorded results and limitations](../docs/evaluation.md) and [source-selection rules](../docs/NOTES.md).
