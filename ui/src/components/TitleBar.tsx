<<<<<<< HEAD
import { Maximize2, Minus, Square, X } from "lucide-react";
import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
=======
import { useState, useEffect } from 'react'
import { Minus, Square, X, Maximize2 } from 'lucide-react'
import { useTranslation } from 'react-i18next'
import { cn } from '../utils/helpers'
>>>>>>> origin/fix/scenario-tests-properly

declare global {
  interface Window {
    electronAPI?: {
<<<<<<< HEAD
      minimize: () => Promise<void>;
      maximize: () => Promise<void>;
      close: () => Promise<void>;
      isMaximized: () => Promise<boolean>;
      onNavigate: (cb: (path: string) => void) => void;
    };
=======
      minimize: () => Promise<void>
      maximize: () => Promise<void>
      close: () => Promise<void>
      isMaximized: () => Promise<boolean>
      onNavigate: (cb: (path: string) => void) => void
    }
>>>>>>> origin/fix/scenario-tests-properly
  }
}

export function TitleBar() {
<<<<<<< HEAD
  const { t } = useTranslation();
  const [isMaximized, setIsMaximized] = useState(false);
  const isElectron = !!window.electronAPI;

  useEffect(() => {
    if (!isElectron) return;
    window.electronAPI?.isMaximized().then(setIsMaximized);
    const interval = setInterval(async () => {
      if (window.electronAPI) setIsMaximized(await window.electronAPI.isMaximized());
    }, 1000);
    return () => clearInterval(interval);
  }, [isElectron]);

  if (!isElectron) return null;

  const handleMinimize = () => window.electronAPI?.minimize();
  const handleMaximize = async () => {
    await window.electronAPI?.maximize();
    setIsMaximized((await window.electronAPI?.isMaximized()) ?? false);
  };
  const handleClose = () => window.electronAPI?.close();

  return (
    <div
      className="h-9 flex items-center justify-between bg-[var(--bg-secondary)] border-b border-[var(--border-primary)] select-none"
      style={{ WebkitAppRegion: "drag" } as React.CSSProperties}
=======
  const { t } = useTranslation()
  const [isMaximized, setIsMaximized] = useState(false)
  const isElectron = !!window.electronAPI

  useEffect(() => {
    if (!isElectron) return
    window.electronAPI!.isMaximized().then(setIsMaximized)
    const interval = setInterval(async () => {
      if (window.electronAPI) setIsMaximized(await window.electronAPI.isMaximized())
    }, 1000)
    return () => clearInterval(interval)
  }, [isElectron])

  if (!isElectron) return null

  const handleMinimize = () => window.electronAPI?.minimize()
  const handleMaximize = async () => {
    await window.electronAPI?.maximize()
    setIsMaximized(await window.electronAPI!.isMaximized())
  }
  const handleClose = () => window.electronAPI?.close()

  return (
    <div className="h-9 flex items-center justify-between bg-[var(--bg-secondary)] border-b border-[var(--border-primary)] select-none"
      style={{ WebkitAppRegion: 'drag' } as React.CSSProperties}
>>>>>>> origin/fix/scenario-tests-properly
    >
      {/* Left: App title */}
      <div className="flex items-center gap-2 px-4">
        <span className="text-xs font-semibold text-[var(--text-secondary)] tracking-wide">
<<<<<<< HEAD
          ⚡ {t("app.name")}
=======
          ⚡ {t('app.name')}
>>>>>>> origin/fix/scenario-tests-properly
        </span>
      </div>

      {/* Right: Window controls */}
<<<<<<< HEAD
      <div
        className="flex items-center h-full"
        style={{ WebkitAppRegion: "no-drag" } as React.CSSProperties}
      >
        <button
          type="button"
          onClick={handleMinimize}
          className="h-full px-3 flex items-center justify-center hover:bg-white/5 transition-colors"
          title="Minimize"
          aria-label="Minimize Window"
=======
      <div className="flex items-center h-full" style={{ WebkitAppRegion: 'no-drag' } as React.CSSProperties}>
        <button
          onClick={handleMinimize}
          className="h-full px-3 flex items-center justify-center hover:bg-white/5 transition-colors"
          title="Minimize"
>>>>>>> origin/fix/scenario-tests-properly
        >
          <Minus className="w-3.5 h-3.5 text-[var(--text-muted)]" />
        </button>
        <button
<<<<<<< HEAD
          type="button"
          onClick={handleMaximize}
          className="h-full px-3 flex items-center justify-center hover:bg-white/5 transition-colors"
          title={isMaximized ? "Restore" : "Maximize"}
          aria-label={isMaximized ? "Restore Window" : "Maximize Window"}
        >
          {isMaximized ? (
            <Square className="w-3 h-3 text-[var(--text-muted)]" />
          ) : (
            <Maximize2 className="w-3.5 h-3.5 text-[var(--text-muted)]" />
          )}
        </button>
        <button
          type="button"
          onClick={handleClose}
          className="h-full px-3 flex items-center justify-center hover:bg-red-500/80 group transition-colors"
          title="Close"
          aria-label="Close Window"
=======
          onClick={handleMaximize}
          className="h-full px-3 flex items-center justify-center hover:bg-white/5 transition-colors"
          title={isMaximized ? 'Restore' : 'Maximize'}
        >
          {isMaximized
            ? <Square className="w-3 h-3 text-[var(--text-muted)]" />
            : <Maximize2 className="w-3.5 h-3.5 text-[var(--text-muted)]" />
          }
        </button>
        <button
          onClick={handleClose}
          className="h-full px-3 flex items-center justify-center hover:bg-red-500/80 group transition-colors"
          title="Close"
>>>>>>> origin/fix/scenario-tests-properly
        >
          <X className="w-3.5 h-3.5 text-[var(--text-muted)] group-hover:text-white" />
        </button>
      </div>
    </div>
<<<<<<< HEAD
  );
=======
  )
>>>>>>> origin/fix/scenario-tests-properly
}
