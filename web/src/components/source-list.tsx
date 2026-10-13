import { ChevronDown, FileText, ExternalLink } from 'lucide-react';
import { type Snapshot, type Source } from '@/lib/api';
import { formatDate } from '@/lib/utils';

function sourceLabel(url: string) {
  try {
    const parsed = new URL(url);
    return `${parsed.hostname}${decodeURIComponent(parsed.pathname)}`;
  } catch { return url; }
}

function safeSourceUrl(url: string) {
  try { return ['http:', 'https:'].includes(new URL(url).protocol) ? url : undefined; }
  catch { return undefined; }
}

interface SourceListProps {
  sources: Source[];
  snapshots?: Snapshot[];
  expanded?: boolean;
}

export function SourceList({ sources, snapshots = [], expanded = false }: SourceListProps) {
  if (!sources.length) return <p className="text-sm text-muted-foreground">No supporting page was found.</p>;
  const dates = new Map(snapshots.map(snapshot => [snapshot.snapshot_id, snapshot.taken_on]));
  const Container = expanded ? 'article' : 'details';
  const Heading = expanded ? 'div' : 'summary';

  return <div className="source-list">
    {sources.map((source, index) => {
      const savedDate = dates.get(source.snapshot_id ?? '');
      return <Container key={`${source.url}-${source.snapshot_id}-${index}`} className="source-item">
        <Heading className="source-heading">
          <FileText size={15} className="shrink-0 text-muted-foreground" aria-hidden="true" />
          <span className="min-w-0 flex-1 break-all">{sourceLabel(source.url)}</span>
          {!expanded && <ChevronDown size={15} className="source-chevron shrink-0" aria-hidden="true" />}
        </Heading>
        <div className="source-body">
          {source.quote ? <blockquote>{source.quote}</blockquote> : <p className="text-muted-foreground">This page has no saved excerpt.</p>}
          <div className="source-meta">
            {savedDate && <span>Saved on {formatDate(savedDate)}</span>}
            {!savedDate && source.snapshot_id && <span className="break-all">Saved version: {source.snapshot_id}</span>}
            {safeSourceUrl(source.url) && <a href={source.url} target="_blank" rel="noreferrer" className="source-link">Open source website <ExternalLink size={12} aria-hidden="true" /></a>}
          </div>
          <p className="mt-2 text-xs text-muted-foreground">The live website may have changed since this page was saved.</p>
        </div>
      </Container>;
    })}
  </div>;
}
