import type { InputHTMLAttributes, ReactNode } from 'react';
import { forwardRef } from 'react';

interface InputProps extends InputHTMLAttributes<HTMLInputElement> {
  label?: string;
  icon?: ReactNode;
  error?: string;
}

export const Input = forwardRef<HTMLInputElement, InputProps>(
  ({ label, icon, error, className = '', ...props }, ref) => {
    return (
      <div className="mb-6">
        {label && (
          <label className="block mb-2 text-sm text-gray-200">{label}</label>
        )}
        <div className="relative flex items-center">
          {icon && (
            <span className="absolute left-4 text-text-muted text-lg">
              {icon}
            </span>
          )}
          <input
            ref={ref}
            className={`w-full py-3.5 pr-4 bg-black/50 border rounded-lg text-white text-base transition-all duration-300 outline-none focus:border-primary-red focus:bg-black/80 focus:shadow-[0_0_0_3px_rgba(211,47,47,0.2)] ${
              icon ? 'pl-12' : 'pl-4'
            } ${error ? 'border-status-red' : 'border-border-custom'} ${className}`}
            {...props}
          />
        </div>
        {error && <p className="mt-1 text-sm text-status-red">{error}</p>}
      </div>
    );
  }
);

Input.displayName = 'Input';
