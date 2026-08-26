/** Accent do usuário (DESIGN.md §Color): estado = atributo `data-accent` no <html>,
 * espelhado em localStorage para aplicar antes do primeiro paint (sem flash). */

export const ACCENT_PADRAO = "violeta"

/** nome → hex do primary (light), para swatches na UI. Presets em index.css. */
export const ACCENTS = {
  violeta: "#7008E7",
  manga: "#EA580E",
  verde: "#009965",
  azul: "#165DFC",
  rosa: "#E60076",
  teal: "#0092B8",
} as const

export type Accent = keyof typeof ACCENTS

const STORAGE_KEY = "accent"

export function aplicarAccent(accent: string | null | undefined) {
  const valido =
    accent && accent in ACCENTS ? (accent as Accent) : ACCENT_PADRAO
  if (valido === ACCENT_PADRAO) {
    delete document.documentElement.dataset.accent // default = sem atributo (index.css)
  } else {
    document.documentElement.dataset.accent = valido
  }
  localStorage.setItem(STORAGE_KEY, valido)
}

/** Chamado no boot (main.tsx), antes do render — lê o cache síncrono. */
export function initAccent() {
  aplicarAccent(localStorage.getItem(STORAGE_KEY))
}
