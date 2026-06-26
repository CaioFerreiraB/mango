# Sistema de Controle Financeiro Pessoal
**Especificação de produto e arquitetura**

> Documento-fonte para geração dos planos de execução. O desenvolvimento será agêntico, com foco inicial no **Claude Code**. O setup de ferramentas de contexto (codegraph, graphify, graphiti, ponytail, impeccable) está no documento separado `DESENVOLVIMENTO.md`.

---

## 1. Objetivo

Sistema de controle financeiro doméstico para acompanhamento de gastos do dia a dia, investimentos e objetivos financeiros. Moeda única: **BRL**.

O sistema roda em dois modos, a partir da **mesma base de código**:

- **Self-hosted** (VM / container): multiusuário, acesso distribuído (web + mobile via PWA). O usuário hospeda em algum lugar para usar de forma compartilhada e a partir de vários dispositivos.
- **Local** (desktop): monousuário, dados sempre locais, sem compartilhamento e sem acesso remoto. Para quem só vai usar no próprio computador.

---

## 2. Escopo e faseamento

**v1 — primeira versão:** importação de dados **exclusivamente via Open Finance (Pluggy)**. A inclusão manual de transações e a importação de OFX ficam para versões posteriores.

**Princípio de sequência — fundação antes da UI.** Antes de qualquer tela, a base deve estar pronta: **modelo de dados completo** (schema de todas as entidades de domínio + migrations Alembic) e **backend com CRUD funcionando e testado** sobre essas entidades. Só depois disso começam as telas. Além de organizar o trabalho, isso aproveita a arquitetura: com o backend pronto, o **schema OpenAPI** já existe e gera o cliente tipado do frontend antes de a UI ser construída.

O conjunto completo de funcionalidades abaixo é o destino do produto, não o recorte da v1. Faseamento sugerido (a confirmar nos planos de execução):

- **Descoberta (antes do banco):** explorar a API do Pluggy e **mapear os endpoints e campos** que serão usados (contas, transações, investimentos, categorias). Confirmar o endpoint de categorias de transação e se ele permite **criar categorias novas**. Esse mapeamento define o que precisa ser modelado e como a categorização e a importação funcionam — é insumo direto da Fase 0.
0. **Fundação (sem UI):** modelagem completa do banco (todas as entidades + `user_id` + migrations) e endpoints **CRUD** com validação Pydantic, isolamento por usuário (repositórios) e testes no CI contra **SQLite e PostgreSQL**. **Um** modo de deploy primeiro.
1. **Núcleo:** integração Pluggy → importação de transações → flags de *transferência* e *revisada* → categorização (auto + override) → contas/cartões/faturas → **primeiras telas** + dashboard básico.
2. **Acompanhamento:** orçamentos, objetivos, assinaturas.
3. **Investimentos:** consumo dos dados do Pluggy + comparação com indicadores de mercado.
4. **Complementos:** notificações no Telegram, divisão de contas, segundo modo de deploy, PWA.

---

## 3. Personas e modos de uso

- **Local (desktop):** monousuário. Acesso local, sem cadastro/login de múltiplos usuários.
- **Self-hosted:** multiusuário. Uma instância atende vários usuários, cada um com dados isolados.
- **Usuário "somente divisão":** tem conta na instância self-hosted **mas não necessariamente usa o acompanhamento de gastos** — pode usar apenas o módulo de divisão de contas (ver 4.11).

---

## 4. Funcionalidades

### 4.1 Cadastro e configurações iniciais

Na criação da conta, dados coletados:

- **Obrigatórios:** Nome, E-mail.
- **Opcionais** (registro/documentação para uso pessoal): Data de nascimento, Salário mensal, Formação, Ocupação atual.

**Fontes de renda.** A renda variável (e a fixa) é modelada como uma entidade própria `fonte_de_renda`, em vez de um campo estático, com:

- `nome`
- `tipo` (`fixa` | `variável`)
- `valor_estimado`
- `recorrência` (mensal, trimestral, semestral, anual, irregular)
- `fonte` (empregador/cliente)

Serve para documentar as expectativas de renda e, no futuro, permitir comparação previsto × realizado (ligando as fontes às transações de crédito reais). Essa ligação previsto × realizado fica para uma evolução posterior.

### 4.2 Contas, cartões e faturas

Modelo explícito de **instituições**, **contas** (corrente, investimento) e **cartões de crédito**.

