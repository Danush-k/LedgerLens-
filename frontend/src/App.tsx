import { useEffect, useState } from 'react'
import { Route, Routes } from 'react-router-dom'
import { Toaster } from 'sonner'
import { ProtectedRoute } from './auth/ProtectedRoute'
import { CommandPalette } from './components/CommandPalette'
import { Sidebar } from './components/Sidebar'
import { TopBar } from './components/TopBar'
import { BulkUpload } from './pages/BulkUpload'
import { CaseDetail } from './pages/CaseDetail'
import { CaseList } from './pages/CaseList'
import { Login } from './pages/Login'
import { NewCase } from './pages/NewCase'
import { Overview } from './pages/Overview'
function AppShell() {
  const [paletteOpen, setPaletteOpen] = useState(false)

  useEffect(() => {
    function handleKeydown(e: KeyboardEvent) {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === 'k') {
        e.preventDefault()
        setPaletteOpen((prev) => !prev)
      }
    }
    document.addEventListener('keydown', handleKeydown)
    return () => document.removeEventListener('keydown', handleKeydown)
  }, [])

  return (
    <ProtectedRoute>
      <div className="flex h-screen bg-ink-50">
        <Sidebar />
        <div className="flex flex-1 flex-col overflow-hidden">
          <TopBar onOpenPalette={() => setPaletteOpen(true)} />
          <main className="flex-1 overflow-y-auto">
            <Routes>
              <Route path="/" element={<Overview />} />
              <Route path="/cases" element={<CaseList />} />
              <Route path="/new" element={<NewCase />} />
              <Route path="/bulk" element={<BulkUpload />} />
              <Route path="/cases/:caseId" element={<CaseDetail />} />
            </Routes>
          </main>
        </div>
      </div>
      <CommandPalette open={paletteOpen} onClose={() => setPaletteOpen(false)} />
      <Toaster theme="light" position="bottom-right" richColors closeButton />
    </ProtectedRoute>
  )
}

export default function App() {
  return (
    <Routes>
      <Route path="/login" element={<Login />} />
      <Route path="*" element={<AppShell />} />
    </Routes>
  )
}
