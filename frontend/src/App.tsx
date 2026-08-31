import { Route, Routes } from 'react-router-dom'
import { Sidebar } from './components/Sidebar'
import { CaseDetail } from './pages/CaseDetail'
import { CaseList } from './pages/CaseList'
import { NewCase } from './pages/NewCase'

export default function App() {
  return (
    <div className="flex h-screen bg-ink-50">
      <Sidebar />
      <main className="flex-1 overflow-y-auto">
        <Routes>
          <Route path="/" element={<CaseList />} />
          <Route path="/new" element={<NewCase />} />
          <Route path="/cases/:caseId" element={<CaseDetail />} />
        </Routes>
      </main>
    </div>
  )
}
