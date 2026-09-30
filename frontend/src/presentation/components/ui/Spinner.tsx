import { Loader2 } from 'lucide-react';

interface SpinnerProps {
  className?: string;
  label?: string;
}

export function Spinner({ className = 'w-8 h-8', label = 'Cargando...' }: SpinnerProps) {
  return (
    <span role="status" aria-label={label} className="inline-flex items-center">
      <Loader2 className={`animate-spin ${className}`} aria-hidden="true" />
    </span>
  );
}