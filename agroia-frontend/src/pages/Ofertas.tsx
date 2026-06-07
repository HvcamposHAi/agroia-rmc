import Chat from './Chat'

// Exemplos de consultas voltadas ao GESTOR da prefeitura. Reutiliza o mesmo
// componente de chat do Assistente (campo de chat + agente), só trocando os
// chips de exemplo e o texto de boas-vindas.
const CONSULTAS_GESTOR = [
  '🧺 Quais produtos a agricultura familiar tem disponível para venda?',
  '🥬 Quais hortaliças a prefeitura mais comprou nos últimos dois anos?',
  '🍅 Qual o preço de referência da CEASA-PR para o tomate hoje?',
  '⚖️ O preço pago pela prefeitura está acima do atacado da CEASA?',
  '💵 Quanto a prefeitura gastou com agricultura familiar em 2024?',
  '🌾 Qual canal compra mais da agricultura familiar?',
  '👥 Quantos produtores forneceram alimentos nos últimos anos?',
  '📈 Qual cultura está com melhor preço esta semana na CEASA?',
]

export default function Ofertas() {
  return (
    <Chat
      suggestions={CONSULTAS_GESTOR}
      welcomeIcon="🧺"
      welcomeTitle="Exemplos de consultas para o gestor"
      welcomeText="Clique em uma pergunta ou escreva a sua: disponibilidade da agricultura familiar, demanda da prefeitura e preços de referência da CEASA-PR."
    />
  )
}
