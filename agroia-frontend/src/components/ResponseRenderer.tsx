import ReactMarkdown from 'react-markdown'

interface ResponseRendererProps {
  content: string
}

export default function ResponseRenderer({ content }: ResponseRendererProps) {
  // Detecta e renderiza tabelas de forma custom
  const renderCustomTable = (text: string) => {
    const tablePattern = /\|(.+)\|[\r\n]+\|[-:\s|]+\|[\r\n]+((?:\|.+\|[\r\n]?)*)/g
    let lastIndex = 0
    const elements: React.ReactNode[] = []

    let match
    while ((match = tablePattern.exec(text)) !== null) {
      // Texto antes da tabela
      if (match.index > lastIndex) {
        elements.push(
          <ReactMarkdown key={`text-${lastIndex}`}>
            {text.substring(lastIndex, match.index)}
          </ReactMarkdown>
        )
      }

      // Extrai header e dados
      const headerLine = match[1]
      const dataLines = match[2].split('\n').filter(line => line.trim())

      const headers = headerLine.split('|').map(h => h.trim()).filter(Boolean)
      const rows = dataLines.map(line =>
        line.split('|').map(cell => cell.trim()).filter(Boolean)
      )

      // Renderiza tabela customizada
      elements.push(
        <div key={`table-${match.index}`} className="response-table">
          <table>
            <thead>
              <tr>
                {headers.map((h, i) => (
                  <th key={i}>{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {rows.map((row, i) => (
                <tr key={i}>
                  {row.map((cell, j) => (
                    <td key={j}>{cell}</td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )

      lastIndex = match.index + match[0].length
    }

    // Texto após última tabela
    if (lastIndex < text.length) {
      elements.push(
        <ReactMarkdown key={`text-end`}>
          {text.substring(lastIndex)}
        </ReactMarkdown>
      )
    }

    return elements.length > 0 ? elements : <ReactMarkdown>{text}</ReactMarkdown>
  }

  return (
    <div className="response-content">
      {renderCustomTable(content)}
    </div>
  )
}
