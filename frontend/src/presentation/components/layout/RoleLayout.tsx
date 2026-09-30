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
        <a
          href="#contenido-principal"
          className="sr-only focus:not-sr-only focus:absolute focus:top-2 focus:left-2 focus:z-[100] focus:rounded-md focus:bg-surface focus:px-4 focus:py-2 focus:text-text-main"
        >
          Saltar al contenido principal
        </a>
        <header className="flex items-center justify-between px-10 py-4 border-b border-border-custom bg-surface sticky top-0 z-50">
          <div className="flex items-center gap-2.5">
            <AppBrand />
            {badge && (
              <span className="ml-3 text-xs bg-primary-blue/15 text-primary-blue px-3 py-1 rounded-full border border-primary-blue/40 font-bold">
                {badge}
              </span>
            )}
          </div>

          <nav aria-label="Navegación principal" className="flex gap-2">
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

        <main id="contenido-principal" tabIndex={-1} className="flex-grow focus:outline-none">
          <Outlet />
        </main>
      </div>
    );
  }

  return (
    <div className="flex min-h-screen">
      <a
        href="#contenido-principal"
        className="sr-only focus:not-sr-only focus:absolute focus:top-2 focus:left-2 focus:z-[100] focus:rounded-md focus:bg-surface focus:px-4 focus:py-2 focus:text-text-main"
      >
        Saltar al contenido principal
      </a>
      <SidebarNav sections={sections} />

      <main
        id="contenido-principal"
        tabIndex={-1}
        className="flex-grow flex flex-col bg-bg-main h-screen overflow-y-auto focus:outline-none"
      >
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