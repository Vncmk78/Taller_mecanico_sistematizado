import type { ReactNode } from 'react';
import { NavLink } from 'react-router-dom';

export interface NavItem {
  to: string;
  label: string;
  icon?: ReactNode;
  end?: boolean;
}

export interface NavSection {
  title?: string;
  items: NavItem[];
}

interface AppNavLinkProps extends NavItem {
  variant: 'sidebar' | 'topnav';
}

const baseClasses: Record<AppNavLinkProps['variant'], string> = {
  sidebar:
    'flex items-center gap-3.5 px-4 py-3.5 rounded-[10px] transition-all duration-200 text-base no-underline',
  topnav:
    'flex items-center gap-2.5 px-4 py-2.5 rounded-[10px] transition-all duration-200 text-sm font-medium no-underline',
};

const activeClasses: Record<AppNavLinkProps['variant'], string> = {
  sidebar:
    'bg-primary-blue text-white shadow-[0_4px_15px_rgba(21,40,63,0.25)] translate-x-[5px]',
  topnav: 'bg-primary-blue text-white shadow-[0_4px_15px_rgba(21,40,63,0.25)]',
};

const idleClasses: Record<AppNavLinkProps['variant'], string> = {
  sidebar: 'text-text-muted hover:bg-bg-secondary hover:text-primary-blue hover:translate-x-[5px]',
  topnav: 'text-text-muted hover:bg-bg-secondary hover:text-primary-blue',
};

export function AppNavLink({ to, label, icon, end, variant }: AppNavLinkProps) {
  return (
    <NavLink
      to={to}
      end={end}
      className={({ isActive }) =>
        `${baseClasses[variant]} ${isActive ? activeClasses[variant] : idleClasses[variant]}`
      }
    >
      {icon}
      {label}
    </NavLink>
  );
}