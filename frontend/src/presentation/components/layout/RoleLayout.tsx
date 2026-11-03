import { useState, type ReactNode } from 'react';
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
  const [menuOpen, setMenuOpen] = useState(false);

  if (variant === 'topnav') {
    return (
      <div className="min-h-screen flex flex-col animate-fade-in">
        <a
          href="#contenido-principal"
          className="sr-only focus:not-sr-only focus:absolute focus:top-2 focus:left-2 focus:z-[100] focus:rounded-md focus:bg-surface focus:px-4 focus:py-2 focus:text-text-main"
        >
          Saltar al contenido principal
        </a>
        <header className="flex flex-wrap items-center justify-between gap-2 px-4 sm:px-6 lg:px-10 py-4 border-b-3 border-b-primary-orange bg-[#111318] sticky top-0 z-50 text-white shadow-[0_4px_14px_rgba(0,0,0,0.25)]">
          <div className="flex shrink-0 items-center gap-2.5">
            <AppBrand />
            {badge && (
              <span className="ml-1 hidden text-xs bg-primary-blue/15 text-primary-blue px-3 py-1 rounded-full border border-primary-blue/40 font-bold sm:ml-3 sm:inline-flex">
                {badge}
              </span>
            )}
          </div>

          <nav
            aria-label="Navegación principal"
            className="order-last flex w-full min-w-0 items-center gap-1 overflow-x-auto sm:gap-2 xl:order-none xl:w-auto xl:flex-1 xl:justify-center"
          >
            {sections.flatMap((section) => section.items).map((item) => (
              <AppNavLink key={item.to} variant="topnav" onNavigate={() => setMenuOpen(false)} {...item} />
            ))}
          </nav>

          <div className="shrink-0">
            <UserMenu
              userName={userName}
              subtitle={userSubtitle}
              onLogout={onLogout}
            />
          </div>
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
      <SidebarNav sections={sections} open={menuOpen} onClose={() => setMenuOpen(false)} />

      <main
        id="contenido-principal"
        tabIndex={-1}
        className="flex min-w-0 flex-grow flex-col bg-bg-secondary h-screen overflow-y-auto focus:outline-none"
      >
        <TopBar
          left={headerLeft}
          rightPrepend={headerRightPrepend}
          badge={badge}
          userName={userName}
          userSubtitle={userSubtitle}
          onLogout={onLogout}
          onOpenMenu={() => setMenuOpen(true)}
          menuOpen={menuOpen}
        />

        <div className="flex-grow">
          <Outlet />
        </div>
      </main>
    </div>
  );
}
