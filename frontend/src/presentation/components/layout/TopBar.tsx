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
    <header className="flex justify-between items-center px-10 py-4 border-b border-border-custom bg-black/30 backdrop-blur-[10px] sticky top-0 z-5">
      <div className="flex items-center gap-3">{left}</div>
      <div className="flex items-center gap-4">
        {badge && (
          <span className="text-xs bg-status-blue/15 text-status-blue px-3 py-1 rounded-full border border-status-blue/40 font-bold">
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