- Um cartão de crédito possui **faturas**.
- Uma despesa de cartão entra na fatura por **competência** (quando o gasto ocorre).
- O **pagamento da fatura** é uma **transferência** da conta corrente para o cartão (regime de **caixa**).
- Tratamento explícito de competência × caixa para **não contabilizar o gasto duas vezes** (uma na despesa do cartão, outra no pagamento da fatura).

### 4.3 Importação de dados (Open Finance / Pluggy)

Na v1, a importação é via Pluggy. Cada usuário cria seu próprio app no Pluggy e conecta as contas pelo Meu Pluggy (necessário para usar o nível gratuito).

Por conta conectada são necessários:

- `clientId`
- `clientSecret`
- `itemId` (recuperado da conexão com o Meu Pluggy)

Via API, recuperamos:

- `apiKey`
- `connectToken`
- Contas disponíveis: descrição, `accountId` e demais dados retornados pelo endpoint
  - Endpoint: `GET https://api.pluggy.ai/accounts?itemId={{itemId}}`

Atualização das contas: **1×/dia** ou quando o usuário clicar em **atualizar conexão**.

Cada transação carrega dois campos de controle:

- **Transferência entre contas:** indica se a transação deve ser contabilizada nas entradas/saídas gerais.
- **Revisada:** indica se a transação já foi revisada pelo usuário.

> As credenciais do Pluggy por usuário são dados sensíveis e devem ser **criptografadas em repouso** — ver 5.5.
>
> **Atenção:** nem todo usuário tem dados importados. Há usuários que acessam **apenas** a divisão de contas (4.11).

### 4.4 Transferências entre contas

O comportamento de **duas pernas** (saída em uma conta + entrada em outra) só ocorre quando a transferência é entre **duas contas do próprio usuário, ambas conectadas ao sistema**. Nesse caso o Pluggy entrega as duas transações separadas, e o sistema precisa:

- **Identificar as duas pernas** (heurística por valor oposto, data próxima e contas do mesmo usuário).
- **Marcar ambas** com o flag de transferência, para que nenhuma das duas entre nas entradas/saídas gerais.

Demais casos **não geram par**:

- **Transferência para conta de outra pessoa / destino externo:** existe só a perna de **saída**. É uma transação normal, contabilizada nas saídas gerais (não recebe o flag de transferência por pareamento).
- **Transferência para uma conta do usuário que não está conectada:** também aparece como perna única; o sistema não tem a contraparte para parear. O flag de transferência pode ser aplicado **manualmente** pelo usuário se ele quiser excluí-la das entradas/saídas.

Ou seja: o pareamento só dispara quando a contraparte existe entre as contas conectadas do usuário; na ausência de contraparte, trata-se como transação comum. Essa regra é parente do problema de deduplicação e deve ser tratada junto.

### 4.5 Categorização de transações

- Cada transação recebe **categoria** e **subcategoria**, podendo ser categorizada também em momento posterior.
- Classificação automática inicial usando a **API do Pluggy**; o usuário pode **alterar e salvar**.
- Aplica-se a transações de **cartão** e de **contas bancárias**.
- O **mapeamento** entre a taxonomia do Pluggy e a taxonomia de categorias/subcategorias do sistema é definido na **fase de descoberta** (§2). O Pluggy expõe um endpoint de categorias de transação que, ao que tudo indica, permite criar categorias novas — a descoberta confirma o comportamento e define como integrar.

### 4.6 Orçamentos por categoria

- Limite de gasto mensal para categorias/subcategorias escolhidas pelo usuário.
- Alertas ao atingir **50%, 75%, 90% e 100%** do orçamento.
- **Regra:** a soma dos orçamentos das subcategorias **não pode ultrapassar** o orçamento da categoria (validação no backend).
- Canais de alerta: in-app e Telegram (4.12).

### 4.7 Assinaturas

- Detecção automática de assinaturas quando o dado vier do Pluggy; caso contrário, **inclusão manual** das assinaturas vigentes.
- O usuário categoriza as assinaturas (ex.: alimentação, streaming, ferramentas de edição), seguindo, quando possível, a categorização das transações.
- Visões: **total gasto** com assinaturas, **total por categoria** e **lista** das assinaturas vigentes.

### 4.8 Objetivos

- Campos: título, descrição, justificativa e valor-alvo.
- Um objetivo pode estar vinculado a **uma ou mais** contas e/ou investimentos; a soma dos saldos vinculados é o valor guardado até o momento.
- **Decisão consciente:** uma conta ou investimento pode estar vinculada a **no máximo um** objetivo (nunca mais de um). Aceita-se a limitação de não fracionar uma conta entre objetivos.

### 4.9 Investimentos

Todos os investimentos de todas as contas são importados e armazenados.

