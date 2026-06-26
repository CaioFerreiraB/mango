# Descoberta — API do Pluggy (Open Finance)

> **Status:** ✅ verificado ao vivo em 2026-06-26 contra a API real (`https://api.pluggy.ai`), via
> `scripts/discovery/explore_pluggy.py` sobre um `itemId` real (1 conta corrente + 1 cartão + 8
> investimentos). JSONs crus em `scripts/discovery/raw/` (gitignorado); aqui só **excertos redigidos**.
>
> Esta é a fase de **descoberta** da spec (`requisitos.md` §2): mapear endpoints e campos a modelar na
> **Fase 0**. Não há código de aplicação aqui — só mapeamento e implicações de modelagem.

## 1. Contexto e como reproduzir

Cada usuário cria seu app no Pluggy (nível gratuito) e conecta contas pelo Meu Pluggy (`requisitos.md`
§4.3). O script aceita um `PLUGGY_ITEM_ID` real (usado nesta captura) ou, sem ele, cria um item no
**connector de sandbox** (`user-ok`/`password-ok`/MFA `123456`).

```bash
cp scripts/discovery/.env.example scripts/discovery/.env   # preencha clientId/clientSecret (+ itemId opcional)
uv run scripts/discovery/explore_pluggy.py                 # após o uv existir (Fase 0, SETUP.md §4.1)
```

> Antes do `uv` estar instalado, dá para rodar com um venv: `python3 -m venv .venv &&
> .venv/bin/pip install httpx python-dotenv && .venv/bin/python scripts/discovery/explore_pluggy.py`.

## 2. Autenticação ✅

Dois estágios, sempre **server-side** (credenciais sensíveis → §5.5, criptografadas em repouso):

| Passo | Endpoint | Entrada | Saída | Header |
| --- | --- | --- | --- | --- |
| 1 | `POST /auth` | `clientId`, `clientSecret` | `apiKey` (validade ~2h) | — |
| 2 | `POST /connect_token` | `apiKey` (+ opcional `itemId`, `webhookUrl`) | `connectToken` (~30min, usado no widget) | `X-API-KEY` |

Demais chamadas vão com header **`X-API-KEY: <apiKey>`**. Guardamos `clientId`/`clientSecret`/`itemId` por
conta; `apiKey`/`connectToken` são efêmeros (derivados em runtime).

## 3. Contas — `GET /accounts?itemId={itemId}` ✅

Dois tipos: **`BANK`** (`subtype` `CHECKING_ACCOUNT`/`SAVINGS_ACCOUNT`) e **`CREDIT`** (`CREDIT_CARD`).
Campos comuns: `id`, `type`, `subtype`, `number`, `name`, `marketingName`, `balance`, `currencyCode`,
`owner`, `taxNumber`, `itemId`, `createdAt`, `updatedAt`.

**`bankData` (conta):** `transferNumber` (COMPE/agência/conta), `closingBalance`,
`automaticallyInvestedBalance`, `overdraftContractedLimit`/`overdraftUsedLimit`,
`unarrangedOverdraftAmount`, `hasReservedBalance`, `reservedBalances`.

**`creditData` (cartão) — base da fatura (§4.2):** `balanceCloseDate` (fechamento), `balanceDueDate`
(vencimento), `minimumPayment`, `creditLimit`, `availableCreditLimit`, `balanceForeignCurrency`,
`brand`, `level`, `status`, `holderType`, `isLimitFlexible`, `additionalCards`,
`disaggregatedCreditLimits`.

**Faturas — `GET /bills?accountId={accountId}` ✅** (page-based: `total`/`totalPages`/`page`/`results`):
`id`, `dueDate`, `totalAmount`, `totalAmountCurrencyCode`, `minimumPaymentAmount`, `allowsInstallments`,
`financeCharges[]` (`{id, type, amount, currencyCode, additionalInfo}` — juros/IOF/multa), `payments[]`.

