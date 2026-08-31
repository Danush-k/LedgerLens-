import { Navigate, useLocation } from 'react-router-dom'
import { useAuth } from './AuthContext'

export function ProtectedRoute({ children }: { children: React.ReactNode }) {
  const { token, loading } = useAuth()
  const location = useLocation()

  if (loading) return null // avoid a login-page flash while localStorage is read
  if (!token) return <Navigate to="/login" state={{ from: location.pathname }} replace />
  return <>{children}</>
}
