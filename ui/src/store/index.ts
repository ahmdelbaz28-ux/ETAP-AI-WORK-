import { create } from 'zustand'

interface AppState {
  sidebarCollapsed: boolean
  toggleSidebar: () => void
  setSidebarCollapsed: (collapsed: boolean) => void
  language: 'en' | 'ar'
  setLanguage: (lang: 'en' | 'ar') => void
  searchQuery: string
  setSearchQuery: (query: string) => void
}

export const useAppStore = create<AppState>((set) => ({
  sidebarCollapsed: false,
  toggleSidebar: () => set((state) => ({ sidebarCollapsed: !state.sidebarCollapsed })),
  setSidebarCollapsed: (collapsed) => set({ sidebarCollapsed: collapsed }),
  language: (localStorage.getItem('i18nextLng') as 'en' | 'ar') || 'en',
  setLanguage: (language) => set({ language }),
  searchQuery: '',
  setSearchQuery: (searchQuery) => set({ searchQuery }),
}))
