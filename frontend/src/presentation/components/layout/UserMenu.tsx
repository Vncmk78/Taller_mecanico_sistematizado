import type { ReactNode } from 'react';
import { LogOut } from 'lucide-react';

interface UserMenuProps {
  userName: string;
  subtitle: string;
  onLogout: () => void;
  prepend?: ReactNode;
}

export function UserMenu({ userName, subtitle, onLogout, prepend }: UserMenuProps) {
  return (
    <div className="flex items-center gap-3">
      {prepend}
      <div className="text-right">
        <div className="text-sm font-bold">{userName}</div>
        <div className="text-xs text-text-muted">{subtitle}</div>
      </div>
      <button
        onClick={onLogout}
        className="ml-5 text-primary-red cursor-pointer text-lg bg-transparent border-none hover:text-white transition-colors"
        title="Cerrar Sesión"
      >
        <LogOut className="w-5 h-5" />
      </button>
    </div>
  );
}