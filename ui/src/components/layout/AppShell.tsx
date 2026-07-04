import type { ReactNode } from 'react';
import { TopBar } from './TopBar';
import { Sidebar } from './Sidebar';
import { StatusBar } from './StatusBar';
import { cn } from '../../utils/helpers';

interface AppShellProps {
  children: ReactNode;
}

export function AppShell({ children }: AppShellProps) {
  // NOSONAR — S6759: React props read-only; requires `readonly` refactor across component tree
  return (
    <div className="flex flex-col h-screen overflow-hidden bg-[var(--bg-primary)]">
      <TopBar />
      <div className="flex flex-1 overflow-hidden">
        <Sidebar />
        <main
          className={cn('flex-1 flex flex-col overflow-hidden min-w-0 transition-all duration-300')}
        >
          <div className="flex-1 overflow-y-auto">{children}</div>
          <StatusBar />
        </main>
      </div>
    </div>
  );
}
