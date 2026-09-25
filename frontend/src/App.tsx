import React, { Component, useEffect, useState, type ReactNode } from 'react'
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
import { NetworkExplorer } from './pages/NetworkExplorer'
import { NewCase } from './pages/NewCase'
import { Overview } from './pages/Overview'
import { useTheme } from './theme/ThemeContext'

interface ErrorBoundaryProps {
  children: ReactNode
}

interface ErrorBoundaryState {
  hasError: boolean
  error: Error | null
}

class ErrorBoundary extends Component<ErrorBoundaryProps, ErrorBoundaryState> {
  constructor(props: ErrorBoundaryProps) {
    super(props)
    this.state = { hasError: false, error: null }
  }

  static getDerivedStateFromError(error: Error) {
    return { hasError: true, error }
  }

  componentDidCatch(error: Error, info: React.ErrorInfo) {
    console.error('ErrorBoundary caught:', error, info)
  }

  render() {
    if (this.state.hasError) {
      return (
        <div className="flex h-screen items-center justify-center p-6 text-center bg-ink-50">
          <div className="max-w-md rounded-xl border border-ink-200 bg-surface p-6 shadow-xs">
            <h2 className="text-base font-semibold text-ink-900">Something went wrong</h2>
            <p className="mt-2 text-xs text-ink-500">
              {this.state.error?.message || 'An unexpected error occurred while loading this view.'}
            </p>
            <button
              onClick={() => {
                this.setState({ hasError: false, error: null })
                window.location.reload()
              }}
              className="mt-4 cursor-pointer rounded-lg bg-brand-600 px-4 py-2 text-xs font-semibold text-white hover:bg-brand-500 transition-colors"
            >
              Reload Page
            </button>
          </div>
        </div>
      )
    }
    return this.props.children
  }
}

function AppShell() {
  const [paletteOpen, setPaletteOpen] = useState(false)
  const { resolved } = useTheme()

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
              <Route path="/network" element={<NetworkExplorer />} />
              <Route path="/new" element={<NewCase />} />
              <Route path="/bulk" element={<BulkUpload />} />
              <Route path="/cases/:caseId" element={<CaseDetail />} />
            </Routes>
          </main>
        </div>
      </div>
      <CommandPalette open={paletteOpen} onClose={() => setPaletteOpen(false)} />
      <Toaster theme={resolved} position="bottom-right" richColors closeButton />
    </ProtectedRoute>
  )
}

export default function App() {
  return (
    <ErrorBoundary>
      <Routes>
        <Route path="/login" element={<Login />} />
        <Route path="*" element={<AppShell />} />
      </Routes>
    </ErrorBoundary>
  )
}
