import type { ReactNode } from 'react';
import { AlertCircle, AlertTriangle, CheckCircle2, Info } from 'lucide-react';

export type AlertTone = 'error' | 'success' | 'warning' | 'info' | 'orange';

interface AlertProps {
  tone?: AlertTone;
  children: ReactNode;
  className?: string;
  action?: ReactNode;
}

const toneClasses: Record<AlertTone, string> = {
  error: 'text-status-red bg-status-red/10 border-status-red/40',
  success: 'text-status-green bg-status-green/10 border-status-green/40',
  warning: 'text-status-yellow bg-status-yellow/10 border-status-yellow/40',
  info: 'text-status-blue bg-status-blue/10 border-status-blue/40',
  orange: 'text-status-orange bg-status-orange/10 border-status-orange/40',
};

const toneIcons: Record<AlertTone, typeof AlertCircle> = {
  error: AlertCircle,
  success: CheckCircle2,
  warning: AlertTriangle,
  info: Info,
  orange: AlertTriangle,
};

export function Alert({ tone = 'info', children, className = '', action }: AlertProps) {
  const Icon = toneIcons[tone];
  return (
    <div
      role="alert"
      className={`flex items-center gap-3 flex-wrap text-sm border border-solid rounded-lg px-4 py-3 ${toneClasses[tone]} ${className}`}
    >
      <span className="flex items-center gap-2 min-w-0">
        <Icon className="w-4 h-4 shrink-0" aria-hidden="true" />
        <span className="min-w-0">{children}</span>
      </span>
      {action && <span className="shrink-0">{action}</span>}
    </div>
  );
}