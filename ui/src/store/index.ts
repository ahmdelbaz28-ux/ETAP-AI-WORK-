import { create } from 'zustand';

interface ContextItem {
  label: string;
  value: string | number | React.ReactNode;
  icon?: React.ElementType;
}

interface SelectedItem {
  type: string;
  name: string;
  details?: ContextItem[];
}

interface AppState {
  // Sidebar
  sidebarCollapsed: boolean;
  toggleSidebar: () => void;
  setSidebarCollapsed: (collapsed: boolean) => void;
  // Mobile sidebar (drawer overlay)
  mobileSidebarOpen: boolean;
  toggleMobileSidebar: () => void;
  setMobileSidebarOpen: (open: boolean) => void;

  // Language
  language: 'en' | 'ar';
  setLanguage: (lang: 'en' | 'ar') => void;

  // Search
  searchQuery: string;
  setSearchQuery: (query: string) => void;

  // Command Palette
  commandPaletteOpen: boolean;
  setCommandPaletteOpen: (open: boolean) => void;
  toggleCommandPalette: () => void;

  // Context Panel
  contextPanelOpen: boolean;
  setContextPanelOpen: (open: boolean) => void;
  selectedItem: SelectedItem | null;
  setSelectedItem: (item: SelectedItem | null) => void;

  // Help Panel
  helpPanelOpen: boolean;
  setHelpPanelOpen: (open: boolean) => void;
  toggleHelpPanel: () => void;

  // Error state
  lastError: Error | string | null;
  setLastError: (error: Error | string | null) => void;
}

export const useAppStore = create<AppState>((set) => ({
  // Sidebar
  sidebarCollapsed: false,
  toggleSidebar: () => set((state) => ({ sidebarCollapsed: !state.sidebarCollapsed })),
  setSidebarCollapsed: (collapsed) => set({ sidebarCollapsed: collapsed }),
  // Mobile sidebar (drawer overlay) — separate from desktop collapse state
  mobileSidebarOpen: false,
  toggleMobileSidebar: () => set((state) => ({ mobileSidebarOpen: !state.mobileSidebarOpen })),
  setMobileSidebarOpen: (open) => set({ mobileSidebarOpen: open }),

  // Language
  language: (localStorage.getItem('i18nextLng') as 'en' | 'ar') || 'en',
  setLanguage: (language) => set({ language }),

  // Search
  searchQuery: '',
  setSearchQuery: (searchQuery) => set({ searchQuery }),

  // Command Palette
  commandPaletteOpen: false,
  setCommandPaletteOpen: (commandPaletteOpen) => set({ commandPaletteOpen }),
  toggleCommandPalette: () => set((state) => ({ commandPaletteOpen: !state.commandPaletteOpen })),

  // Context Panel
  contextPanelOpen: false,
  setContextPanelOpen: (contextPanelOpen) => set({ contextPanelOpen }),
  selectedItem: null,
  setSelectedItem: (selectedItem) => set({ selectedItem, contextPanelOpen: selectedItem !== null }),

  // Help Panel
  helpPanelOpen: false,
  setHelpPanelOpen: (helpPanelOpen) => set({ helpPanelOpen }),
  toggleHelpPanel: () => set((state) => ({ helpPanelOpen: !state.helpPanelOpen })),

  // Error state
  lastError: null,
  setLastError: (lastError) => set({ lastError }),
}));
