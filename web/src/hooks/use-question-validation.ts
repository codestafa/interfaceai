import { useEffect, useState } from 'react';
import { validateQuestion, type QuestionValidation } from '@/lib/api';

interface DraftFeedback {
  question: string;
  asOf: string;
  validation: QuestionValidation;
}

export function useQuestionValidation(question: string, asOf: string, enabled: boolean) {
  const [feedback, setFeedback] = useState<DraftFeedback | null>(null);

  useEffect(() => {
    setFeedback(null);
    if (!enabled || !question.trim()) return;

    const controller = new AbortController();
    const timer = setTimeout(async () => {
      try {
        const validation = await validateQuestion(question.trim(), asOf, controller.signal);
        if (!controller.signal.aborted) setFeedback({ question, asOf, validation });
      } catch {
        // Validation is optional guidance; lookup remains available if it fails.
      }
    }, 600);

    return () => {
      clearTimeout(timer);
      controller.abort();
    };
  }, [question, asOf, enabled]);

  // Hide old feedback during the render itself, before effect cleanup runs.
  return enabled && feedback?.question === question && feedback.asOf === asOf
    ? feedback.validation
    : null;
}
