import { BrowserRouter, Routes, Route, Navigate, useLocation } from 'react-router-dom'
import Layout from './components/Layout'
import Home from './pages/Home'
import Chat from './pages/Chat'
import Demanda from './pages/Demanda'
import Alertas from './pages/Alertas'
import Documentos from './pages/Documentos'
import Auditoria from './pages/Auditoria'
import Coleta from './pages/Coleta'
import Mercado from './pages/Mercado'
import Produtor from './pages/Produtor'
import Ofertas from './pages/Ofertas'

// Redireciona rotas antigas para /demanda preservando a query (?cultura=...&ano=...).
function RedirectToDemanda() {
  const { search } = useLocation()
  return <Navigate to={`/demanda${search}`} replace />
}

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<Layout />}>
          {/* Página inicial do portal = Assistente */}
          <Route index element={<Navigate to="/assistente" replace />} />
          <Route path="inicio" element={<Home />} />
          <Route path="assistente" element={<Chat />} />
          <Route path="demanda" element={<Demanda />} />
          <Route path="mercado" element={<Mercado />} />
          <Route path="ofertas" element={<Ofertas />} />
          <Route path="produtor" element={<Produtor />} />
          <Route path="documentos" element={<Documentos />} />
          <Route path="alertas" element={<Alertas />} />
          <Route path="auditoria" element={<Auditoria />} />
          <Route path="coleta" element={<Coleta />} />
          {/* Compatibilidade: rotas antigas → Demanda */}
          <Route path="dashboard" element={<RedirectToDemanda />} />
          <Route path="consultas" element={<RedirectToDemanda />} />
        </Route>
      </Routes>
    </BrowserRouter>
  )
}