- **O Pluggy já entrega os valores calculados** (valor investido, valor bruto atual, IR e IOF quando elegível). O sistema **consome** esses valores; **não recalcula impostos** por conta própria.
- **Renda variável** (bolsa): cada compra com preço da ação e quantidade; agrupamento por ativo com valor total investido, valor bruto atual e valorização.
- **Fundos imobiliários:** lista de proventos pagos e *dividend yield* do período analisado (o usuário pode querer DY de um mês ou semana específicos).
- Investimentos podem estar ligados a objetivos, respeitando a regra 1:1 de 4.8.

**Comparação de carteira com indicadores** (IBOV, IPCA, CDI e outros), no período escolhido:

- O usuário escolhe quais indicadores ver, dentro da lista disponível.
- Recortes: carteira inteira / só renda fixa / só renda variável / por tipo de ativo (CDB, Tesouro Direto, FII, etc.).
- **Dependência externa:** fonte de dados de mercado (B3, brapi ou similar) para os indicadores — registrada em 5.6.

### 4.10 Dashboards

- Dados agregados no período escolhido (diário, semanal, mensal, anual).
- Dados completos: listas de transações, entre outras visualizações a definir na implementação da UI.
- Cortes de período usam o fuso **America/Sao_Paulo** (relevante para "fim do dia", resumos diários/semanais).

### 4.11 Divisão de contas

Módulo deliberadamente **simples e restrito** (réplica reduzida do Splitwise), focado no uso pessoal; pode ser expandido depois.

Cada usuário adiciona uma despesa a dividir, com valor, descrição, categoria e modo de divisão:

- pago por mim e dividir igualmente;
- pago por mim e eu recebo tudo;
- pago por outro usuário e dividir igualmente;
- pago por outro usuário e ele recebe tudo.

Restrições de escopo:

- Só é possível dividir com quem **tem conta na mesma instância**.
- Um usuário pode existir na instância **somente para divisão** de contas, sem usar o acompanhamento de gastos.

### 4.12 Notificações no Telegram

Bot opcional, configurado no primeiro uso.

- Na primeira execução, o usuário opta por usar ou não as notificações; se sim, é apresentado um **passo a passo** de configuração do bot. O fluxo precisa capturar o `chat_id` **após o usuário dar `/start`** (o bot não consegue iniciar conversa sozinho).
- **Nova transação reconhecida:** aviso. Como o sync é diário/sob demanda, as transações de um mesmo sync devem ser **agregadas numa só mensagem**, não uma mensagem por transação.
- **Transações não revisadas:** aviso **2×/dia** em horários escolhidos pelo usuário, enquanto houver pendência.
- **Resumo diário** ao fim do dia (ativável/desativável).
- **Resumo semanal** em dia escolhido pelo usuário (ativável/desativável).

---

## 5. Requisitos e especificações técnicas

### 5.1 Hospedagem e execução

Dois modos, mesma base de código; o comportamento varia **apenas por configuração**.

**Self-hosted (VM / container):**

- Instalável como container Docker, distribuível via GitHub.
- **Secrets de runtime** (chave de assinatura de sessão, senha do banco, credenciais por usuário) geridos no ambiente do container em execução — não em segredos de CI/CD nem embutidos na imagem.
- **Aviso de atualização:** o app **não se atualiza sozinho**. Ele apenas exibe uma **notificação de que há nova versão disponível**, com o **que muda nela (changelog)**, checando a última release no GitHub. A atualização em si é feita pelo usuário, externamente (pull da nova imagem / recreate do container).
- Webapp com instalação mobile via **PWA**.

**Local (desktop):**

- App **standalone** instalável em Linux, Windows e Mac via **pywebview** (carrega a SPA em `localhost`).
- Dados sempre locais; demais funcionalidades preservadas.

### 5.2 Backend

**Framework e stack**
- **FastAPI** (Python), servindo a API e o frontend buildado a partir de um único servidor ASGI.
- Validação de entrada/saída via **Pydantic**, com modelos explícitos para as entidades principais (valores monetários, datas, categorias, etc.).
- Acesso a dados via **SQLAlchemy** (ORM).
- Documentação da API gerada automaticamente (OpenAPI/Swagger).

**Modo de execução único**
- O mesmo servidor FastAPI atende aos dois modos: atrás de reverse proxy no self-hosted e embutido em `localhost` no desktop. Não há duas implementações.

**Síncrono vs. assíncrono**
- Padrão: **rotas síncronas** com SQLAlchemy síncrono, priorizando simplicidade e previsibilidade.
- **async** permitido de forma pontual onde houver ganho concreto (I/O externo, integrações), nunca como padrão geral.

