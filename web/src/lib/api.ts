export interface Source { url: string; snapshot_id?: string | null; quote?: string | null }
export interface Answer {
  text: string; sources: Source[]; confident: boolean; conflict_note?: string | null;
  selected_snapshot_date?: string | null; coverage_note?: string | null;
}
export interface Conflict {
  topic: string; values: string[]; sources: Source[]; resolution?: string | null; reason?: string | null;
}
export interface Snapshot { snapshot_id: string; taken_on: string; page_count: number }
export interface KnowledgeStatus {
  state: 'loading' | 'ready' | 'error'; snapshots: Snapshot[];
  latest_date: string | null; error: string | null;
}
export interface QuestionValidation {
  status: 'ready' | 'needs_info' | 'unavailable';
  message: string;
  blocking: boolean;
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let response: Response;
  try {
    const timeout = AbortSignal.timeout(65_000);
    const signal = init?.signal ? AbortSignal.any([init.signal, timeout]) : timeout;
    response = await fetch(path, { ...init, signal });
  } catch (error) {
    if (error instanceof Error && error.name === 'TimeoutError') {
      throw new Error('The request took too long. Please try again.');
    }
    throw new Error('Cannot reach the knowledge service. Check that the local server is running, then retry.');
  }
  const body: unknown = await response.json().catch(() => null);
  if (!response.ok) {
    const detail = body && typeof body === 'object' && 'detail' in body ? body.detail : null;
    const message = typeof detail === 'string' ? detail : 'The request could not be completed. Please check your question and date, then retry.';
    throw new Error(message);
  }
  if (!body) throw new Error('The service returned an empty response. Please retry.');
  return body as T;
}

export const getStatus = () => request<KnowledgeStatus>('/api/status');
export const getConflicts = () => request<Conflict[]>('/api/conflicts');
export const askQuestion = (question: string, asOf: string) => request<Answer>('/api/answer', {
  method: 'POST', headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({ question, as_of: asOf || null }),
});
export const validateQuestion = (question: string, asOf: string, signal: AbortSignal) => request<QuestionValidation>('/api/validate', {
  method: 'POST', headers: { 'Content-Type': 'application/json' }, signal,
  body: JSON.stringify({ question, as_of: asOf || null }),
});
export const errorMessage = (error: unknown) => error instanceof Error ? error.message : 'Something went wrong. Please retry.';
