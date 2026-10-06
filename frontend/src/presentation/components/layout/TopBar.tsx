import type { ReactNode } from 'react';
import { UserMenu } from '@/presentation/components/layout/UserMenu';

interface TopBarProps {
  left?: ReactNode;
  rightPrepend?: ReactNode;
  badge?: string;
  userName: string;
  userSubtitle: string;
  onLogout: () => void;
}

export function TopBar({
  left,
  rightPrepend,
  badge,
  userName,
  userSubtitle,
  onLogout,
}: TopBarProps) {
  return (
    <header className="flex justify-between items-center px-4 sm:px-8 lg:px-10 py-4 border-b border-border-custom bg-surface sticky top-0 z-5">
      <div className="flex items-center gap-3 min-w-0">{left}</div>
      <div className="flex items-center gap-3 sm:gap-4 shrink-0">
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