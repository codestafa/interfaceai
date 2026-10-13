import { useEffect, useMemo, useState } from 'react';
import { ArrowLeft, Check, ChevronDown, LoaderCircle, Scale, Search } from 'lucide-react';
import { ErrorNotice } from '@/components/error-notice';
import { SourceList } from '@/components/source-list';
import { errorMessage, getConflicts, type Conflict, type Snapshot } from '@/lib/api';
import { formatDate } from '@/lib/utils';

export function ConflictsView({ active, ready, snapshots, onBack }: { active: boolean; ready: boolean; snapshots: Snapshot[]; onBack: () => void }) {
  const [conflicts, setConflicts] = useState<Conflict[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [attempt, setAttempt] = useState(0);
  const [search, setSearch] = useState('');
  const datesBySnapshot = useMemo(() => new Map(snapshots.map(snapshot => [snapshot.snapshot_id, snapshot.taken_on])), [snapshots]);
  function evidenceDates(conflict: Conflict) {
    return [...new Set(conflict.sources.map(source => datesBySnapshot.get(source.snapshot_id ?? '')).filter((date): date is string => Boolean(date)))].sort().map(date => formatDate(date, true)).join(' · ');
  }
  useEffect(() => {
    if (!active || !ready || conflicts) return;
    let current = true;
    setError(null);
    getConflicts().then(data => { if (current) setConflicts(data); }).catch(cause => { if (current) setError(errorMessage(cause)); });
    return () => { current = false; };
  }, [active, ready, conflicts, attempt]);
  const filtered = useMemo(() => {
    const query = search.trim().toLowerCase();
    return (conflicts ?? []).filter(conflict => [conflict.topic, ...conflict.values, conflict.resolution, conflict.reason, ...conflict.sources.map(source => `${source.url} ${source.snapshot_id}`)].join(' ').toLowerCase().includes(query));
  }, [conflicts, search]);

  return <div>
    <button type="button" onClick={onBack} className="back-link"><ArrowLeft size={17} aria-hidden="true" />Back to your question</button><div className="page-heading conflicts-heading"><h1>When saved pages disagree.</h1><p>See which answer was chosen and why. These comparisons cover all saved dates, so older choices may differ from the latest answer.</p></div>
    <div className="conflict-toolbar"><div className="search-field"><Search size={17} aria-hidden="true" /><label htmlFor="conflict-search" className="sr-only">Search conflicts</label><input id="conflict-search" type="search" value={search} onChange={event => setSearch(event.target.value)} placeholder="Search topics, values, or sources…" /></div><span className="conflict-count" aria-live="polite">{conflicts ? `${filtered.length} ${filtered.length === 1 ? 'conflict' : 'conflicts'}` : 'Loading pages'}</span></div>
    {error ? <ErrorNotice message={error} retry={() => setAttempt(value => value + 1)} /> : !ready || !conflicts ? <div className="pending-state" role="status"><LoaderCircle className="animate-spin text-primary" size={20} /><p>{ready ? 'Loading disagreements…' : 'Waiting for the saved pages…'}</p></div> : filtered.length === 0 ? <div className="empty-state"><Scale size={28} aria-hidden="true" /><h2>{search ? 'No matching disagreements' : 'No disagreements found'}</h2><p>{search ? 'Try a product name, a rate, or a shorter search.' : 'No disagreements were found in the saved pages.'}</p></div> : <div className="conflicts-list">{filtered.map((conflict, index) => <article className="conflict-card" key={`${conflict.topic}-${index}`}>
      <div className="conflict-title"><span className="conflict-number">{String(index + 1).padStart(2, '0')}</span><h2>{conflict.topic}</h2><span className={conflict.resolution ? 'resolution-tag' : 'resolution-tag unresolved'}>{conflict.resolution ? 'Resolved' : 'Unresolved'}</span></div>
      <div className="competing-values"><span className="mini-label">COMPETING CLAIMS</span><div>{conflict.values.map((value, valueIndex) => <span className="value-chip" key={`${value}-${valueIndex}`}>{value}</span>)}</div></div>
      <div className="resolution"><span className="resolution-icon"><Check size={15} aria-hidden="true" /></span><div><h3>{conflict.resolution ? `Selected: ${conflict.resolution}` : 'No reliable selection'}</h3><p>{conflict.reason || 'The available evidence does not establish a clear resolution.'}</p></div></div>
      <details className="conflict-evidence"><summary><span className="evidence-summary-top">Inspect evidence <span className="evidence-source-count">{conflict.sources.length} sources</span><ChevronDown size={15} aria-hidden="true" /></span><span className="evidence-snapshot-dates">Pages saved on {evidenceDates(conflict) || 'Not available'}</span></summary><SourceList sources={conflict.sources} snapshots={snapshots} /></details>
    </article>)}</div>}
    {conflicts && conflicts.length > 0 && <p className="conflict-footer">Each comparison is for the same product and terms. Different account tiers and changes over time are considered separately.</p>}
  </div>;
}
