import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { Header } from './components/layout/Header'
import { Footer } from './components/layout/Footer'
import { MainContent } from './components/layout/MainContent'
import { AlbumCreator } from './components/features/AlbumCreator'
import { GenerationProgress } from './components/features/GenerationProgress'
import { AlbumResult } from './components/features/AlbumResult'
import { PlanReview } from './components/features/PlanReview'
import { useNavigationStore } from './stores/navigation.store'

const queryClient = new QueryClient({
  defaultOptions: {
    queries: { staleTime: 30_000, retry: 1 },
  },
})

function AppShell() {
  const currentView = useNavigationStore((s) => s.currentView)
  const setView = useNavigationStore((s) => s.setView)

  const viewMap: Record<string, React.ReactNode> = {
    home: <AlbumCreator />,
    generating: <GenerationProgress />,
    review: <PlanReview />,
    result: <AlbumResult />,
  }

  return (
    <div className="min-h-svh flex flex-col bg-background">
      <Header onNavigate={setView} currentView={currentView} />
      <MainContent viewKey={currentView}>
        {viewMap[currentView] ?? <AlbumCreator />}
      </MainContent>
      <Footer />
    </div>
  )
}

export default function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <AppShell />
    </QueryClientProvider>
  )
}
