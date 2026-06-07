export type SemaforoCor = 'verde' | 'amarelo' | 'vermelho' | 'cinza'

interface Props {
  semaforo: SemaforoCor
  texto: string
}

export function SemaforoPreco({ semaforo, texto }: Props) {
  const cores: Record<SemaforoCor, { bg: string; border: string; dot: string }> = {
    verde:    { bg: '#d6ebe8', border: '#0f766e', dot: '#0f766e' },
    amarelo:  { bg: '#fdf1e3', border: '#b45309', dot: '#b45309' },
    vermelho: { bg: '#fee2e2', border: '#dc2626', dot: '#dc2626' },
    cinza:    { bg: '#f3f4f6', border: '#9ca3af', dot: '#9ca3af' },
  }
  const c = cores[semaforo]

  return (
    <div
      style={{
        display: 'inline-flex',
        alignItems: 'center',
        gap: '8px',
        padding: '6px 14px',
        borderRadius: '20px',
        border: `1.5px solid ${c.border}`,
        backgroundColor: c.bg,
        fontSize: '0.85rem',
        fontFamily: 'Inter, sans-serif',
      }}
    >
      <span
        style={{
          width: 10,
          height: 10,
          borderRadius: '50%',
          backgroundColor: c.dot,
          flexShrink: 0,
        }}
      />
      {texto}
    </div>
  )
}
