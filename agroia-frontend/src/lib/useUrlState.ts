import { useCallback } from 'react'
import { useSearchParams } from 'react-router-dom'

/**
 * Estado persistido na URL (query string), via react-router useSearchParams.
 * Mantém filtros/busca ao navegar, recarregar (F5) e compartilhar por link.
 *
 * IMPORTANTE: o setter monta os novos params a partir de `window.location.search`
 * (atualizado de forma síncrona pelo history.pushState/replaceState) em vez do
 * `searchParams` do render atual. Isso garante que VÁRIOS setters chamados no
 * mesmo handler (ex.: setBusca(...) e depois setPage(1)) componham corretamente —
 * caso contrário o segundo navigate sobrescreveria o primeiro (react-router passa
 * uma cópia do snapshot do render para o updater, não um valor ao vivo).
 * Usa replace:true para não poluir o histórico a cada tecla.
 */
export function useUrlState(
  key: string,
  defaultValue = '',
): [string, (v: string) => void] {
  const [searchParams, setSearchParams] = useSearchParams()
  const value = searchParams.get(key) ?? defaultValue

  const setValue = useCallback(
    (v: string) => {
      const next = new URLSearchParams(window.location.search)
      if (v === '' || v === defaultValue) next.delete(key)
      else next.set(key, v)
      setSearchParams(next, { replace: true })
    },
    [key, defaultValue, setSearchParams],
  )

  return [value, setValue]
}
