export type SemaforoCor = 'verde' | 'amarelo' | 'vermelho' | 'cinza'

interface Props {
  semaforo: SemaforoCor
  texto: string
}

export function SemaforoPreco({ semaforo, texto }: Props) {
  const cores: Record<SemaforoCor, { bg: string; border: string; dot: string }> = {
    verde:    { bg: '#d1fae5', border: '#3a7d44', dot: '#3a7d44' },
    amarelo:  { bg: '#fef9c3', border: '#f5a623', dot: '#f5a623' },
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
        fontFamily: 'Nunito, sans-serif',
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
