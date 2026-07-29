# Descoberta — fundamentos de FII por ticker/ISIN

> **Status:** ✅ explorado em 2026-07-27 (CVM Dados Abertos + payload real do Pluggy em
> `scripts/discovery/raw/investments.json`, gitignorado). Só mapeamento — **nada implementado**.
> Complementa `descoberta-pluggy.md`. Sem raspagem: tudo sai de API/open data que já podemos acessar.

**TL;DR:** o Pluggy **não** manda o CNPJ do FII (vem `issuerCNPJ: null` para `type=EQUITY`), mas manda
o **ISIN**. O Informe Mensal de FII da CVM (open data, CSV público) tem a coluna `Codigo_ISIN`, então
dá pra ligar **ISIN do Pluggy → CNPJ do fundo** com chave **exata** (verificado no GGRC11) e, a partir
do CNPJ, puxar quase todos os fundamentos do fundo. Fontes: Pluggy (já roda) + brapi (já roda) + CVM
Dados Abertos. Custo real = **ETL em lote** sobre os ZIPs da CVM filtrado pelos ISINs em carteira, não
uma chamada por ticker.

## 1. O que o Pluggy dá (e não dá) para FII

Do `GET /investments` (já persistido em `investimento`, ver `sync.py::_upsert_investimentos`), no FII
real de descoberta **GGRC11** (`type=EQUITY`, `subtype=REAL_ESTATE_FUND`):

| campo Pluggy | valor | nosso campo |
|---|---|---|
| `code` (ticker) | `GGRC11` | `investimento.code` ✅ |
| `isin` | `BRGGRCCTF002` | `investimento.isin` ✅ |
| `issuer` (nome) | `GGR COVEPI RENDA FDO INV IMOB` | `investimento.issuer` ✅ |
| `issuerCNPJ` | **`null`** | `investimento.issuer_cnpj` ❌ |

Ou seja: o `issuer_cnpj` que já persistimos só vem preenchido em previdência/parte da renda fixa; para
FII é sempre nulo. **Já temos o ISIN — que é a chave da ponte.**

## 2. A ponte: ISIN do Pluggy → CNPJ do fundo (via CVM)

O Informe Mensal de FII (arquivo `geral`) traz `Codigo_ISIN` ao lado de `CNPJ_Fundo_Classe`. Join
exato, verificado:

```
Pluggy isin = BRGGRCCTF002
  → CVM inf_mensal_fii_geral.Codigo_ISIN
  → CNPJ_Fundo_Classe = 26.614.291/0001-00
     (Nome_Fundo_Classe = "GGR COVEPI RENDA FUNDO DE INVESTIMENTO IMOBILIÁRIO RL")
```

Sem casar por nome (que é abreviado/instável), sem scraping. O ISIN do Pluggy e o `Codigo_ISIN` da CVM
são o mesmo ISIN B3 de 12 chars; normalizar caixa antes de comparar.

## 3. Fontes CVM (Dados Abertos — público, sem token)

CSV separado por `;`, encoding **ISO-8859-1 (latin1)**. Cada arquivo é chaveado por
`(CNPJ_Fundo_Classe, Data_Referencia, Versao)` — pegar a **maior `Versao`** por (CNPJ, mês). ZIP anual
com **todos** os fundos → baixar, filtrar pelos ISINs/CNPJs em carteira, guardar.

- **Informe Mensal** — `https://dados.cvm.gov.br/dados/FII/DOC/INF_MENSAL/DADOS/inf_mensal_fii_<ANO>.zip`
  - `inf_mensal_fii_geral_<ANO>.csv` — cadastro/classificação
  - `inf_mensal_fii_complemento_<ANO>.csv` — PL, cotistas, VP da cota, DY do mês
  - `inf_mensal_fii_ativo_passivo_<ANO>.csv` — composição de ativos
  - dicionário: `.../INF_MENSAL/META/meta_inf_mensal_fii.zip`
- **Informe Trimestral** — `https://dados.cvm.gov.br/dados/FII/DOC/INF_TRIMESTRAL/DADOS/inf_trimestral_fii_<ANO>.zip`
  - `inf_trimestral_fii_imovel_<ANO>.csv` — desempenho por imóvel (vacância, inadimplência)
  - dicionário: `.../INF_TRIMESTRAL/META/meta_inf_trimestral_fii.zip`

Preço e proventos **não** vêm da CVM aqui — continuam do que já temos (brapi / Pluggy).

