import { createContext, useContext, useEffect, useState } from 'react'

type ThemeChoice = 'light'

interface ThemeState {
  choice: ThemeChoice
  resolved: 'light'
  setChoice: (choice: ThemeChoice) => void
}

const ThemeContext = createContext<ThemeState | null>(null)

export function ThemeProvider({ children }: { children: React.ReactNode }) {
  const [choice] = useState<ThemeChoice>('light')
  const resolved = 'light'

  useEffect(() => {
    const root = document.documentElement
    root.setAttribute('data-theme', 'light')
    root.style.colorScheme = 'light'
    try {
      localStorage.setItem('fraudmap_theme', 'light')
    } catch {
      // ignore
    }
  }, [])

  function setChoice() {
    // locked to light
  }

  return (
    <ThemeContext.Provider value={{ choice, resolved, setChoice }}>
      {children}
    </ThemeContext.Provider>
  )
}

export function useTheme() {
  const ctx = useContext(ThemeContext)
  if (!ctx) throw new Error('useTheme must be used within ThemeProvider')
  return ctx
}
