import Chat from './Chat'
import { defineMessages, useI18n, useT } from '../i18n'
import type { Lang } from '../i18n'

// Exemplos de consultas voltadas ao GESTOR da prefeitura. Reutiliza o mesmo
// componente de chat do Assistente (campo de chat + agente), só trocando os
// chips de exemplo e o texto de boas-vindas.
const CONSULTAS_GESTOR: Record<Lang, string[]> = {
  pt: [
    '🧺 Quais produtos a agricultura familiar tem disponível para venda?',
    '🥬 Quais hortaliças a prefeitura mais comprou nos últimos dois anos?',
    '🍅 Qual o preço de referência da CEASA-PR para o tomate hoje?',
    '⚖️ O preço pago pela prefeitura está acima do atacado da CEASA?',
    '💵 Quanto a prefeitura gastou com agricultura familiar em 2024?',
    '🌾 Qual canal compra mais da agricultura familiar?',
    '👥 Quantos produtores forneceram alimentos nos últimos anos?',
    '📈 Qual cultura está com melhor preço esta semana na CEASA?',
  ],
  en: [
    '🧺 Which products do family farmers have available for sale?',
    '🥬 Which vegetables did the city buy most in the last two years?',
    "🍅 What is CEASA-PR's reference price for tomatoes today?",
    '⚖️ Is the price paid by the city above the CEASA wholesale price?',
    '💵 How much did the city spend on family farming in 2024?',
    '🌾 Which channel buys the most from family farming?',
    '👥 How many farmers have supplied food in recent years?',
    '📈 Which crop has the best price at CEASA this week?',
  ],
  es: [
    '🧺 ¿Qué productos tiene disponibles para la venta la agricultura familiar?',
    '🥬 ¿Qué hortalizas compró más la alcaldía en los últimos dos años?',
    '🍅 ¿Cuál es el precio de referencia de la CEASA-PR para el tomate hoy?',
    '⚖️ ¿El precio pagado por la alcaldía está por encima del mayorista de la CEASA?',
    '💵 ¿Cuánto gastó la alcaldía en agricultura familiar en 2024?',
    '🌾 ¿Qué canal compra más a la agricultura familiar?',
    '👥 ¿Cuántos productores suministraron alimentos en los últimos años?',
    '📈 ¿Qué cultivo tiene el mejor precio esta semana en la CEASA?',
  ],
}

const MSG = defineMessages({
  pt: {
    titulo: 'Exemplos de consultas para o gestor',
    texto: 'Clique em uma pergunta ou escreva a sua: disponibilidade da agricultura familiar, demanda da prefeitura e preços de referência da CEASA-PR.',
  },
  en: {
    titulo: 'Sample questions for managers',
    texto: 'Click a question or write your own: family farming availability, city demand and CEASA-PR reference prices.',
  },
  es: {
    titulo: 'Ejemplos de consultas para el gestor',
    texto: 'Haga clic en una pregunta o escriba la suya: disponibilidad de la agricultura familiar, demanda de la alcaldía y precios de referencia de la CEASA-PR.',
  },
})

export default function Ofertas() {
  const { lang } = useI18n()
  const t = useT(MSG)
  return (
    <Chat
      suggestions={CONSULTAS_GESTOR[lang]}
      welcomeIcon="🧺"
      welcomeTitle={t('titulo')}
      welcomeText={t('texto')}
    />
  )
}
