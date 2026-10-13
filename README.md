# Knowledge Desk

A local knowledge prototype for the credit-union snapshot assignment. Ask about Dupaco's accounts, rates, branches, membership, and policies using five saved website versions. Answers include source excerpts and dates; the app also exposes detected disagreements between sources.

The browser and evaluator use the same deterministic Python knowledge controller. **No API key, language model, account, or paid service is required.** Dependency installation and Docker image builds need internet access; answering questions uses only local snapshot files.

The browser starts with one question field and a **Get answer** action. Open **How we found this** after an answer to inspect evidence. **Options** reveals the historical date control, and a secondary link opens source disagreements. After a 600 ms typing pause, a helper suggests missing details or explains invalid input. Optional hints allow broad questions. There is no saved question history.

## Run with Docker

Docker builds the React frontend and Python backend into one image. One Uvicorn worker serves both the API and the compiled browser assets; Node is not present in the final image. The container runs as a nonroot user and reads snapshots from a read-only mount.

### 1. Prerequisites and source

- Docker Engine or Docker Desktop with Docker Compose v2, running locally.
- The organizer-provided `hackathon-knowledge-kit-participant.zip`. It is private and is not included in this repository or image.
- Git. The commands below use a POSIX shell (macOS, Linux, or Windows WSL).

```bash
git clone https://github.com/codestafa/interfaceai.git
cd interfaceai
git config core.hooksPath .githooks
docker compose version
docker compose build
```

Clone the default `main` branch for the integrated application. See [the review workflow](CONTRIBUTING.md) for feature branches, publication checks, and the current GitHub branch-protection limitation.

The multi-stage build uses Node 22 for `npm ci` and the type-checked Vite build, then Python 3.11 for the runtime dependencies. The default-deny `.dockerignore` only admits application source, dependency declarations, frontend assets, the import script, and the contract dataclasses. Snapshots, archives, results, evaluation answers, the starter, assignment documents, `.git`, and `.env` files never enter the build context.

### 2. Prepare local data without installing Python

Set `KIT_ARCHIVE` to the absolute location of your participant archive. This one-off container imports the supplied files and unpacks all snapshots into the ignored local `data/` directory. It needs no network connection. Your archive is mounted read-only, and the imported data stays on your machine.

```bash
KIT_ARCHIVE="/absolute/path/to/hackathon-knowledge-kit-participant.zip"
mkdir -p data
docker run --rm --network none --read-only \
  --user "$(id -u):$(id -g)" \
  --mount "type=bind,source=$KIT_ARCHIVE,target=/kit/participant.zip,readonly" \
  --mount "type=bind,source=$(pwd)/data,target=/data" \
  knowledge-desk:local \
  python scripts/import_kit.py /kit/participant.zip --destination /data --unpack
```

The result includes `data/snapshots/<snapshot-id>/manifest.json` and each snapshot's Markdown files. Only `data/snapshots/` is mounted into the running app. Supplied evaluator files imported beside it are for local evaluation, not part of the application image.

The app must be able to read the extracted files. The command above creates them as your host user. For a shared directory with restrictive permissions, grant read access to files and traversal access to directories before launching the container.

### 3. Start and check readiness

```bash
docker compose up -d --wait --wait-timeout 120
docker compose ps
curl --fail http://127.0.0.1:8080/api/status
```