> **Modelagem §4.2 (competência × caixa):** a despesa de cartão referencia sua fatura via
> `transaction.creditCardMetadata.billId` (ver §4). O **pagamento da fatura** aparece como transação da
> conta corrente categorizada como **`05100000` "Pagamento de cartão de crédito"** — usamos isso (+ flag de
> transferência) para não contar o gasto duas vezes.

## 4. Transações — `GET /v2/transactions?accountId={accountId}` ✅ ⚠️

> ⚠️ **Mudança de contrato confirmada:** `GET /transactions` (v1) está **deprecado (HTTP 410)**. Usar
> **`GET /v2/transactions`** com **paginação por cursor**: a resposta é `{results, next}` e seguimos a URL
> em `next` até `null`. O v2 **não aceita `pageSize`**.

**Campos:** `id`, `accountId`, `date` (ISO8601), `description`, `descriptionRaw`, `amount`,
`amountInAccountCurrency`, `currencyCode`, `type` (`DEBIT`/`CREDIT`), `status` (`POSTED`/`PENDING`),
`balance`, `category` (string **em inglês**), `categoryId` (código hierárquico, ver §7), `merchant`,
`paymentData`, `creditCardMetadata`, `operationType`, `providerCode`, `providerId`, `order`.

**`creditCardMetadata` (cartão):** `billId` (→ fatura, §4.2), `installmentNumber`, `totalInstallments`,
`totalAmount`, `payeeMCC`.

**`paymentData` (transferências):** `payer` e `receiver` (`name`, `accountNumber`, `branchNumber`,
`routingNumber`, `routingNumberISPB`, `documentNumber{type,value}`), `paymentMethod`
(`PIX`/`TED`/`DOC`/`BOLETO`), `reason`, `referenceNumber`, `receiverReferenceId`, `boletoMetadata`
(`barcode`, `digitableLine`, `baseAmount`, `interestAmount`, `discountAmount`, `penaltyAmount`).

> **Valores em centavos (decisão #2):** o Pluggy entrega `amount` como **decimal em reais** (confirmado:
> ex. `-167.7`, `-89.9`, `8500`). Na ingestão convertemos para **inteiro em centavos** com arredondamento
> (`round(amount * 100)`) para evitar erro de ponto flutuante.

## 5. Transferências entre contas (§4.4) ✅

A taxonomia do Pluggy **já distingue** transferências de **mesma titularidade** das demais — sinal forte
para a heurística de pareamento:

- **`04000000` "Transferência mesma titularidade"** → `04010000` Dinheiro, `04020000` PIX, `04030000` TED.
- **`05000000` "Transferências"** (terceiros/genéricas): `05010000` Boleto, `05070000` PIX, `05080000` TED,
  `05090000`/`05090001…` "para terceiros", **`05100000` "Pagamento de cartão de crédito"**.

**Heurística de pareamento (duas pernas):** `amount` oposto + `date` próxima + **ambas as contas do
usuário conectadas**, reforçado por `paymentData.payer`/`receiver` (documento/conta) e pela categoria
`04xxxxxx`. Sem contraparte conectada = **perna única** (transação normal); o usuário pode marcar o flag
manualmente.

**Flags de controle (nossos, não do Pluggy):** `eh_transferencia` (exclui de entradas/saídas) e `revisada`
— modelados em `transacao`.

## 6. Investimentos — `GET /investments?itemId={itemId}` ✅ (§4.9)

