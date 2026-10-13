import { AlertCircle, RotateCcw } from 'lucide-react';
import { Button } from '@/components/ui/button';

export function ErrorNotice({ message, retry, title = 'Unable to complete the request' }: { message: string; retry?: () => void; title?: string }) {
  return <div className="error-notice" role="alert">
    <AlertCircle size={18} className="shrink-0" aria-hidden="true" />
    <div className="min-w-0 flex-1"><p className="font-medium">{title}</p><p className="mt-1 text-sm">{message}</p></div>
    {retry && <Button type="button" variant="outline" size="sm" onClick={retry}><RotateCcw />Retry</Button>}
  </div>;
}
