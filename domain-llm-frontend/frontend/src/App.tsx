import { createContext, useContext, useState, ReactNode } from 'react'
import { Navigate, Route, Routes, useLocation } from 'react-router-dom'
import Login from './pages/Login'
import DomainSelect from './pages/DomainSelect'
import Workspace from './pages/Workspace'
import Overview from './pages/Overview'
import Datasets from './pages/Datasets'
import Training from './pages/Training'
import Chat from './pages/Chat'
import Evaluation from './pages/Evaluation'
import Compare from './pages/Compare'
import Admin from './pages/Admin'

export interface User {
  name: string
  role: 'user' | 'admin'
}

const UserContext = createContext<{ user: User | null; login: (u: User) => void; logout: () => void }>({
  user: null,
  login: () => {},
  logout: () => {},
})

export const useUser = () => useContext(UserContext)

function RequireAuth({ children }: { children: ReactNode }) {
  const { user } = useUser()
  const loc = useLocation()
  if (!user) return <Navigate to="/login" state={{ from: loc.pathname }} replace />
  return <>{children}</>
}

export default function App() {
  const saved = sessionStorage.getItem('dw-user')
  const [user, setUser] = useState<User | null>(saved ? JSON.parse(saved) : null)

  const login = (u: User) => {
    setUser(u)
    sessionStorage.setItem('dw-user', JSON.stringify(u))
  }
  const logout = () => {
    setUser(null)
    sessionStorage.removeItem('dw-user')
  }

  return (
    <UserContext.Provider value={{ user, login, logout }}>
      <Routes>
        <Route path="/login" element={<Login />} />
        <Route path="/" element={<RequireAuth><DomainSelect /></RequireAuth>} />
        <Route path="/domain/:domainId" element={<RequireAuth><Workspace /></RequireAuth>}>
          <Route index element={<Overview />} />
          <Route path="datasets" element={<Datasets />} />
          <Route path="training" element={<Training />} />
          <Route path="chat" element={<Chat />} />
          <Route path="evaluation" element={<Evaluation />} />
        </Route>
        <Route path="/compare" element={<RequireAuth><Compare /></RequireAuth>} />
        <Route path="/admin" element={<RequireAuth><Admin /></RequireAuth>} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </UserContext.Provider>
  )
}