Page-based. O Pluggy entrega **valores já calculados** — consumimos, não recalculamos impostos (decisão #5).
Tipos vistos na captura: `SECURITY` (`PGBL`/`RETIREMENT` — previdência), `MUTUAL_FUND`
(`INVESTMENT_FUND`), `FIXED_INCOME` (`CDB`), `ETF`, `EQUITY` (`REAL_ESTATE_FUND` = FII).

| Campo | Significado |
| --- | --- |
| `amountOriginal` | valor investido |
| `amount` | valor bruto atual |
| `taxes` / `taxes2` | **IR** / **IOF** |
| `amountProfit` | lucro/prejuízo |
| `amountWithdrawal` | disponível para resgate |
| `quantity` / `value` | quantidade / preço unitário (renda variável/fundos) |
| `rate`, `rateType`, `fixedAnnualRate`, `annualRate`, `lastMonthRate`, `lastTwelveMonthsRate` | indexadores/rentabilidade |
| `isin`, `code`, `issuer`, `issuerCNPJ`, `dueDate`, `issueDate`, `subtype`, `status` | identificação/metadados |

> Campos **variam por tipo** (ex.: previdência `SECURITY` sem `amountOriginal`/`amountProfit`) → modelar
> como **nullable**. **Proventos/movimentos** (FII *dividend yield*, §4.9) vêm de
> `GET /investments/{id}/transactions` (confirmado: fundos retornaram movimentos). **Indicadores de
> mercado** (IBOV/IPCA/CDI) **não** vêm do Pluggy → fonte externa (§5.6), fora da descoberta.

## 7. Categorias — `GET /categories` ✅ — comportamento da API

Taxonomia fixa do Pluggy: **130 categorias, 22 raízes**, **hierarquia de até 3 níveis** (ex.: `05090000` →
`05090001`…). Campos: `id` (código de 8 dígitos), `description` (inglês), `descriptionTranslated`
(**pt-BR**), `parentId`, `parentDescription`. As transações trazem `category` em **inglês** + `categoryId`;
o pt-BR vem do espelho de `/categories`.

**22 raízes:** Renda, Empréstimos e financiamento, Investimentos, Transferência mesma titularidade,
Transferências, Obrigações legais, Serviços, Compras, Serviços digitais, Supermercado, Alimentos e bebidas,
Viagens, Doações, Apostas, Impostos, Taxas bancárias, Moradia, Saúde, Transporte, Seguros, Lazer, Outros.

**Pergunta-chave — criar categorias novas?** **NÃO.** Verificado ao vivo:

- **`POST /categories` → HTTP 405 Method Not Allowed.** A taxonomia é **somente leitura**; não há criação de
  categorias-folha (`raw/probe_post_categories.json`).
- **Regras de categorização — `GET/POST /categories/rules` (HTTP 200):** existem, mas **não criam
  categorias**. Uma regra mapeia transações para uma categoria **já existente** ("se a descrição casar com X,
  rotule como `categoryId` Y"); roda **antes** da IA do Pluggy, por *exact match*, e é amarrada ao
  `client_id`. A doc é explícita: *"Category Rules assign transactions to existing Pluggy categories only —
  they do not create new custom categories."* `POST /categories/rules` exige ao menos `description` +
  `categoryId` (existente). (Atenção: o caminho é `/categories/rules`; `/category-rules` retorna 403.)

## 8. Adoção da taxonomia do Pluggy + override por transação (§4.5) ✅

**Decisão de produto:** o mango **adota a taxonomia do Pluggy como está** — sem taxonomia própria nem
mapeamento. Concretamente:

- Espelhamos `GET /categories` numa tabela local (referenciando o `id` do Pluggy + `descriptionTranslated`),
  preservando a **hierarquia (`parentId`, até 3 níveis)**.
- Cada `transacao` guarda `categoryId` sugerido pelo Pluggy.
- O usuário pode **re-categorizar e salvar** (override **local**): campo de categoria sobrescrita + marcação
  "ajustado pelo usuário".
- **Re-sync:** **não** sobrescrever a categoria ajustada pelo usuário ao reimportar. O override é **nosso**,
  no banco (fonte de verdade). *Opção futura:* empurrar o override como **regra** (`POST /categories/rules`,
  mapeando para uma categoria existente) para o Pluggy já trazer a categoria certa em syncs futuros — cada
  usuário tem o próprio app Pluggy (§4.3), então a regra fica no escopo dele. Não é necessário na v1.
- **Orçamentos (decisão #20):** soma das subcategorias ≤ categoria, usando os pares da própria taxonomia.

## 9. Operacional (sandbox, limites, sync, webhooks)

- **Sandbox:** connector com `user-ok`/`password-ok`/MFA `123456`; outros usuários simulam erros/MFA/perf.
- **Rate limits** (por IP/min, doc): `POST /auth`, `GET /v2/transactions`, `GET /investments` ~360;
  **`PATCH /items` (update manual) ~20**. `429` traz `Retry-After: 60` (o script trata).
- **Sync:** auto a cada 8/12/24h (conforme plano); sob demanda via `PATCH /items` (§4.3: 1×/dia ou
  "atualizar conexão"). Coleta o delta desde o último sync + margem de dias.
- **Webhooks** (insumo §4.12): eventos de item (created/updated/error), transações, pagamentos; resposta
  2XX em ≤5s e processamento async; HTTPS obrigatório.

## 10. Implicações de modelagem (insumo Fase 0)

Checklist de entidades/campos. Todas carregam `user_id` (§5.2); valores monetários em **centavos**
(decisão #2):

- **`credencial_pluggy`** — `clientId`, `clientSecret`, `itemId` **criptografados em repouso** (§5.5).
- **`instituicao`** / **`conta`** — `type` `BANK`/`CREDIT`, `subtype`, `pluggy_account_id`, saldo, campos de
  `bankData`/`creditData`.
- **`cartao` + `fatura`** — `balanceCloseDate`/`balanceDueDate`/`minimumPayment`; fatura com
  `dueDate`/`totalAmount`/`minimumPaymentAmount`/`financeCharges`; vínculo via `creditCardMetadata.billId`.
- **`transacao`** — `pluggy_transaction_id`, `amount` (centavos), `date`, `description`, `type`, `status`,
  `categoryId` (Pluggy) + **override de categoria**, parcelas (`installmentNumber`/`totalInstallments`),
  `paymentData` (payer/receiver para §4.4) + flags **`eh_transferencia`** e **`revisada`**.
- **`categoria`** (auto-relacionada, **hierarquia até 3 níveis**) — espelho de `/categories`
  (`id`, `parentId`, `descriptionTranslated`).
- **`investimento` (+ `investimento_transacao`)** — `amountOriginal`/`amount`/`taxes`/`taxes2`/`amountProfit`
  (nullable por tipo), `type`/`subtype`, `quantity`/`value`, indexadores; proventos via
  `/investments/{id}/transactions`.
- **`fonte_de_renda`** — entidade própria (§4.1), independente do Pluggy.
- Vínculo **objetivo ↔ conta/investimento** 1:1 (decisão #4).

## 11. Confirmado × em aberto

| Item | Status |
| --- | --- |
| Auth `apiKey` (`X-API-KEY`) / `connect_token` | ✅ confirmado |
| Contas `BANK`/`CREDIT`, `bankData`/`creditData`, faturas | ✅ confirmado |
| **Transações via `/v2/transactions` (cursor); v1 deprecado (410)** | ✅ confirmado |
| `amount` em **reais decimais** → converter para centavos | ✅ confirmado |
| `creditCardMetadata.billId` + parcelas; `paymentData` payer/receiver | ✅ confirmado |
| Investimentos pré-calculados (IR/IOF), tipos, movimentos | ✅ confirmado |
| **`POST /categories` → 405 (não cria categorias)** | ✅ confirmado — resolve §4.5/decisão #19 |
| Taxonomia de **3 níveis**, `categoryId` hierárquico, pt-BR em `descriptionTranslated` | ✅ confirmado |
| `/categories/rules` (regras de categorização) | ✅ HTTP 200 — mapeia p/ categoria **existente**, **não cria** categoria; opção p/ persistir override no Pluggy |
| Pareamento de transferência conta→conta com dois itens reais | 🔎 a validar com 2+ contas conectadas (categoria `04xxxxxx` ajuda) |
| Rate limits / webhooks exatos | 🔎 conforme docs; revisitar na implementação do sync (Fase 1) |

> **Reconciliação (sem editar a spec agora):** a §4.5/decisão #19 supunha "criar categorias novas" no
> Pluggy. A descoberta **refutou** isso (`POST /categories` → 405). Decisão de produto: **adotar a taxonomia
> do Pluggy** + override **local** por transação. Atualizar o log de decisões da spec numa próxima passada.
