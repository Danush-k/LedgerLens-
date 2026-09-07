import { Navigate, useLocation } from 'react-router-dom'
import { LoadingRing } from '../components/Logo'
import { useAuth } from './AuthContext'

export function ProtectedRoute({ children }: { children: React.ReactNode }) {
  const { token, loading } = useAuth()
  const location = useLocation()

  // Reading localStorage is near-instant, but returning null means a blank
  // frame; the mark holds the space instead of flashing empty.
  if (loading) {
    return (
      <div className="flex h-screen items-center justify-center bg-ink-50">
        <LoadingRing size={44} />
      </div>
    )
  }
  if (!token) return <Navigate to="/login" state={{ from: location.pathname }} replace />
  return <>{children}</>
}
