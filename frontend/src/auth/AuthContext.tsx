import { createContext, useContext, useEffect, useState } from 'react'
import { api } from '../api/client'

interface AuthUser {
  username: string
  role: 'investigator' | 'admin'
}

interface AuthState {
  user: AuthUser | null
  token: string | null
  loading: boolean
  login: (username: string, password: string) => Promise<void>
  logout: () => void
}

const AuthContext = createContext<AuthState | null>(null)

const TOKEN_KEY = 'fraudmap_token'
const USER_KEY = 'fraudmap_user'

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [token, setToken] = useState<string | null>(null)
  const [user, setUser] = useState<AuthUser | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    try {
      const storedToken = localStorage.getItem(TOKEN_KEY)
      const storedUser = localStorage.getItem(USER_KEY)
      if (storedToken && storedUser) {
        setToken(storedToken)
        setUser(JSON.parse(storedUser))
      }
    } catch {
      // localStorage unavailable (private mode etc) - just start logged out
    } finally {
      setLoading(false)
    }
  }, [])

  async function login(username: string, password: string) {
    const body = new URLSearchParams({ username, password })
    const { data } = await api.post('/auth/login', body, {
      headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
    })
    const authUser: AuthUser = { username: data.username, role: data.role }
    setToken(data.access_token)
    setUser(authUser)
    try {
      localStorage.setItem(TOKEN_KEY, data.access_token)
      localStorage.setItem(USER_KEY, JSON.stringify(authUser))
    } catch {
      // best-effort persistence only
    }
  }

  function logout() {
    setToken(null)
    setUser(null)
    try {
      localStorage.removeItem(TOKEN_KEY)
      localStorage.removeItem(USER_KEY)
    } catch {
      // ignore
    }
  }

  return (
    <AuthContext.Provider value={{ user, token, loading, login, logout }}>{children}</AuthContext.Provider>
  )
}

export function useAuth() {
  const ctx = useContext(AuthContext)
  if (!ctx) throw new Error('useAuth must be used within AuthProvider')
  return ctx
}

export function getStoredToken(): string | null {
  try {
    return localStorage.getItem(TOKEN_KEY)
  } catch {
    return null
  }
}

export function clearStoredAuth() {
  try {
    localStorage.removeItem(TOKEN_KEY)
    localStorage.removeItem(USER_KEY)
  } catch {
    // ignore
  }
}
