import { useEffect, type ReactNode } from 'react';
import { AlertTriangle, X } from 'lucide-react';
import { Button } from '@/presentation/components/ui/Button';

interface ConfirmDialogProps {
  open: boolean;
  title: string;
  description?: ReactNode;
  confirmLabel?: string;
  cancelLabel?: string;
  tone?: 'danger' | 'primary';
  isLoading?: boolean;
  onConfirm: () => void;
  onCancel: () => void;
}

export function ConfirmDialog({
  open,
  title,
  description,
  confirmLabel = 'Confirmar',
  cancelLabel = 'Cancelar',
  tone = 'danger',
  isLoading = false,
  onConfirm,
  onCancel,
}: ConfirmDialogProps) {
  useEffect(() => {
    if (!open) return;

    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape') onCancel();
    };
    document.addEventListener('keydown', handleKeyDown);
    return () => document.removeEventListener('keydown', handleKeyDown);
  }, [open, onCancel]);

  if (!open) return null;

  return (
    <div
      className="fixed inset-0 z-50 bg-black/50 flex items-center justify-center p-4 animate-fade-in"
      onMouseDown={(e) => {
        if (e.target === e.currentTarget) onCancel();
      }}
    >
      <div
        role="dialog"
        aria-modal="true"
        aria-label={title}
        className="card relative w-full max-w-[440px] p-8 text-center"
      >
        <button
          type="button"
          aria-label="Cerrar"
          onClick={onCancel}
          className="absolute right-4 top-4 text-text-muted hover:text-text-main bg-transparent border-none cursor-pointer"
        >
          <X className="w-5 h-5" />
        </button>

        <div className="w-16 h-16 rounded-full mx-auto mb-5 flex items-center justify-center bg-status-red/10">
          <AlertTriangle className="w-8 h-8 text-status-red" />
        </div>

        <h3 className="text-2xl font-bold tracking-tight text-text-main">{title}</h3>
        {description && (
          <p className="mt-3 text-text-muted text-base whitespace-pre-line">{description}</p>
        )}

        <div className="flex flex-col sm:flex-row sm:items-center justify-center gap-3 mt-8">
          <Button
            type="button"
            variant="secondary"
            disabled={isLoading}
            onClick={onCancel}
            className="sm:flex-1 py-3"
          >
            {cancelLabel}
          </Button>
          <Button
            type="button"
            variant={tone === 'primary' ? 'primary' : 'danger'}
            isLoading={isLoading}
            onClick={onConfirm}
            className="sm:flex-1 py-3"
          >
            {confirmLabel}
          </Button>
        </div>
      </div>
    </div>
  );
}