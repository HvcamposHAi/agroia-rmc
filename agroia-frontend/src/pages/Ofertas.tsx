import { useNavigate } from 'react-router-dom'

// Exemplos de consultas voltadas ao GESTOR da prefeitura. Cada chip abre o
// Assistente já com a pergunta (deep-link /assistente?q=…, que dispara sozinho).
const CONSULTAS_GESTOR = [
  { icon: '🧺', q: 'Quais produtos a agricultura familiar tem disponível para venda?' },
  { icon: '🥬', q: 'Quais hortaliças a prefeitura mais comprou nos últimos dois anos?' },
  { icon: '🍅', q: 'Qual o preço de referência da CEASA-PR para o tomate hoje?' },
  { icon: '⚖️', q: 'O preço pago pela prefeitura está acima do atacado da CEASA?' },
  { icon: '💵', q: 'Quanto a prefeitura gastou com agricultura familiar em 2024?' },
  { icon: '🌾', q: 'Qual canal compra mais da agricultura familiar?' },
  { icon: '👥', q: 'Quantos produtores forneceram alimentos nos últimos anos?' },
  { icon: '📈', q: 'Qual cultura está com melhor preço esta semana na CEASA?' },
]

export default function Ofertas() {
  const navigate = useNavigate()
  const consultar = (q: string) => navigate(`/assistente?q=${encodeURIComponent(q)}`)

  return (
    <div className="page">
      <div style={{ marginBottom: 12 }}>
        <h2 style={{ margin: '0 0 2px', fontFamily: 'Inter, sans-serif', color: 'var(--texto)' }}>Ofertas da agricultura familiar</h2>
        <p style={{ margin: 0, fontSize: 13, color: 'var(--texto-suave)' }}>
          Consulte a oferta e a demanda da agricultura familiar em linguagem natural.
        </p>
      </div>

      <div className="chat-welcome">
        <span className="welcome-icon">🧺</span>
        <h3>Exemplos de consultas para o gestor</h3>
        <p>
          Clique em uma pergunta para consultar no Assistente: disponibilidade da agricultura
          familiar, demanda da prefeitura e preços de referência da CEASA-PR.
        </p>
        <div className="suggestions">
          {CONSULTAS_GESTOR.map(c => (
            <button key={c.q} className="suggestion-btn" onClick={() => consultar(c.q)}>
              {c.icon} {c.q}
            </button>
          ))}
        </div>
      </div>
    </div>
  )
}
