# Docker guide

Docker builds the React frontend and Python backend into one image. One Uvicorn worker serves both the API and the compiled browser assets; Node is not present in the final image. The container runs as a nonroot user and reads snapshots from a read-only mount.

## 1. Prerequisites and source

- Docker Engine or Docker Desktop with Docker Compose v2, running locally.
- The organizer-provided `hackathon-knowledge-kit-participant.zip`. It is private and is not included in this repository or image.
- Git. The commands below use a POSIX shell (macOS, Linux, or Windows WSL).

```bash
git clone https://github.com/codestafa/interfaceai.git
cd interfaceai
git config core.hooksPath tools/git-hooks
docker compose version
docker compose build
```

Clone the default `main` branch for the integrated application. See [the review workflow](CONTRIBUTING.md) for feature branches, publication checks, and the current main-branch protection status.

The multi-stage build uses Node 22 for `npm ci` and the type-checked Vite build, then Python 3.11 for the runtime dependencies. The default-deny `.dockerignore` only admits application source, dependency declarations, frontend assets, the import script, and the contract dataclasses. Snapshots, archives, results, evaluation answers, the starter, assignment documents, `.git`, and `.env` files never enter the build context.

## 2. Prepare local data without installing Python

Set `KIT_ARCHIVE` to the absolute location of your participant archive. This one-off container imports the supplied files and unpacks all snapshots into the ignored local `data/` directory. It needs no network connection. Your archive is mounted read-only, and the imported data stays on your machine.

```bash
KIT_ARCHIVE="/absolute/path/to/hackathon-knowledge-kit-participant.zip"
mkdir -p data
docker run --rm --network none --read-only \
  --user "$(id -u):$(id -g)" \
  --mount "type=bind,source=$KIT_ARCHIVE,target=/kit/participant.zip,readonly" \
  --mount "type=bind,source=$(pwd)/data,target=/data" \
  knowledge-desk:local \
  python tools/import_kit.py /kit/participant.zip --destination /data --unpack
```

The result includes `data/snapshots/<snapshot-id>/manifest.json` and each snapshot's Markdown files. Only `data/snapshots/` is mounted into the running app. Supplied evaluator files imported beside it are for local evaluation, not part of the application image.

The app must be able to read the extracted files. The command above creates them as your host user. For a shared directory with restrictive permissions, grant read access to files and traversal access to directories before launching the container.

## 3. Start and check readiness

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

## Ports and existing snapshot directories

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

## Logs, updates, and stopping

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

## Troubleshooting

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

## Container smoke test

This check uses temporary synthetic evidence and removes its test container when finished. It requires no participant kit.

```bash
docker build -f tools/Dockerfile -t knowledge-desk:local .
python3 tools/smoke_container.py --image knowledge-desk:local
```

For development without Docker, see the [backend](../backend/README.md) and [frontend](../frontend/README.md) guides. Return to the [project overview](../README.md).