**Modos de uso e multiusuário**
- **Local:** monousuário, sem cadastro/login.
- **Self-hosted:** multiusuário, dados isolados por usuário.
- **Schema único** para os dois modos: toda entidade de domínio carrega `user_id`; no modo local, opera-se com um usuário implícito/fixo.

**Isolamento de dados (self-hosted)**
- Requisito de segurança: nenhum usuário acessa dados de outro sob nenhuma circunstância.
- Toda leitura/escrita filtrada pelo usuário autenticado, aplicada na **camada de acesso a dados** (repositórios).
- Coberto por **testes automatizados** específicos.

**Autenticação (self-hosted)**
- Cadastro e autenticação obrigatórios.
- Senhas com hashing seguro (**bcrypt** ou **argon2**), nunca em texto plano.
- Sessão **no servidor** via **cookie `httpOnly` `Secure` `SameSite`** (ID opaco de sessão, não JWT), com proteção **CSRF**. A tabela de sessões no banco permite revogação imediata (logout, "sair de todos os dispositivos").
- **Recuperação de senha (sem e-mail):** via **TOTP** (`pyotp`) — segredo gerado no cadastro, exibido como QR code, armazenado criptografado no banco; o "esqueci a senha" valida um código de 6 dígitos do app autenticador antes de permitir nova senha. O mesmo TOTP serve como **2FA**.
- **Backstop:** **reset administrativo por CLI** (ex.: `app reset-password <email>`), executável pelo dono da instância, cobrindo a perda do dispositivo autenticador.
- **Códigos de recuperação** de uso único (hash no banco) ficam como melhoria opcional posterior.

**Arquitetura interna**
- Separação clara: **rotas** (API), **serviços** (lógica de negócio), **repositórios/ORM** (acesso a dados).
- Regras de negócio não residem nas rotas.

**Qualidade e testes**
- Lógica de negócio e isolamento cobertos por testes, executados no CI contra **SQLite e PostgreSQL**.

### 5.3 Frontend

