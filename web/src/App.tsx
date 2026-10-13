import { useRef, useState } from 'react';
import { ErrorNotice } from '@/components/error-notice';
import { useKnowledgeStatus } from '@/hooks/use-knowledge-status';
import { AskView } from '@/views/ask-view';
import { ConflictsView } from '@/views/conflicts-view';
import { formatDate } from '@/lib/utils';

export default function App() {
  const { status, error, retry } = useKnowledgeStatus();
  const [view, setView] = useState<'ask' | 'conflicts'>('ask');
  const [asOf, setAsOf] = useState('');
  const mainRef = useRef<HTMLElement>(null);
  const ready = status?.state === 'ready' && !error;
  const isError = Boolean(error || status?.state === 'error');

  function showView(next: 'ask' | 'conflicts') {
    setView(next);
    requestAnimationFrame(() => mainRef.current?.focus({ preventScroll: true }));
    window.scrollTo({ top: 0, behavior: 'instant' });
  }

  return <div className="app-shell">
    <a href="#main-content" className="skip-link">Skip to content</a>
    <header className="site-header"><span className="wordmark">Dupaco answers<span aria-hidden="true">.</span></span></header>
    <main id="main-content" className="main-content" ref={mainRef} tabIndex={-1}>
      {isError && <div className="service-error"><ErrorNotice title="We can’t reach the saved pages yet" message={error || status?.error || 'The saved pages could not be loaded.'} retry={retry} /></div>}
      <div hidden={view !== 'ask'}>
        <AskView active={view === 'ask'} status={status} asOf={asOf} setAsOf={setAsOf} onShowConflicts={() => showView('conflicts')} serviceError={isError} />
      </div>
      <div hidden={view !== 'conflicts'}>
        <ConflictsView active={view === 'conflicts'} ready={ready} snapshots={status?.snapshots ?? []} onBack={() => showView('ask')} />
      </div>
      <footer className="page-footer">
        <p>{status?.latest_date ? `Answers use saved website pages through ${formatDate(status.latest_date)}.` : 'Answers come from saved Dupaco website pages.'}</p>
        {view === 'ask' && <button type="button" className="quiet-link" onClick={() => showView('conflicts')}>Explore source disagreements</button>}
      </footer>
    </main>
  </div>;
}
