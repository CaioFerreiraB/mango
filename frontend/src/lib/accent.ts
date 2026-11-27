/** Accent do usuário (DESIGN.md §Color): estado = atributo `data-accent` no <html>,
 * espelhado em localStorage para aplicar antes do primeiro paint (sem flash). */

export const ACCENT_PADRAO = "violeta"

/** nome → hex do primary (light), para swatches na UI. Presets em index.css. */
export const ACCENTS = {
  violeta: "#7008E7",
  tangerina: "#FB6A1E",
  lima: "#84CC16",
  azul: "#165DFC",
  rosa: "#E60076",
  grafite: "#1F2937",
} as const

export type Accent = keyof typeof ACCENTS

const STORAGE_KEY = "accent"

// Ids antigos (antes do redesenho dos presets), os mesmos da migration c4f8a2e61d07: quem tinha
// "verde" guardado no navegador abre já em "lima", sem esperar o /me.
const LEGADO: Record<string, Accent> = {
  verde: "lima",
  manga: "tangerina",
  teal: "grafite",
}

export function aplicarAccent(accent: string | null | undefined) {
  const atual = (accent && LEGADO[accent]) || accent
  const valido = atual && atual in ACCENTS ? (atual as Accent) : ACCENT_PADRAO
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
