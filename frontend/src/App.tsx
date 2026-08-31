import { Route, Routes } from 'react-router-dom'
import { ProtectedRoute } from './auth/ProtectedRoute'
import { Sidebar } from './components/Sidebar'
import { BulkUpload } from './pages/BulkUpload'
import { CaseDetail } from './pages/CaseDetail'
import { CaseList } from './pages/CaseList'
import { Login } from './pages/Login'
import { NewCase } from './pages/NewCase'
import { Overview } from './pages/Overview'

export default function App() {
  return (
    <Routes>
      <Route path="/login" element={<Login />} />
      <Route
        path="*"
        element={
          <ProtectedRoute>
            <div className="flex h-screen bg-ink-50">
              <Sidebar />
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
          </ProtectedRoute>
        }
      />
    </Routes>
  )
}
