import { useEffect, useId, type ReactNode } from 'react';
import { X } from 'lucide-react';
import { useDialogFocus } from '@/presentation/hooks/useDialogFocus';

interface FormModalProps {
  open: boolean;
  title: string;
  onClose: () => void;
  children: ReactNode;
  maxWidthClassName?: string;
}

/**
 * Contenedor común de los formularios modales: superpone la tarjeta, expone el
 * diálogo con su título para lectores de pantalla y ofrece el botón de cierre.
 * El formulario y sus acciones los aporta cada consumidor.
 */
export function FormModal({
  open,
  title,
  onClose,
  children,
  maxWidthClassName = 'max-w-[520px]',
}: FormModalProps) {
  const titleId = useId();
  const { ref: dialogRef, handleKeyDown: handleDialogKeyDown } =
    useDialogFocus<HTMLDivElement>(open);

  useEffect(() => {
    if (!open) return;

    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape') onClose();
    };
    document.addEventListener('keydown', handleKeyDown);
    return () => document.removeEventListener('keydown', handleKeyDown);
  }, [open, onClose]);

  if (!open) return null;

  return (
    <div className="fixed inset-0 z-50 bg-black/50 flex items-center justify-center p-4 animate-fade-in">
      <div
        ref={dialogRef}
        role="dialog"
        aria-modal="true"
        aria-labelledby={titleId}
        tabIndex={-1}
        onKeyDown={handleDialogKeyDown}
        className={`card w-full ${maxWidthClassName} p-6 relative outline-none`}
      >
        <button
          type="button"
          aria-label="Cerrar"
          onClick={onClose}
          className="absolute right-2 top-2 inline-flex h-11 w-11 items-center justify-center rounded-lg text-text-muted hover:text-text-main hover:bg-bg-secondary"
        >
          <X className="w-5 h-5" aria-hidden />
        </button>
        <h3 id={titleId} className="text-xl font-bold mb-4">
          {title}
        </h3>
        {children}
      </div>
    </div>
  );
}
