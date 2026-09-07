import axios from 'axios'
import { Loader2, LogIn } from 'lucide-react'
import { useState } from 'react'
import { useLocation, useNavigate } from 'react-router-dom'
import { useAuth } from '../auth/AuthContext'
import { LogoMark } from '../components/Logo'

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

  return (
    <div className="flex h-screen items-center justify-center bg-[#131b24] px-4">
      <div className="w-full max-w-[360px]">
        <div className="mb-5 flex items-center gap-3">
          <LogoMark size={34} className="text-brand-400" title="LedgerLens" />
          <div>
            <p className="text-[17px] font-semibold tracking-[-0.01em] text-[#e6ecf3]">
              Ledger<span className="font-normal">Lens</span>
            </p>
            <p className="mt-0.5 text-[10px] uppercase tracking-[0.14em] text-[#6c7a8a]">
              Fraud attribution
            </p>
          </div>
        </div>

        <div className="rounded border border-[#2c3742] bg-[#1c262f] p-6">
          <p className="mb-4 text-[13px] font-medium text-[#93a2b3]">Investigator sign-in</p>

          <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label className="mb-1.5 block text-[11px] font-medium uppercase tracking-wide text-[#93a2b3]">Username</label>
            <input
              required
              autoFocus
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              className="w-full rounded border border-[#2c3742] bg-[#131b24] px-3 py-2 text-[13px] text-[#e6ecf3] outline-none focus:border-brand-400"
            />
          </div>
          <div>
            <label className="mb-1.5 block text-[11px] font-medium uppercase tracking-wide text-[#93a2b3]">Password</label>
            <input
              required
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              className="w-full rounded border border-[#2c3742] bg-[#131b24] px-3 py-2 text-[13px] text-[#e6ecf3] outline-none focus:border-brand-400"
            />
          </div>

          {error && (
            <p className="rounded border border-[#5a2a26] bg-[#2e1614] px-3 py-2 text-xs text-[#f2867c]">
              {error}
            </p>
          )}

          <button
            type="submit"
            disabled={submitting}
            className="flex w-full cursor-pointer items-center justify-center gap-2 rounded bg-brand-500 px-4 py-2 text-[13px] font-medium text-white transition-colors hover:bg-brand-600 disabled:cursor-not-allowed disabled:opacity-60"
          >
            {submitting ? <Loader2 size={16} className="animate-spin" /> : <LogIn size={16} />}
            {submitting ? 'Signing in…' : 'Sign in'}
          </button>
        </form>

        </div>

        <p className="mt-4 text-[11px] leading-relaxed text-[#6c7a8a]">
          Demo credentials <code className="text-[#93a2b3]">investigator</code> /{' '}
          <code className="text-[#93a2b3]">changeme123</code>. Change these before any
          deployment beyond this machine.
        </p>
      </div>
    </div>
  )
}
