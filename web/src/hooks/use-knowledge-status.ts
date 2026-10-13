import { useCallback, useEffect, useState } from 'react';
import { errorMessage, getStatus, type KnowledgeStatus } from '@/lib/api';

export function useKnowledgeStatus() {
  const [status, setStatus] = useState<KnowledgeStatus | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [attempt, setAttempt] = useState(0);
  const retry = useCallback(() => { setError(null); setAttempt(value => value + 1); }, []);

  useEffect(() => {
    let active = true;
    let timer: ReturnType<typeof setTimeout> | undefined;
    async function load() {
      try {
        const next = await getStatus();
        if (!active) return;
        setStatus(next);
        setError(null);
        if (next.state === 'loading') timer = setTimeout(load, 1500);
      } catch (cause) {
        if (active) setError(errorMessage(cause));
      }
    }
    void load();
    return () => { active = false; clearTimeout(timer); };
  }, [attempt]);

  return { status, error, retry };
}
