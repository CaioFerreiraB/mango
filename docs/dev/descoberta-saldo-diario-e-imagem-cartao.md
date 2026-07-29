# Descoberta — saldo diário e imagem de cartões

> **Status:** ✅ explorado em 2026-07-15 (docs Pluggy + captura real em `scripts/discovery/raw/`,
> gitignorada). Só mapeamento — **nada implementado**. Complementa `descoberta-pluggy.md`.

**TL;DR:** (1) saldo dia a dia não existe pronto na Pluggy nem em nenhum agregador sobre o Open
Finance Brasil — obtível combinando reconstrução retroativa via transações (~12 meses) com snapshots
diários no sync. (2) Imagem real de cada cartão é inalcançável por fonte acessível a nós; caminho
viável é renderizar o cartão (cor/logo da instituição + bandeira SVG + level + últimos 4 dígitos).

## 1. Saldo de contas dia a dia

**O que a Pluggy oferece:**

- `GET /accounts` → só **saldo atual** (`balance`); já armazenado em `conta.saldo_centavos`.
- [Real-Time Balance](https://docs.pluggy.ai/docs/real-time-balance) (`GET /accounts/{id}/balance`) →
  saldo atual sob demanda, só connectors Open Finance, **sem histórico**; consome a mesma cota de
  rate limit do sync.
- Campo `balance` por transação ("saldo após a transação") — a
  [doc](https://docs.pluggy.ai/docs/transactions) sugere usar o `balance` da última transação do dia
  como saldo de fim de dia, **mas** só vem preenchido nos connectors "Direct" **PJ** (Itaú PJ,
  Sicredi PJ, Bradesco PJ, Inter PJ, Banrisul PJ, Santander PJ). Na nossa captura real: **0 de 18**
  transações com `balance` → `transacao.balance_centavos` fica sempre nulo em contas PF.

**Outras fontes:** limitação regulatória — as APIs do Open Finance Brasil só expõem saldo corrente;
Belvo/Klavi/etc. têm o mesmo teto. Não há fonte externa com série histórica de saldo.

**Como obter (técnica padrão de PFMs, duas pernas complementares):**

1. **Reconstrução retroativa:** saldo de fechamento do dia D = saldo atual − Δ das transações
   posteriores a D. A conexão inicial traz [até 365 dias de
   histórico](https://docs.pluggy.ai/docs/item) → retro-preenche ~12 meses. Riscos: transações
   `PENDING`; buracos no histórico fazem o saldo derivar; bloqueios/reservas mudam saldo sem
   transação (raro).
2. **Snapshot diário no sync (forward):** gravar `(conta, data, saldo)` a cada sync — já temos
   scheduler e saldo por conta. Fonte de verdade dali em diante; corrige drift da reconstrução.

Cartão: "saldo diário" = fatura aberta acumulada; mesma acumulação de transações. Onde o `balance`
por transação vier preenchido (PJ), usar como âncora.

**Veredito: viável** — exato daqui pra frente (snapshots), aproximado-mas-consistente nos últimos
12 meses (reconstrução), impossível antes disso.

## 2. Imagem de cartões de crédito

**O que a Pluggy entrega por cartão** (captura real): `brand`, `level`, `marketingName`
(ex. "PLUGGY UNICLASS MASTERCARD BLACK"), `brandAdditionalInfo` e **só os 4 últimos dígitos**.
Nenhum campo de imagem — o `imageUrl` é do *connector* (logo da instituição; ver
`pluggy-sandbox-sem-catalogo-de-bancos`).

**Fontes de card art real — todas inviáveis:**

- **Visa TMS [Card Art](https://developer.visaacceptance.com/docs/vas/en-us/tms/developer/ctv/rest/tms/tms-card-art/tms-net-tkn-card-art-retrieve-intro.html)
  / Mastercard MDES** entregam a arte exata do cartão, mas só no ecossistema de **tokenização**,
  restrito a emissores/merchants credenciados. Os [guidelines da
  Mastercard](https://www.mastercard.com/brandcenter/us/en/card-artwork.html) são explícitos:
  material proprietário.
- **BIN lookup** (binlist etc.): exige os 6–8 primeiros dígitos; a Pluggy só dá os 4 últimos.
- **Banco público de artes por produto de cartão BR:** não existe. Milhares de produtos mutáveis +
  risco de marca/direitos → curadoria manual sem fim.

**Utilizável (open source):** bandeiras em SVG
([payment-brands-images](https://github.com/jeffdrumgod/payment-brands-images),
[bandeiras-de-cartao](https://github.com/myTapp/bandeiras-de-cartao)) e logos de bancos BR
([Bancos-em-SVG](https://github.com/Tgentil/Bancos-em-SVG),
[icones-bancos-brasileiros](https://github.com/matheuscuba/icones-bancos-brasileiros)) — além do
nosso catálogo curado de instituições (logo+cor) do vínculo manual.

**Veredito e recomendação:** **renderizar o cartão** — componente SVG/CSS com cor+logo da
instituição (já temos), bandeira (SVG open source), `level` e "•••• 9437". Cobre 100% sem curadoria
por produto. Opcional: skins curadas para os ~10–20 cartões icônicos (roxinho Nubank, C6 carbon…)
com cores/gradientes inspirados, sem reproduzir a arte oficial.
