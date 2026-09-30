import type { ButtonHTMLAttributes, ReactNode } from 'react';

interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: 'primary' | 'secondary' | 'admin' | 'accent' | 'danger' | 'success';
  isLoading?: boolean;
  children: ReactNode;
}

const variantClasses = {
  primary:
    'bg-primary-blue text-white hover:bg-primary-blue-hover shadow-[0_4px_15px_rgba(21,40,63,0.25)] hover:shadow-[0_6px_20px_rgba(21,40,63,0.3)] hover:-translate-y-0.5',
  secondary:
    'bg-surface border border-border-custom text-text-main hover:bg-bg-secondary hover:border-border-custom',
  admin:
    'bg-primary-blue text-white hover:bg-primary-blue-hover shadow-[0_4px_15px_rgba(21,40,63,0.25)]',
  accent:
    'bg-primary-orange text-white hover:bg-primary-orange-hover shadow-[0_4px_15px_rgba(242,106,46,0.25)] hover:shadow-[0_6px_20px_rgba(242,106,46,0.35)] hover:-translate-y-0.5',
  danger:
    'bg-status-red/10 border border-status-red/30 text-status-red hover:bg-status-red/20',
  success:
    'bg-status-green text-white hover:bg-status-green/90 shadow-[0_4px_20px_rgba(22,131,93,0.3)]',
};

export function Button({
  variant = 'primary',
  isLoading = false,
  children,
  className = '',
  disabled,
  type = 'button',
  ...props
}: ButtonProps) {
  return (
    <button
      type={type}
      className={`px-6 py-3 rounded-lg font-bold text-base transition-all duration-300 cursor-pointer border-none disabled:opacity-50 disabled:cursor-not-allowed ${variantClasses[variant]} ${className}`}
      disabled={disabled || isLoading}
      {...props}
    >
      {isLoading ? (
        <span className="flex items-center justify-center gap-2">
          <svg
            className="animate-spin h-5 w-5"
            xmlns="http://www.w3.org/2000/svg"
            fill="none"
            viewBox="0 0 24 24"
          >
            <circle
              className="opacity-25"
              cx="12"
              cy="12"
              r="10"
              stroke="currentColor"
              strokeWidth="4"
            />
            <path
              className="opacity-75"
              fill="currentColor"
              d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"
            />
          </svg>
          Cargando...
        </span>
      ) : (
        children
      )}
    </button>
  );
}
