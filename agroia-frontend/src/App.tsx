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
import BenchmarkMotores from './pages/BenchmarkMotores'

// Redireciona rotas antigas preservando a query (?cultura=...&ano=..., ?q=...).
function RedirectPreservando({ para }: { para: string }) {
  const { search } = useLocation()
  return <Navigate to={`${para}${search}`} replace />
}

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<Layout />}>
          {/* Página inicial do portal = Início (visão institucional + atalhos por público) */}
          <Route index element={<Navigate to="/inicio" replace />} />
          <Route path="inicio" element={<Home />} />
          <Route path="assistente" element={<Chat />} />
          <Route path="demanda" element={<Demanda />} />
          <Route path="mercado" element={<Mercado />} />
          <Route path="produtor" element={<Produtor />} />
          <Route path="documentos" element={<Documentos />} />
          <Route path="alertas" element={<Alertas />} />
          <Route path="auditoria" element={<Auditoria />} />
          <Route path="benchmark" element={<BenchmarkMotores />} />
          <Route path="coleta" element={<Coleta />} />
          {/* Compatibilidade: rotas antigas */}
          <Route path="dashboard" element={<RedirectPreservando para="/demanda" />} />
          <Route path="consultas" element={<RedirectPreservando para="/demanda" />} />
          {/* "Ofertas" era o mesmo chat do Assistente com outros exemplos — unificado */}
          <Route path="ofertas" element={<RedirectPreservando para="/assistente" />} />
        </Route>
      </Routes>
    </BrowserRouter>
  )
}
