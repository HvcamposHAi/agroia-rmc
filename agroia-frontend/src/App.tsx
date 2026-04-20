import { BrowserRouter as Router, Routes, Route } from 'react-router-dom'
import Layout from './components/Layout'
import Chat from './pages/Chat'
import Dashboard from './pages/Dashboard'
import Consultas from './pages/Consultas'
import './index.css'

function App() {
  return (
    <Router>
      <Routes>
        <Route path="/" element={<Layout><Chat /></Layout>} />
        <Route path="/dashboard" element={<Layout><Dashboard /></Layout>} />
        <Route path="/consultas" element={<Layout><Consultas /></Layout>} />
      </Routes>
    </Router>
  )
}

export default App
