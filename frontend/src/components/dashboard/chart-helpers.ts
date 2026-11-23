const compacto = new Intl.NumberFormat("pt-BR", {
  notation: "compact",
  maximumFractionDigits: 1,
})

/** Formata o tick do eixo Y (centavos → reais compacto). Ex.: 123456 → `1,2 mil`. */
export const eixoBRL = (centavos: number) => compacto.format(centavos / 100)
