/**
 * Tons de status do app inteiro — o mesmo estado tem a mesma cara em qualquer tela (pendente,
 * pago, atrasado, em aberto…). Pílula com fundo suave, bolinha no tom cheio e texto no `*-ink`
 * (AA); a palavra sempre acompanha a cor (a11y).
 */
export const TONS_SELO = {
  neutro: { badge: "bg-muted text-foreground", ponto: "bg-muted-foreground" },
  apagado: {
    badge: "bg-muted text-muted-foreground",
    ponto: "bg-muted-foreground/60",
  },
  info: { badge: "bg-primary/10 text-accent-ink", ponto: "bg-primary" },
  sucesso: { badge: "bg-success/12 text-success-ink", ponto: "bg-success" },
  aviso: { badge: "bg-warning/15 text-warning-ink", ponto: "bg-warning" },
  perigo: { badge: "bg-negative/12 text-negative-ink", ponto: "bg-negative" },
} as const

export type TomSelo = keyof typeof TONS_SELO
