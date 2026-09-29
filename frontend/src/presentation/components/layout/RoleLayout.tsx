import type { ReactNode } from 'react';
import { Outlet } from 'react-router-dom';
import { AppBrand } from '@/presentation/components/layout/AppBrand';
import { AppNavLink, type NavSection } from '@/presentation/components/layout/AppNavLink';
import { SidebarNav } from '@/presentation/components/layout/SidebarNav';
import { TopBar } from '@/presentation/components/layout/TopBar';
import { UserMenu } from '@/presentation/components/layout/UserMenu';

export interface RoleLayoutProps {
  variant: 'sidebar' | 'topnav';
  sections: NavSection[];
  badge?: string;
  userName: string;
  userSubtitle: string;
  onLogout: () => void;
  headerLeft?: ReactNode;
  headerRightPrepend?: ReactNode;
}

export function RoleLayout({
  variant,
  sections,
  badge,
  userName,
  userSubtitle,
  onLogout,
  headerLeft,
  headerRightPrepend,
}: RoleLayoutProps) {
  if (variant === 'topnav') {
    return (
      <div className="min-h-screen flex flex-col animate-fade-in">
        <header className="flex items-center justify-between px-10 py-4 border-b border-border-custom bg-black/80 backdrop-blur-[10px] sticky top-0 z-50">
          <div className="flex items-center gap-2.5">
            <AppBrand />
            {badge && (
              <span className="ml-3 text-xs bg-primary-red/15 text-primary-red px-3 py-1 rounded-full border border-primary-red/40 font-bold">
                {badge}
              </span>
            )}
          </div>

          <nav className="flex gap-2">
            {sections.flatMap((section) => section.items).map((item) => (
              <AppNavLink key={item.to} variant="topnav" {...item} />
            ))}
          </nav>

          <UserMenu
            userName={userName}
            subtitle={userSubtitle}
            onLogout={onLogout}
          />
        </header>

        <main className="flex-grow">
          <Outlet />
        </main>
      </div>
    );
  }

  return (
    <div className="flex min-h-screen">
      <SidebarNav sections={sections} />

      <main className="flex-grow flex flex-col bg-glass-panel h-screen overflow-y-auto backdrop-blur-[8px]">
        <TopBar
          left={headerLeft}
          rightPrepend={headerRightPrepend}
          badge={badge}
          userName={userName}
          userSubtitle={userSubtitle}
          onLogout={onLogout}
        />

        <div className="flex-grow">
          <Outlet />
        </div>
      </main>
    </div>
  );
}