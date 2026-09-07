import axios from 'axios'
import { AlertCircle, Loader2, LogIn, Sparkles } from 'lucide-react'
import { useState } from 'react'
import { useLocation, useNavigate } from 'react-router-dom'
import { useAuth } from '../auth/AuthContext'
import { LogoMark } from '../components/Logo'
import { ThemeToggle } from '../components/ThemeToggle'

export function Login() {
  const { login } = useAuth()
  const navigate = useNavigate()
  const location = useLocation()
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [submitting, setSubmitting] = useState(false)

  const from = (location.state as { from?: string })?.from ?? '/'

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    setError(null)
    setSubmitting(true)
    try {
      await login(username, password)
      navigate(from, { replace: true })
    } catch (err) {
      if (axios.isAxiosError(err) && !err.response) {
        setError(
          err.code === 'ECONNABORTED'
            ? 'The server took too long to respond. Is the API running?'
            : 'Could not reach the server. Is the API running?',
        )
      } else {
        setError('Incorrect username or password.')
      }
    } finally {
      setSubmitting(false)
    }
  }

  const fillDemo = () => {
    setUsername('investigator')
    setPassword('changeme123')
    setError(null)
  }

  return (
    <div className="relative flex min-h-screen w-full items-center justify-center bg-ink-50 p-4 transition-colors duration-200">
      {/* Top Floating Theme Switcher */}
      <div className="absolute top-4 right-4 z-20 flex items-center gap-2">
        <ThemeToggle variant="surface" />
      </div>

      <div className="w-full max-w-[380px] animate-in fade-in zoom-in-95 duration-200">
        {/* Brand Header */}
        <div className="mb-6 flex items-center justify-center gap-3">
          <LogoMark size={38} className="text-brand-500" title="LedgerLens" />
          <div>
            <p className="text-xl font-bold tracking-tight text-ink-900">
              Ledger<span className="font-light text-brand-600 dark:text-brand-400">Lens</span>
            </p>
            <p className="text-[10px] font-semibold uppercase tracking-[0.16em] text-ink-500">
              Forensic Intelligence
            </p>
          </div>
        </div>

        {/* Main Card */}
        <div className="rounded-2xl border border-ink-200 bg-surface p-7 shadow-xl backdrop-blur-xs transition-colors duration-200">
          <div className="mb-5 border-b border-ink-100 pb-3">
            <h1 className="text-sm font-bold text-ink-900">Investigator Sign-in</h1>
            <p className="mt-0.5 text-xs text-ink-500">
              Access case files and blockchain attribution tools
            </p>
          </div>

          <form onSubmit={handleSubmit} className="space-y-4">
            <div>
              <label
                htmlFor="username"
                className="mb-1.5 block text-xs font-semibold uppercase tracking-wider text-ink-600"
              >
                Username
              </label>
              <input
                id="username"
                required
                autoFocus
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                placeholder="investigator"
                className="w-full rounded-lg border border-ink-200 bg-surface-sunk px-3.5 py-2.5 text-xs font-medium text-ink-900 placeholder:text-ink-400 outline-none transition-all focus:border-brand-500 focus:ring-2 focus:ring-brand-500/20"
              />
            </div>

            <div>
              <label
                htmlFor="password"
                className="mb-1.5 block text-xs font-semibold uppercase tracking-wider text-ink-600"
              >
                Password
              </label>
              <input
                id="password"
                required
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="••••••••••••"
                className="w-full rounded-lg border border-ink-200 bg-surface-sunk px-3.5 py-2.5 text-xs font-medium text-ink-900 placeholder:text-ink-400 outline-none transition-all focus:border-brand-500 focus:ring-2 focus:ring-brand-500/20"
              />
            </div>

            {error && (
              <div className="flex items-start gap-2 rounded-lg border border-critical/30 bg-critical-soft px-3 py-2.5 text-xs text-critical">
                <AlertCircle size={15} className="mt-0.5 shrink-0" />
                <span>{error}</span>
              </div>
            )}

            <button
              type="submit"
              disabled={submitting}
              className="flex w-full cursor-pointer items-center justify-center gap-2 rounded-lg bg-brand-500 py-2.5 px-4 text-xs font-bold text-white shadow-xs transition-all hover:bg-brand-600 active:scale-[0.99] disabled:cursor-not-allowed disabled:opacity-60"
            >
              {submitting ? <Loader2 size={15} className="animate-spin" /> : <LogIn size={15} />}
              {submitting ? 'Signing in…' : 'Sign In'}
            </button>
          </form>

          {/* Quick Demo Autofill */}
          <div className="mt-4 pt-3 border-t border-ink-100">
            <button
              type="button"
              onClick={fillDemo}
              className="flex w-full cursor-pointer items-center justify-center gap-1.5 rounded-lg border border-ink-200 bg-surface-sunk py-2 px-3 text-xs font-semibold text-ink-700 transition-colors hover:bg-ink-100 hover:text-ink-900"
            >
              <Sparkles size={13} className="text-brand-500" />
              <span>Fill Demo Credentials</span>
            </button>
          </div>
        </div>

        {/* Credentials reminder */}
        <p className="mt-4 text-center text-xs text-ink-500">
          Demo login: <span className="font-mono font-medium text-ink-700">investigator</span> /{' '}
          <span className="font-mono font-medium text-ink-700">changeme123</span>
        </p>
      </div>
    </div>
  )
}
