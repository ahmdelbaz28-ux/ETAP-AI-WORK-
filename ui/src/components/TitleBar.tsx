import { useState, useEffect } from 'react';
import { Minus, Square, X, Maximize2 } from 'lucide-react';
import { useTranslation } from 'react-i18next';

declare global {
  interface Window {
    electronAPI?: {
      minimize: () => Promise<void>;
      maximize: () => Promise<void>;
      close: () => Promise<void>;
      isMaximized: () => Promise<boolean>;
      onNavigate: (cb: (path: string) => void) => void;
    };
  }
}

export function TitleBar() {
  const { t } = useTranslation();
  const [isMaximized, setIsMaximized] = useState(false);
  const isElectron = !!globalThis.electronAPI;

  useEffect(() => {
    if (!isElectron) return;
    globalThis.electronAPI?.isMaximized().then(setIsMaximized);
    const interval = setInterval(async () => {
      if (globalThis.electronAPI) setIsMaximized(await globalThis.electronAPI.isMaximized());
    }, 1000);
    return () => clearInterval(interval);
  }, [isElectron]);

  if (!isElectron) return null;

  const handleMinimize = () => globalThis.electronAPI?.minimize();
  const handleMaximize = async () => {
    await globalThis.electronAPI?.maximize();
    setIsMaximized(await globalThis.electronAPI?.isMaximized());
  };
  const handleClose = () => globalThis.electronAPI?.close();

  return (
    <div
      className="h-9 flex items-center justify-between bg-[var(--bg-secondary)] border-b border-[var(--border-primary)] select-none"
      style={{ WebkitAppRegion: 'drag' } as React.CSSProperties}
    >
      {/* Left: App title */}
      <div className="flex items-center gap-2 px-4">
        <span className="text-xs font-semibold text-[var(--text-secondary)] tracking-wide">
          ⚡ {t('app.name')}
        </span>
      </div>

      {/* Right: Window controls */}
      <div
        className="flex items-center h-full"
        style={{ WebkitAppRegion: 'no-drag' } as React.CSSProperties}
      >
        <button
          onClick={handleMinimize}
          className="h-full px-3 flex items-center justify-center hover:bg-white/5 transition-colors"
          title="Minimize"
          aria-label="Minimize Window"
        >
          <Minus className="w-3.5 h-3.5 text-[var(--text-muted)]" />
        </button>
        <button
          onClick={handleMaximize}
          className="h-full px-3 flex items-center justify-center hover:bg-white/5 transition-colors"
          title={isMaximized ? 'Restore' : 'Maximize'}
          aria-label={isMaximized ? 'Restore Window' : 'Maximize Window'}
        >
          {isMaximized ? (
            <Square className="w-3 h-3 text-[var(--text-muted)]" />
          ) : (
            <Maximize2 className="w-3.5 h-3.5 text-[var(--text-muted)]" />
          )}
        </button>
        <button
          onClick={handleClose}
          className="h-full px-3 flex items-center justify-center hover:bg-red-500/80 group transition-colors"
          title="Close"
          aria-label="Close Window"
        >
          <X className="w-3.5 h-3.5 text-[var(--text-muted)] group-hover:text-white" />
        </button>
      </div>
    </div>
  );
}
