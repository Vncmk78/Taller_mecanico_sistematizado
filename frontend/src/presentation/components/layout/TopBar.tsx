import type { ReactNode } from 'react';
import { Menu } from 'lucide-react';
import { UserMenu } from '@/presentation/components/layout/UserMenu';

interface TopBarProps {
  left?: ReactNode;
  rightPrepend?: ReactNode;
  badge?: string;
  userName: string;
  userSubtitle: string;
  onLogout: () => void;
  onOpenMenu?: () => void;
  menuOpen?: boolean;
}

export function TopBar({
  left,
  rightPrepend,
  badge,
  userName,
  userSubtitle,
  onLogout,
  onOpenMenu,
  menuOpen = false,
}: TopBarProps) {
  return (
    <header className="flex justify-between items-center gap-3 px-4 sm:px-8 lg:px-10 py-4 border-b border-border-custom bg-surface sticky top-0 z-20">
      <div className="flex min-w-0 flex-1 items-center gap-3">
        <button
          type="button"
          aria-label="Abrir menú de navegación"
          aria-controls="navegacion-lateral"
          aria-expanded={menuOpen}
          onClick={onOpenMenu}
          className="shrink-0 rounded-lg p-2 text-text-muted transition-colors hover:bg-bg-secondary hover:text-primary-blue lg:hidden"
        >
          <Menu className="h-5 w-5" aria-hidden />
        </button>
        {left}
      </div>
      <div className="flex shrink-0 items-center gap-3 sm:gap-4">
        {badge && (
          <span className="hidden md:inline-flex text-xs bg-status-blue/15 text-status-blue px-3 py-1 rounded-full border border-status-blue/40 font-bold">
            {badge}
          </span>
        )}
        <UserMenu
          userName={userName}
          subtitle={userSubtitle}
          onLogout={onLogout}
          prepend={rightPrepend}
        />
      </div>
    </header>
  );
}
