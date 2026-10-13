# Dupaco answers frontend

React + TypeScript + Vite, with Tailwind CSS v4 and editable shadcn/ui-style primitives backed by Radix UI. Button follows the MIT-licensed [shadcn/ui component patterns](https://ui.shadcn.com/docs); their source is kept locally under `src/components/ui`. Icons are bundled from Lucide. No remote fonts, images, or runtime assets are required.

From this directory:

```sh
npm ci
npm run dev
```

Vite proxies `/api` to `http://127.0.0.1:8000`; start the Python API separately using the root instructions. For the shared production server, run `npm run build` and let FastAPI serve `web/dist`. `npm run typecheck` validates the frontend independently.

The UI uses the actual knowledge API. Status polls only while snapshots are loading; conflicts load when that view is opened. The question-first flow leads to an answer, with dates under Options and flat source excerpts under How we found this. Submitted questions, drafts, date selections, and answer state remain in memory while visiting the advanced disagreements view. Source excerpts render as text; opening a source link is an explicit user action and may show a newer live website.