Open [Knowledge Desk at localhost:8080](http://127.0.0.1:8080). The port is published only on `127.0.0.1`, so the app is not exposed to your local network. Port 8080 is the default to avoid an existing development server on 8000.

The health check waits until `/api/status` reports `"state":"ready"`, not just until HTTP starts responding. Ingestion runs in the background and rebuilds the in-memory indexes on each startup. The supplied kit normally indexes in a few seconds; allow more time on slower machines. Status should list five snapshots and their latest data date. The browser shows a loading state until ingestion finishes.

Try an API request:

```bash
curl --fail http://127.0.0.1:8080/api/answer \
  -H 'Content-Type: application/json' \
  -d '{"question":"What is Dupaco’s routing number?"}'
```

### Ports and existing snapshot directories

To use another host port, set `KNOWLEDGE_PORT` for each Compose command that needs the override:

```bash
KNOWLEDGE_PORT=8081 docker compose up -d --wait
```

To use previously extracted snapshots, set `KNOWLEDGE_DATA_DIR` to the directory containing the snapshot folders, not the kit ZIP or one individual snapshot:

```bash
KNOWLEDGE_DATA_DIR="/absolute/path/to/snapshots" \
  KNOWLEDGE_PORT=8081 docker compose up -d --wait
```

Inside the container, this host directory is always available at `/data/snapshots`. Compose deliberately fails if the source directory does not exist. It never creates an empty snapshot directory on your behalf. Keep any persistent local overrides in an ignored `.env` file; this app requires no secrets in that file.

### Logs, updates, and stopping

```bash
docker compose logs --tail=100 knowledge
docker compose logs -f knowledge
docker compose down
```

Press Ctrl+C to stop following logs. `down` removes the app container and Compose network; the locally mounted dataset remains in `data/`. The app keeps no persistent user history or database volume.

After changing application code, rebuild and recreate the service:

```bash
docker compose up -d --build --wait --wait-timeout 120
```

After updating only snapshot files, restart the service to rebuild its indexes:

```bash
docker compose restart knowledge
curl --fail http://127.0.0.1:8080/api/status
```

Use the same environment overrides for rebuild and restart commands if you changed the data directory or host port.

### Troubleshooting

| Symptom | What to check |
| --- | --- |
| Cannot connect to the Docker daemon | Start Docker Desktop or your Docker Engine, then retry. |
| Bind source path does not exist | Run the import step first, or correct `KIT_ARCHIVE` / `KNOWLEDGE_DATA_DIR`. Mount paths must exist on the Docker host. |
| Port is already allocated | Set an unused `KNOWLEDGE_PORT`, such as 8081. |
| Container is unhealthy | Read `docker compose logs --tail=100 knowledge` and `/api/status`. Missing data and unreadable files are reported there. |
| “No snapshots found” | Mount the extracted directory whose immediate children contain `manifest.json`. Unpack archives before starting: the runtime data mount is read-only. |
| Permission denied reading snapshots | Ensure the nonroot container can read snapshot files and traverse their directories; check Docker Desktop file-sharing permissions too. |
| Readiness times out while indexing | Inspect status and logs, then increase `--wait-timeout`. A longer timeout will not fix a reported loading error. |
| UI still shows old code | Rebuild the image and recreate the service, then refresh the browser. |

This is a local prototype, without authentication or production deployment configuration. Keep the localhost port binding when running it.

## Run without Docker

Requirements: Python 3.11 or newer, Node.js 22.12 or newer, and the supplied participant kit.

```bash
python3.11 -m venv .venv
.venv/bin/python -m pip install -r backend/requirements-dev.txt
npm ci --prefix frontend
npm run build --prefix frontend
.venv/bin/python scripts/import_kit.py /path/to/hackathon-knowledge-kit-participant.zip --unpack
.venv/bin/python -m uvicorn backend.server.app:app --host 127.0.0.1 --port 8000 --workers 1
```

Open [Knowledge Desk at localhost:8000](http://127.0.0.1:8000). The importer places the private snapshot archives, extracted snapshots, and official evaluation tools in ignored paths at the repository root. Without `--unpack`, the local server unpacks archives on first startup. To use another extracted directory, set `KNOWLEDGE_SNAPSHOTS` before the Uvicorn command. Run a single worker.

For frontend development, leave the Python server running and run `npm run dev --prefix frontend` in another terminal. Vite proxies `/api` to port 8000. Its terminal output supplies the frontend development URL.

## Evaluate and test

The official evaluator, public questions, and starter remain local. Import the participant kit into the repository root before running these commands, even if you previously prepared `data/` for Docker:

```bash
.venv/bin/python scripts/import_kit.py /path/to/hackathon-knowledge-kit-participant.zip --unpack
.venv/bin/python harness/run_eval.py --submission backend/submission --eval eval/public_eval.jsonl --out results/prototype
.venv/bin/python -m pytest -q
npm run build --prefix frontend
```

The unchanged supplied evaluator writes its summary and per-question results to the ignored `results/` directory. It loads `backend/submission/solution.py` directly and does not require a running web server. Do not enable its optional paid LLM judge when measuring offline performance.

Measured locally with the public 40-question set: **0.9574 QA score**, **1.0 repeat consistency**, **0.09 s answer p95**, and **4.0 s ingestion**, with no evaluation errors or forbidden stale-value hits. The backend and publication suite has **126 passing tests**, including 11 publication-guard tests and three kit-import tests; TypeScript checking and the production frontend build pass. The container passed both a synthetic-data smoke test and a local run with all five supplied snapshots. These are recorded measurements, not guarantees for other machines or hidden tests. See [evaluation details](docs/evaluation.md).

Run the container smoke test independently after building:

```bash
python3 scripts/smoke_container.py --image knowledge-desk:local
```

It generates its own temporary evidence, checks the UI assets and API, and removes its test container. GitHub CI uses this synthetic check and does not have access to the private participant dataset.

## Known limitations

The requirement audit identified three gaps that remain open:

1. Some conflicting prose policies can produce a confident answer instead of a reported contradiction.
2. Different snapshots claiming different values for the same explicit applicable period are not always compared for conflict.
3. A broad request for every savings-account APY can omit a product, such as Launchpad, even when its evidence is present.

The public score does not establish complete requirement coverage. The supplied scorer cannot fully assess the broad certificate-list answer, which was manually reviewed, and the final conflict gold set is unavailable. The query interpreter supports focused wording and qualifiers; it is not an unrestricted conversational model. Heavy typos and unsupported languages can result in uncertainty. See [NOTES.md](NOTES.md) for source-selection rules and other boundaries.

## Architecture and API

The monorepo separates the browser interface from the Python application. Run the documented commands from the repository root unless a package README says otherwise.

```text
interfaceai/
├── frontend/               # React, TypeScript, Vite; compiled output in dist/
├── backend/
│   ├── server/             # FastAPI endpoints and local snapshot loading
│   ├── submission/         # Self-contained evaluator entrypoint and MVC core
│   ├── tests/              # Knowledge-core and HTTP tests with synthetic data
│   └── requirements*.txt   # Python runtime and development dependencies
├── harness/contract.py     # Published interface dataclasses only
├── scripts/                # Local kit import, publication guard, container smoke test
├── tests/                  # Repository-tooling tests
├── docs/                   # Verification records
├── Dockerfile              # Frontend build and Python runtime stages
└── compose.yaml            # Local service and read-only snapshot mount
```

[Frontend development](frontend/README.md) and [backend development](backend/README.md) have package-specific commands. Root `requirements*.txt` files are compatibility wrappers around the backend declarations. The root test configuration runs both application and tooling tests. The private kit's remaining `harness/`, `eval/`, snapshot, and result files stay in ignored locations at the root; they are not packages to publish.

- **Model:** immutable evidence and fact records, complete snapshot membership, extraction, retrieval, date selection, and source resolution under `backend/submission/knowledge/`.
- **Controller:** `backend/submission/solution.py` constructs the shared controller implementing `ingest`, `answer`, and `conflicts`. `backend/server/` loads the kit and exposes the controller over HTTP.
- **View:** Python presenters format answers and contract objects; `frontend/` renders results without implementing knowledge rules.

The knowledge core uses the Python standard library. FastAPI and Uvicorn deliver the HTTP app. Node is needed only for building or developing the browser interface.

| Endpoint | Purpose |
| --- | --- |
| `GET /api/status` | Loading state, snapshot dates, and loading errors. |
| `POST /api/answer` | An answer with confidence, citations, and any conflict explanation. |
| `POST /api/validate` | Inline guidance: status, message, and whether clarification is required. |
| `GET /api/conflicts` | The same detected-conflict inventory returned to the evaluator. |

Both POST endpoints accept `{"question":"...","as_of":"2026-05-31"}`; `as_of` is optional. An explicit `as_of` takes precedence over a date written in the question. The answer endpoint independently applies the same validation rules as the helper. Malformed requests receive HTTP 422, requests made before readiness receive HTTP 503, and unavailable evidence returns a normal answer with `confident: false`.

## Data handling

Keep the organizer's snapshot content, archives, public evaluation answers, starter files, assignment documents, generated results, and any local environment files out of Git. The supplied `harness/contract.py` contains only interface dataclasses and is the one harness file required by the published application. The default-deny Docker context independently excludes private material, including files already present on your machine.

The application does not fetch live websites, send questions to an AI provider, or save question history. Source URLs are evidence links; you may choose to open one in your browser. No API keys or credentials are needed for building or running this prototype.
