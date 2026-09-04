import { Navigate, Route, Routes } from 'react-router-dom'
import DomainSelect from './pages/DomainSelect'
import Workspace from './pages/Workspace'
import Overview from './pages/Overview'
import Datasets from './pages/Datasets'
import Training from './pages/Training'
import Chat from './pages/Chat'
import Evaluation from './pages/Evaluation'
import Compare from './pages/Compare'
import Admin from './pages/Admin'

export default function App() {
  return (
    <Routes>
      <Route path="/" element={<DomainSelect />} />
      <Route path="/domain/:domainId" element={<Workspace />}>
        <Route index element={<Overview />} />
        <Route path="datasets" element={<Datasets />} />
        <Route path="training" element={<Training />} />
        <Route path="chat" element={<Chat />} />
        <Route path="evaluation" element={<Evaluation />} />
      </Route>
      <Route path="/compare" element={<Compare />} />
      <Route path="/admin" element={<Admin />} />
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  )
}