## 4. Campos obtíveis (todos verificados)

### Já temos (Pluggy / brapi — sem CVM)

| Campo | Fonte |
|---|---|
| ISIN, ticker, nome do fundo | Pluggy `investimento.isin` / `.code` / `.issuer` |
| preço da cota (histórico) | brapi `GET /quote/{ticker}` → `historicalDataPrice` (`indicadores.precos_historicos`) |
| distribuição de rendimentos (histórico) | Pluggy `GET /investments/{id}/transactions` (proventos, já em `investimento_transacao`) |

### Via ponte CVM — Informe Mensal (arquivo · coluna)

| Campo | Arquivo | Coluna |
|---|---|---|
| CNPJ do fundo | geral | `CNPJ_Fundo_Classe` |
| administrador (nome + CNPJ) | geral | `Nome_Administrador`, `CNPJ_Administrador` |
| início do fundo | geral | `Data_Funcionamento` |
| segmento | geral | `Segmento_Atuacao` |
| tipo de fundo (tijolo/papel/híbrido/FoF) | geral | derivado de `Mandato` + `Segmento_Atuacao` + `Tipo_Gestao` |
| patrimônio líquido | complemento | `Patrimonio_Liquido` |
| número de cotistas | complemento | `Total_Numero_Cotistas` (+ quebra por tipo em `Numero_Cotistas_*`) |
| valor patrimonial da cota | complemento | `Valor_Patrimonial_Cotas` |
| **P/VP** | calculado | preço (brapi) ÷ `Valor_Patrimonial_Cotas` |
| **dividend yield 12M do fundo** | calculado | Σ `Percentual_Dividend_Yield_Mes` dos 12 meses (ou Σ proventos ÷ preço) |
| alocação da carteira | ativo_passivo | `FII`, `CRI`, `CRI_CRA`, `LCI`, `LCI_LCA`, `Imoveis_Renda_Acabados`, `Imoveis_Renda_Construcao`, `Terrenos`, `Direitos_Bens_Imoveis`, `Outras_Cotas_FI`, `Debentures`, `Disponibilidades`, … sobre `Total_Investido` |

### Via ponte CVM — Informe Trimestral (arquivo · coluna)

| Campo | Arquivo | Coluna | Observação |
|---|---|---|---|
| vacância física | imovel | `Percentual_Vacancia` | por imóvel → agregar (ponderar por área/receita); só fundos com imóvel (tijolo) |
| inadimplência | imovel | `Percentual_Inadimplencia` | idem — por imóvel, agregar |

## 5. Custo, latência e veredito

- **Não é chamada por ticker, é ETL.** ZIP anual da CVM com todos os fundos → ingerir mensal
  (`geral`+`complemento`+`ativo_passivo`) e trimestral (`imovel`), filtrar pelos ISINs em carteira,
  gravar CNPJ + fundamentos. Encaixa no scheduler `self_hosted` que já materializa/alerta.
- **Latência:** o Informe Mensal chega ~15–30 dias após o mês; o Trimestral, bem mais. Não é tempo
  real — mas fundamento de FII não precisa ser. Preço/proventos seguem em tempo de sync (brapi/Pluggy).
- **Sugestão de fatiamento (YAGNI):** Fase 1 = só o Mensal (destrava CNPJ, PL, cotistas, VP → P/VP, DY,
  segmento, tipo, administrador, início, alocação). Fase 2 = Trimestral (vacância/inadimplência),
  só se a tela de detalhe do FII pedir — arquivo maior, mais defasado, só tijolo.

**Veredito: viável e limpo** — ponte exata por ISIN, todas as fontes são API/open data que já
acessamos. `investimento.isin` já guarda a chave; falta o job de ingestão + onde persistir os
fundamentos (ex.: no `ativo` ou tabela nova).

---

**Fora de escopo (só existem em regulamento/texto livre ou não são exatos — omitidos de propósito):**
taxa de administração (o CVM tem só a *despesa* realizada no mês, não a taxa nominal), taxa de
performance, gestor (o informe traz só administrador), exposição por segmento (o fundo tem um único
segmento; agregação fina exigiria breakdown que não é estruturado).

**Logo (descoberta correlata):** ação → `https://icons.brapi.dev/icons/{TICKER}.svg` é público e
determinístico (não gasta cota da brapi); **FII não tem** (404 em MXRF11/HGLG11/KNRI11/XPML11) → cai no
avatar de iniciais+cor. Ver contexto no fio de logo.
