import { create } from 'zustand'

export type View = 'home' | 'generating' | 'review' | 'result'

interface NavigationStore {
  currentView: View
  setView: (view: View) => void
}

export const useNavigationStore = create<NavigationStore>((set) => ({
  currentView: 'home',
  setView: (view) => set({ currentView: view }),
}))