**Arquitetura geral**
- **SPA**: arquivos estáticos carregados e renderizados pelo navegador, sem servidor de frontend em execução.
- Os mesmos estáticos atendem aos dois modos: servidos pelo FastAPI no self-hosted e via `localhost`/**pywebview** no desktop.
- Sem SSR; interface montada no cliente, consumindo a API.

**Framework e stack**
- **React** + **TypeScript**.
- Build com **Vite** (modo SPA, sem meta-frameworks de SSR).
- Tipagem ponta a ponta: cliente de API **tipado a partir do schema OpenAPI** gerado pelo FastAPI.

**Interface e estilização**
- Componentes via **shadcn/ui** (copiados para o projeto, mantidos como código próprio).
- **Tailwind CSS** como base de estilo.
- Acessibilidade e comportamento de base via **Radix UI**.
- Componentes complexos (ex.: tabela com ordenação/paginação/filtro) com **TanStack Table**.
- **Design tokens** centrais (cor primária, cores para valores positivos/negativos, espaçamento, tipografia), respeitando contraste/acessibilidade.

**Estado e dados**
- Estado de servidor (contas, transações, categorias, orçamentos) via **TanStack Query**.
- Estado local de UI via recursos nativos do React (`useState`/`useContext`); estado global só com necessidade concreta.

**Roteamento**
- **React Router** no cliente; URLs refletem o estado de navegação (`/transacoes`, `/contas/:id`), com links diretos e voltar/avançar.

**Formulários e validação**
- **React Hook Form** + **Zod**, integrados ao shadcn/ui.
- Validação no frontend **complementa**, não substitui, a validação do backend (Pydantic é a fonte de verdade).

**PWA (self-hosted)**
- Instalável como **PWA** (manifest + service worker via `vite-plugin-pwa`); exige HTTPS (atendido pelo reverse proxy).
- **Sem offline:** o PWA é **apenas instalável** (atalho na home + HTTPS); não há funcionamento offline. O service worker fica mínimo, sem cache de dados da API.

### 5.4 Banco de dados

**Estratégia geral**
- Modelo único via SQLAlchemy; o banco varia por configuração. Sem duas implementações de schema.

**Local (desktop)**
- **SQLite** em arquivo único (ex.: `financas.db`).
- **WAL** habilitado (`PRAGMA journal_mode=WAL`).
- Backup = copiar o arquivo; restauração = substituí-lo. O sistema deve facilitar exportação/importação.

**Self-hosted (VM / container)**
- **PostgreSQL** como serviço; conexão por configuração (env var / arquivo em volume), sem credenciais na imagem.
- Backup do Postgres via rotina (`pg_dump`) — definir nos planos de execução.

**Valores monetários**
- Armazenados como **INTEGER em centavos** em todo o sistema, evitando imprecisão de ponto flutuante e divergência de comportamento entre SQLite e PostgreSQL.

**Histórico de edições**
- **Não há** versionamento/histórico de edições de transações (decisão consciente).

**Migrations**
- Versionamento via **Alembic**; migrations aplicadas automaticamente no boot, evoluindo o schema sem perda de dados; comportamento idêntico nos dois bancos.

**Compatibilidade e qualidade**
- Acesso na camada do ORM; evitar SQL cru e tipos específicos de um dialeto.
- Suíte de testes no CI contra **SQLite e PostgreSQL** (paridade entre os modos).

### 5.5 Segurança e privacidade

- **Isolamento multiusuário** como requisito de segurança, aplicado na camada de repositório e coberto por testes (ver 5.2).
- **Senhas** com bcrypt/argon2.
- **Credenciais do Pluggy por usuário** (`clientSecret`, `apiKey`, etc.) são dados sensíveis e devem ser **criptografadas em repouso no banco** — criptografia na camada da aplicação, com chave proveniente do ambiente; **nunca em texto plano**.
- **LGPD:** o sistema lida com dados financeiros e pessoais sensíveis. Campos pessoais do cadastro são opcionais; considerar recursos de exportar/excluir os próprios dados. No self-hosted, deixar claro que o administrador da instância controla o banco.

### 5.6 Integrações e dependências externas

- **Pluggy (Open Finance):** importação de contas/transações e **valores de investimento já calculados** (investido, bruto, IR, IOF).
- **Fonte de dados de mercado** (B3, brapi ou similar): indicadores IBOV/IPCA/CDI e outros, para a comparação de carteira (4.9).
- **Telegram Bot API:** notificações (4.12) — atentar a rate limits e à restrição do `/start`.

---

## 6. Decisões de projeto registradas

| # | Decisão | Status |
| --- | --- | --- |
| 1 | Moeda única: **BRL** | Definido |
| 2 | Valores monetários armazenados como **INTEGER em centavos** | Definido |
| 3 | **Sem histórico de edições** de transações | Definido |
| 4 | Uma conta/investimento serve **no máximo um** objetivo | Definido (consciente) |
| 5 | IR/IOF e valores de investimento **consumidos do Pluggy**, não recalculados | Definido |
| 6 | Campos pessoais do cadastro (salário, nascimento, formação, ocupação, rem. variável) **opcionais** | Definido |
| 7 | Divisão de contas **simples e restrita**; só com usuários da mesma instância | Definido |
| 8 | Conceito explícito de **fatura** de cartão (competência × caixa) | Definido |
| 9 | Pareamento de transferência só para **conta→conta do próprio usuário** (ambas conectadas); demais casos = perna única | Definido |
| 10 | Credenciais Pluggy **criptografadas em repouso** | Definido |
| 11 | v1 importa **apenas via Open Finance** (Pluggy) | Definido |
| 12 | App **não se atualiza sozinho**: só notifica nova versão + changelog (via GitHub); update feito externamente | Definido |
| 13 | Sessão **no servidor via cookie `httpOnly`** (não JWT), com CSRF e revogação por tabela de sessões | Definido |
| 14 | Desktop **standalone via pywebview**, monousuário, sem login | Definido |
| 15 | Recuperação de senha **sem e-mail**: **TOTP** (`pyotp`, também 2FA) + **reset administrativo por CLI**; códigos de recuperação opcionais depois | Definido |
| 16 | Sequência: **banco completo + backend CRUD testado antes de qualquer tela** (Fase 0) | Definido |
| 17 | Renda modelada como entidade **`fonte_de_renda`** (nível 2); previsto × realizado fica para depois | Definido |
| 18 | PWA **apenas instalável**, sem offline | Definido |
| 19 | **Fase de descoberta** da API Pluggy antes de modelar o banco | Definido |
| 20 | Orçamento: **soma das subcategorias ≤ orçamento da categoria** | Definido |

---

## 7. Pontos em aberto

Os pontos de modelagem anteriores foram resolvidos (ver decisões 17–20). O único item que depende de investigação externa — o **mapeamento da taxonomia de categorias do Pluggy** — passou a ser tratado na **fase de descoberta** (§2), e não como pendência de modelagem.

Não há pontos em aberto que bloqueiem o início da fase de descoberta ou da Fase 0.
