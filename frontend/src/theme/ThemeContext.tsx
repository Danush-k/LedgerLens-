import { createContext, useContext, useEffect, useState } from 'react'

type ThemeChoice = 'light' | 'dark' | 'system'

interface ThemeState {
  choice: ThemeChoice
  resolved: 'light' | 'dark'
  setChoice: (choice: ThemeChoice) => void
}

const ThemeContext = createContext<ThemeState | null>(null)
const STORAGE_KEY = 'fraudmap_theme'

function systemPrefersDark() {
  return window.matchMedia?.('(prefers-color-scheme: dark)').matches ?? false
}

export function ThemeProvider({ children }: { children: React.ReactNode }) {
  const [choice, setChoiceState] = useState<ThemeChoice>(() => {
    try {
      return (localStorage.getItem(STORAGE_KEY) as ThemeChoice) || 'system'
    } catch {
      return 'system'
    }
  })
  const [resolved, setResolved] = useState<'light' | 'dark'>(() =>
    choice === 'system' ? (systemPrefersDark() ? 'dark' : 'light') : (choice as 'light' | 'dark'),
  )

  useEffect(() => {
    const root = document.documentElement
    if (choice === 'system') {
      root.removeAttribute('data-theme')
      setResolved(systemPrefersDark() ? 'dark' : 'light')
    } else {
      root.setAttribute('data-theme', choice)
      setResolved(choice)
    }
  }, [choice])

  useEffect(() => {
    if (choice !== 'system') return
    const mq = window.matchMedia('(prefers-color-scheme: dark)')
    const handler = () => setResolved(mq.matches ? 'dark' : 'light')
    mq.addEventListener('change', handler)
    return () => mq.removeEventListener('change', handler)
  }, [choice])

  function setChoice(next: ThemeChoice) {
    setChoiceState(next)
    try {
      localStorage.setItem(STORAGE_KEY, next)
    } catch {
      // best-effort only
    }
  }

  return <ThemeContext.Provider value={{ choice, resolved, setChoice }}>{children}</ThemeContext.Provider>
}

export function useTheme() {
  const ctx = useContext(ThemeContext)
  if (!ctx) throw new Error('useTheme must be used within ThemeProvider')
  return ctx
}
