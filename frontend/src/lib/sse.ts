/**
 * Parser incremental de `text/event-stream` (POST não cabe em `EventSource`). Recebe pedaços
 * arbitrários da rede — um evento pode chegar partido entre chunks — e emite cada evento completo.
 * Comentários (`: ping`) e eventos sem `data` são ignorados.
 */
export function criarParserSSE(
  onEvento: (tipo: string, dados: unknown) => void
): (pedaco: string) => void {
  let resto = ""
  return (pedaco) => {
    resto += pedaco.replace(/\r\n?/g, "\n")
    const blocos = resto.split("\n\n")
    resto = blocos.pop() ?? ""
    for (const bloco of blocos) {
      let tipo = "message"
      const dados: string[] = []
      for (const linha of bloco.split("\n")) {
        if (linha.startsWith(":")) continue
        const sep = linha.indexOf(":")
        const campo = sep === -1 ? linha : linha.slice(0, sep)
        const valor = sep === -1 ? "" : linha.slice(sep + 1).replace(/^ /, "")
        if (campo === "event") tipo = valor
        else if (campo === "data") dados.push(valor)
      }
      if (dados.length) onEvento(tipo, JSON.parse(dados.join("\n")))
    }
  }
}
