import { useRef, useState, type FormEvent } from 'react';
import { ArrowRight, ChevronDown, CircleHelp, LoaderCircle } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { ErrorNotice } from '@/components/error-notice';
import { SourceList } from '@/components/source-list';
import { useQuestionValidation } from '@/hooks/use-question-validation';
import { askQuestion, errorMessage, type Answer, type KnowledgeStatus } from '@/lib/api';
import { formatDate } from '@/lib/utils';

interface AskViewProps {
  active: boolean;
  status: KnowledgeStatus | null;
  asOf: string;
  setAsOf: (date: string) => void;
  onShowConflicts: () => void;
  serviceError: boolean;
}

interface Result { answer: Answer; question: string; asOf: string }

export function AskView({ active, status, asOf, setAsOf, onShowConflicts, serviceError }: AskViewProps) {
  const [question, setQuestion] = useState('');
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<Result | null>(null);
  const questionRef = useRef<HTMLTextAreaElement>(null);
  const resultRef = useRef<HTMLElement>(null);
  const ready = status?.state === 'ready' && !serviceError;
  const validation = useQuestionValidation(question, asOf, active && ready && !pending && !result);
  const submissionBlocked = !question.trim() || !ready || pending || Boolean(validation?.blocking);

  async function submit(event?: FormEvent) {
    event?.preventDefault();
    if (submissionBlocked) return;
    setPending(true);
    setError(null);
    const submittedQuestion = question.trim();
    const submittedDate = asOf;
    try {
      const answer = await askQuestion(submittedQuestion, submittedDate);
      setResult({ answer, question: submittedQuestion, asOf: submittedDate });
      requestAnimationFrame(() => resultRef.current?.focus({ preventScroll: true }));
    } catch (cause) { setError(errorMessage(cause)); }
    finally { setPending(false); }
  }

  function askAgain() {
    setResult(null);
    requestAnimationFrame(() => {
      questionRef.current?.focus();
      questionRef.current?.select();
    });
  }

  const answerDate = result?.answer.selected_snapshot_date ?? status?.snapshots.find(snapshot =>
    result?.answer.sources.some(source => source.snapshot_id === snapshot.snapshot_id),
  )?.taken_on;

  return <div>
    {!result && <>
      <div className="page-heading"><h1>What would you like to know about Dupaco?</h1><p>Ask about a rate, an account, or a branch.<br className="desktop-break" /> We’ll look it up in the saved website pages.</p></div>
      <form className="question-form" onSubmit={submit}>
        <label htmlFor="question" className="field-label">Your question</label>
        <textarea ref={questionRef} id="question" name="question" rows={3} maxLength={4000} value={question} onChange={event => setQuestion(event.target.value)} placeholder="For example, what’s the rate for a 60-month auto loan?" aria-describedby="question-validation question-help" aria-invalid={validation?.blocking || undefined} onKeyDown={event => { if ((event.metaKey || event.ctrlKey) && event.key === 'Enter') { event.preventDefault(); void submit(); } }} />
        <p id="question-validation" className={`validation-helper${validation?.blocking ? ' blocking' : ''}`} aria-live="polite" aria-atomic="true">{validation?.message}</p>
        <details className="question-options">
          <summary>Options{asOf && <span> · {formatDate(asOf, true)}</span>}<ChevronDown size={15} aria-hidden="true" /></summary>
          <div className="date-option"><label htmlFor="as-of" className="field-label">Look back to an earlier date</label><div className="date-control"><input id="as-of" name="as_of" type="date" value={asOf} onChange={event => setAsOf(event.target.value)} aria-describedby="date-help" />{asOf && <button type="button" className="quiet-link" onClick={() => setAsOf('')}>Clear date</button>}</div><p id="date-help">Leave this blank for the latest saved information, or include a date in your question.</p></div>
        </details>
        <Button type="submit" disabled={submissionBlocked} className="primary-action">{pending ? <><LoaderCircle className="animate-spin" />Finding your answer…</> : <>Get answer <ArrowRight /></>}</Button>
        <p id="question-help" className="form-help">{!ready ? (serviceError || status?.state === 'error' ? 'Reconnect to the saved pages above to get an answer.' : 'Getting the saved pages ready. You can write your question now.') : 'Include the product, term, or location for a more useful answer.'}</p>
      </form>
      {error && <div className="request-error"><ErrorNotice message={error} retry={() => { void submit(); }} title="Your question is still here" /></div>}
    </>}

    <div aria-live="polite" className="sr-only">{pending ? 'Looking for your answer in the saved website pages.' : result ? 'Your answer is ready.' : ''}</div>
    {result && <section className="answer-result" ref={resultRef} tabIndex={-1} aria-label="Your answer">
      <div className="page-heading result-heading"><h1>Here’s what we found.</h1></div>
      <p className="answered-question"><span>You asked</span>{result.question}</p>
      <div className="answer-text">{result.answer.text}</div>
      {result.answer.confident && <p className="answer-status">Supported by saved pages{answerDate && ` · ${formatDate(answerDate)}`}</p>}
      {!result.answer.confident && <p className="uncertainty-note"><CircleHelp size={18} aria-hidden="true" /><span>We couldn’t confirm a complete answer from the saved pages.</span></p>}
      {!result.answer.confident && answerDate && <p className="answer-status">Pages saved on {formatDate(answerDate)}</p>}
      {result.answer.coverage_note && <p className="coverage-note">{result.answer.coverage_note}</p>}
      <details className="answer-evidence">
        <summary>How we found this <ChevronDown size={17} aria-hidden="true" /></summary>
        <div className="evidence-content">
          {(answerDate || result.asOf) && <div className="answer-dates">{answerDate && <p>Pages saved on <strong>{formatDate(answerDate)}</strong></p>}{result.asOf && <p>You requested information as of <strong>{formatDate(result.asOf)}</strong></p>}</div>}
          {result.answer.conflict_note && <div className="conflict-note"><h2>Some pages gave different answers</h2><p>{result.answer.conflict_note}</p><button type="button" onClick={onShowConflicts} className="quiet-link">Explore source disagreements</button></div>}
          <div className="answer-sources"><h2>Supporting pages</h2><SourceList sources={result.answer.sources} snapshots={status?.snapshots} expanded /></div>
        </div>
      </details>
      <Button type="button" onClick={askAgain} className="primary-action ask-again">Ask another question <ArrowRight /></Button>
    </section>}
  </div>;
}
