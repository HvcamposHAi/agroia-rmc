import { createContext, createElement, useCallback, useContext, useEffect, useMemo, useState } from 'react'
import type { ReactNode } from 'react'

// Internacionalização (pt / en / es) sem dependência externa.
// Cada página define seu próprio dicionário com defineMessages() e usa useT(dict);
// o idioma escolhido fica no localStorage e também vai para o backend (campo
// `idioma`), para que os agentes respondam no mesmo idioma da interface.

export type Lang = 'pt' | 'en' | 'es'

export interface LangInfo {
  code: Lang
  label: string     // nome no próprio idioma
  short: string     // rótulo curto do seletor
  locale: string    // Intl (números, datas)
  speech: string    // Web Speech API (voz)
}

export const LANGS: LangInfo[] = [
  { code: 'pt', label: 'Português', short: 'PT', locale: 'pt-BR', speech: 'pt-BR' },
  { code: 'en', label: 'English', short: 'EN', locale: 'en-US', speech: 'en-US' },
  { code: 'es', label: 'Español', short: 'ES', locale: 'es-ES', speech: 'es-ES' },
]

const CHAVE = 'agroia_idioma'

function detectarIdioma(): Lang {
  try {
    const salvo = localStorage.getItem(CHAVE)
    if (salvo === 'pt' || salvo === 'en' || salvo === 'es') return salvo
  } catch { /* sem storage */ }
  const nav = (typeof navigator !== 'undefined' ? navigator.language : 'pt').slice(0, 2).toLowerCase()
  return nav === 'en' || nav === 'es' ? nav : 'pt'
}

// Idioma corrente fora do React (apiClient, formatadores).
let idiomaAtual: Lang = detectarIdioma()
export const getLang = (): Lang => idiomaAtual
export const langInfo = (l: Lang = idiomaAtual): LangInfo => LANGS.find(x => x.code === l) ?? LANGS[0]
export const getLocale = (): string => langInfo().locale

type Vars = Record<string, string | number>
export type Dict = Record<string, string>

/** Dicionário de uma página: en/es precisam ter exatamente as mesmas chaves de pt. */
export function defineMessages<T extends Dict>(m: {
  pt: T
  en: { [K in keyof T]: string }
  es: { [K in keyof T]: string }
}): Record<Lang, T> {
  return m as Record<Lang, T>
}

function interpolar(texto: string, vars?: Vars): string {
  if (!vars) return texto
  return texto.replace(/\{(\w+)\}/g, (m, k) => (k in vars ? String(vars[k]) : m))
}

interface Ctx {
  lang: Lang
  setLang: (l: Lang) => void
  locale: string
}

const I18nContext = createContext<Ctx>({ lang: idiomaAtual, setLang: () => {}, locale: getLocale() })

export function I18nProvider({ children }: { children: ReactNode }) {
  const [lang, setLangState] = useState<Lang>(idiomaAtual)

  const setLang = useCallback((l: Lang) => {
    idiomaAtual = l
    try { localStorage.setItem(CHAVE, l) } catch { /* só nesta sessão */ }
    setLangState(l)
  }, [])

  useEffect(() => {
    document.documentElement.lang = langInfo(lang).locale
  }, [lang])

  const value = useMemo(() => ({ lang, setLang, locale: langInfo(lang).locale }), [lang, setLang])
  return createElement(I18nContext.Provider, { value }, children)
}

export function useI18n() {
  return useContext(I18nContext)
}

/** t(chave, vars) do dicionário da página, no idioma atual (fallback: pt, depois a própria chave). */
export function useT<T extends Dict>(messages: Record<Lang, T>) {
  const { lang } = useI18n()
  return useCallback(
    (chave: keyof T & string, vars?: Vars): string =>
      interpolar(messages[lang]?.[chave] ?? messages.pt[chave] ?? chave, vars),
    [lang, messages],
  )
}

// ─── Formatadores sensíveis ao idioma ──────────────────────────────────────
export const fmtNum = (v: number, opts?: Intl.NumberFormatOptions) => v.toLocaleString(getLocale(), opts)
export const fmtBRL = (v: number, opts?: Intl.NumberFormatOptions) =>
  v.toLocaleString(getLocale(), { style: 'currency', currency: 'BRL', ...opts })
export const fmtData = (d: Date | string, opts?: Intl.DateTimeFormatOptions) =>
  (typeof d === 'string' ? new Date(d) : d).toLocaleDateString(getLocale(), opts)
export const fmtDataHora = (d: Date | string, opts?: Intl.DateTimeFormatOptions) =>
  (typeof d === 'string' ? new Date(d) : d).toLocaleString(getLocale(), opts)
