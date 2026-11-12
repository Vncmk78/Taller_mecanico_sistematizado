import type { ReactNode } from 'react';
import { LogOut } from 'lucide-react';

interface UserMenuProps {
  userName: string;
  subtitle: string;
  onLogout: () => void;
  prepend?: ReactNode;
  tone?: 'light' | 'dark';
}

export function UserMenu({ userName, subtitle, onLogout, prepend, tone = 'light' }: UserMenuProps) {
  const nameClass = tone === 'dark' ? 'text-white' : 'text-text-main';
  const subtitleClass = tone === 'dark' ? 'text-[#CBD5E1]' : 'text-text-muted';

  return (
    <div className="flex items-center gap-3">
      {prepend}
      <div className="hidden sm:block text-right">
        <div className={`text-sm font-bold ${nameClass}`}>{userName}</div>
        <div className={`text-xs ${subtitleClass}`}>{subtitle}</div>
      </div>
      <button
        type="button"
        aria-label="Cerrar sesión"
        onClick={onLogout}
        className="ml-2 sm:ml-5 text-primary-orange cursor-pointer text-lg bg-transparent border-none hover:text-primary-orange-hover transition-colors"
        title="Cerrar sesión"
      >
        <LogOut className="w-5 h-5" aria-hidden />
      </button>
    </div>
  );
}
