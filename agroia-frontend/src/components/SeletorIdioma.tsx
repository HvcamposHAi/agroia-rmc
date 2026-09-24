import { LANGS, useI18n } from '../i18n'

// Seletor PT / EN / ES da barra superior. A troca vale para toda a interface
// e para as respostas dos agentes (o idioma vai em cada chamada à API).
export default function SeletorIdioma() {
  const { lang, setLang } = useI18n()
  return (
    <div className="lang-switch" role="group" aria-label="Idioma / Language / Idioma">
      {LANGS.map(l => (
        <button
          key={l.code}
          type="button"
          className={`lang-btn${l.code === lang ? ' active' : ''}`}
          onClick={() => setLang(l.code)}
          aria-pressed={l.code === lang}
          title={l.label}
          lang={l.locale}
        >
          {l.short}
        </button>
      ))}
    </div>
  )
}
