import { useState, useRef, useCallback, useEffect, type ReactNode } from 'react';
import { cn } from '../../utils/helpers';
import { GripVertical, PanelLeftClose, PanelRightClose } from 'lucide-react';

interface EngineeringWorkspaceProps {
  leftPanel?: ReactNode;
  centerPanel: ReactNode;
  rightPanel?: ReactNode;
  leftTitle?: string;
  rightTitle?: string;
  defaultLeftWidth?: number;
  defaultRightWidth?: number;
  minPanelWidth?: number;
}

export function EngineeringWorkspace({
  // NOSONAR — S6759: React props read-only; requires `readonly` refactor across component tree
  leftPanel,
  centerPanel,
  rightPanel,
  leftTitle = 'Navigator',
  rightTitle = 'Properties',
  defaultLeftWidth = 260,
  defaultRightWidth = 300,
  minPanelWidth = 180,
}: EngineeringWorkspaceProps) {
  const [leftWidth, setLeftWidth] = useState(defaultLeftWidth);
  const [rightWidth, setRightWidth] = useState(defaultRightWidth);
  const [leftCollapsed, setLeftCollapsed] = useState(false);
  const [rightCollapsed, setRightCollapsed] = useState(!rightPanel);
  const [dragging, setDragging] = useState<'left' | 'right' | null>(null);
  const containerRef = useRef<HTMLDivElement>(null);

  const handleMouseDown = useCallback(
    (panel: 'left' | 'right') => (e: React.MouseEvent) => {
      e.preventDefault();
      setDragging(panel);
    },
    [],
  );

  useEffect(() => {
    if (!dragging) return;

    const handleMouseMove = (e: MouseEvent) => {
      if (!containerRef.current) return;
      const rect = containerRef.current.getBoundingClientRect();

      if (dragging === 'left') {
        const newWidth = Math.max(
          minPanelWidth,
          Math.min(e.clientX - rect.left, rect.width - rightWidth - 100),
        );
        setLeftWidth(newWidth);
      } else if (dragging === 'right') {
        const newWidth = Math.max(
          minPanelWidth,
          Math.min(rect.right - e.clientX, rect.width - leftWidth - 100),
        );
        setRightWidth(newWidth);
      }
    };

    const handleMouseUp = () => setDragging(null);

    document.addEventListener('mousemove', handleMouseMove);
    document.addEventListener('mouseup', handleMouseUp);
    document.body.style.cursor = 'col-resize';
    document.body.style.userSelect = 'none';

    return () => {
      document.removeEventListener('mousemove', handleMouseMove);
      document.removeEventListener('mouseup', handleMouseUp);
      document.body.style.cursor = '';
      document.body.style.userSelect = '';
    };
  }, [dragging, leftWidth, rightWidth, minPanelWidth]);

  return (
    <div ref={containerRef} className="flex h-full overflow-hidden">
      {/* Left Panel */}
      {leftPanel && (
        <>
          <div
            className={cn(
              'shrink-0 flex flex-col bg-[var(--bg-secondary)] border-r border-[var(--border-primary)] overflow-hidden transition-all duration-200',
              leftCollapsed ? 'w-10' : '',
            )}
            style={leftCollapsed ? {} : { width: leftWidth }}
          >
            {leftCollapsed ? (
              <div className="flex flex-col items-center py-2 gap-2">
                <button
                  onClick={() => setLeftCollapsed(false)}
                  className="p-1.5 rounded-lg hover:bg-[var(--bg-elevated)] text-[var(--text-muted)] hover:text-[var(--text-primary)] transition-colors"
                  title="Expand panel"
                >
                  <PanelLeftClose className="w-4 h-4 rotate-180" />
                </button>
              </div>
            ) : (
              <>
                <div className="flex items-center justify-between px-3 py-2 border-b border-[var(--border-primary)]">
                  <span className="text-xs font-semibold text-[var(--text-muted)] uppercase tracking-wider">
                    {leftTitle}
                  </span>
                  <button
                    onClick={() => setLeftCollapsed(true)}
                    className="p-1 rounded hover:bg-[var(--bg-elevated)] text-[var(--text-muted)] hover:text-[var(--text-primary)] transition-colors"
                    title="Collapse panel"
                  >
                    <PanelLeftClose className="w-3.5 h-3.5" />
                  </button>
                </div>
                <div className="flex-1 overflow-y-auto">{leftPanel}</div>
              </>
            )}
          </div>

          {/* Left Resize Handle */}
          {!leftCollapsed && (
            <div // NOSONAR — S6848: non-interactive DOM role; intentional
              onMouseDown={handleMouseDown('left')}
              className={cn(
                'w-1 shrink-0 cursor-col-resize group flex items-center justify-center hover:bg-[var(--accent-primary)]/30 transition-colors',
                dragging === 'left' && 'bg-[var(--accent-primary)]/30',
              )}
            >
              <GripVertical className="w-3 h-3 text-[var(--text-muted)] opacity-0 group-hover:opacity-100 transition-opacity" />
            </div>
          )}
        </>
      )}

      {/* Center Panel */}
      <div className="flex-1 overflow-auto min-w-0">{centerPanel}</div>

      {/* Right Panel */}
      {rightPanel && (
        <>
          {/* Right Resize Handle */}
          {!rightCollapsed && (
            <div // NOSONAR — S6848: non-interactive DOM role; intentional
              onMouseDown={handleMouseDown('right')}
              className={cn(
                'w-1 shrink-0 cursor-col-resize group flex items-center justify-center hover:bg-[var(--accent-primary)]/30 transition-colors',
                dragging === 'right' && 'bg-[var(--accent-primary)]/30',
              )}
            >
              <GripVertical className="w-3 h-3 text-[var(--text-muted)] opacity-0 group-hover:opacity-100 transition-opacity" />
            </div>
          )}

          <div
            className={cn(
              'shrink-0 flex flex-col bg-[var(--bg-secondary)] border-l border-[var(--border-primary)] overflow-hidden transition-all duration-200',
              rightCollapsed ? 'w-10' : '',
            )}
            style={rightCollapsed ? {} : { width: rightWidth }}
          >
            {rightCollapsed ? (
              <div className="flex flex-col items-center py-2 gap-2">
                <button
                  onClick={() => setRightCollapsed(false)}
                  className="p-1.5 rounded-lg hover:bg-[var(--bg-elevated)] text-[var(--text-muted)] hover:text-[var(--text-primary)] transition-colors"
                  title="Expand panel"
                >
                  <PanelRightClose className="w-4 h-4 rotate-180" />
                </button>
              </div>
            ) : (
              <>
                <div className="flex items-center justify-between px-3 py-2 border-b border-[var(--border-primary)]">
                  <span className="text-xs font-semibold text-[var(--text-muted)] uppercase tracking-wider">
                    {rightTitle}
                  </span>
                  <button
                    onClick={() => setRightCollapsed(true)}
                    className="p-1 rounded hover:bg-[var(--bg-elevated)] text-[var(--text-muted)] hover:text-[var(--text-primary)] transition-colors"
                    title="Collapse panel"
                  >
                    <PanelRightClose className="w-3.5 h-3.5" />
                  </button>
                </div>
                <div className="flex-1 overflow-y-auto">{rightPanel}</div>
              </>
            )}
          </div>
        </>
      )}
    </div>
  );
}
