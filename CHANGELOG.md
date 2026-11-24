# Changelog

Todas as mudanças relevantes deste projeto são registradas aqui.

O formato segue [Keep a Changelog](https://keepachangelog.com/pt-BR/1.1.0/) e o versionamento segue
[SemVer](https://semver.org/lang/pt-BR/). Enquanto a versão for **0.x**, mudanças incompatíveis podem
sair numa versão *minor* — a superfície pública (API HTTP, variáveis de ambiente, schema do banco)
ainda está se assentando. Cada versão publicada tem uma imagem correspondente em
`ghcr.io/caioferreirab/mango`; instruções de upgrade em [deploy/README.md](deploy/README.md).

## [Não publicado]

## [0.10.0] — 2026-11-24

### Adicionado

- **Visão competência × caixa no dashboard:** um seletor no topo troca os cards, os gráficos e as
  abas Receitas/Despesas entre **Competência** (compra no cartão conta na data da compra, sem o
  pagamento da fatura) e **Caixa** (só o que saiu da conta: o pagamento da fatura entra, na
  categoria "Pagamento de cartão", no lugar das compras do cartão). A escolha fica lembrada neste
  navegador. Orçamento e painel de cartões continuam em competência.
- **Divisão por porcentagem e por valor:** além de "dividir igualmente" e "valor integral", cada
  pessoa pode ter uma porcentagem (soma 100%) ou um valor (soma o total da despesa). Com duas
  pessoas, digitar a parte de uma preenche a da outra com o complemento. Na edição, mudar o total de
  uma divisão por porcentagem recalcula os valores pelas mesmas porcentagens.
- **Transação com valor diferente da divisão:** ao vincular, escolha entre **manter a divisão** — o
  orçamento conta o valor da transação menos a parte dos outros (ex.: divisão de R$ 100 em 50/50 numa
  transação de R$ 150 → R$ 100 no orçamento) e quanto eles devem não muda — ou **reajustar a
  divisão** ao valor da transação, na mesma proporção. O detalhe da transação mostra a conta.

### Corrigido

- **Pagamento de fatura não conta mais duas vezes:** sai das somas também quando a categoria
  "Pagamento de cartão" vem de uma regra, de uma assinatura ou de uma recategorização recente — não
  só quando o banco já a informa. E quando o banco chama o pagamento de boleto ou PIX, o débito na
  conta é ligado ao "pagamento recebido" do cartão (mesmo valor, até 3 dias) e passa a ser tratado
  como pagamento de fatura.

### Alterado

- Aba Despesas: "Maiores estabelecimentos" virou **"Maiores despesas"**, já que os valores são
  somados pela descrição da transação.

## [0.9.0] — 2026-11-23

### Adicionado

- **Dashboard em abas — Geral, Receitas e Despesas:** a Geral mantém os cards, as últimas
  transações, entradas e saídas e a evolução patrimonial. **Receitas** traz a evolução por
  dia/semana/mês/ano, a distribuição por categoria, as principais fontes de receita, previstas
  (orçamento de receita) × realizadas e o acumulado vs. o período anterior. **Despesas** traz a
  evolução empilhada por categoria, a rosca de categorias (movida da Geral), os maiores
  estabelecimentos, despesas × orçamento do mês, o acumulado com o ritmo do orçamento, a média por
  dia da semana, a divisão por meio de pagamento (com a quebra por conta/cartão) e o painel de
  cartões (movido da Geral). Clicar numa categoria, fonte, estabelecimento, meio ou categoria do
  orçamento abre as transações correspondentes, somando exatamente o valor do gráfico. A aba fica
  na URL (`?aba=receitas`) e os gráficos de série ganharam a granularidade anual.
- **Nova navegação no celular:** o menu completo abre pelo ☰ no topo, como uma gaveta lateral, e
  a barra inferior virou uma pílula flutuante com o Início e mais três atalhos que você escolhe em
  Configurações → Preferências → Atalhos do celular.
- **Saldo em destaque:** o saldo em contas ganhou um card na sua cor de destaque (celular e
  computador). O olho dele oculta os valores de todos os cards do painel e fica lembrado neste
  navegador; no celular, os outros cards ficam dois por linha.
- **Filtros do dashboard num botão** no celular, em vez de ocupar o topo da página.
- **Transações de uma categoria num clique:** nos gráficos de despesas por categoria (rosca,
  barras e empilhado), clicar numa categoria abre a lista das transações dela no período.
- **Últimas transações no dashboard:** as 10 mais recentes logo abaixo dos cards, com o aviso de
  transações pendentes acima da tabela.

- **Compra dividida nas transações:** no detalhe de uma saída, "Dividir" cria uma divisão
  pré-preenchida (valor, descrição, categoria, data) ou vincula uma divisão já existente que você
  pagou e ainda não tinha transação. A lista ganhou o marcador de divisão e o filtro "Divisão"
  (só divididas / sem divisão) em "Mais filtros".
- **Orçamento e dashboard contam só a sua parte:** compra dividida entra pelo valor da sua
  parcela; a parcela de uma divisão paga por outra pessoa também entra como gasto seu (na data e
  categoria da divisão) e aparece na lista de transações com "Pago por Fulano".
- **Divisões sem transação viram pendência:** ao criar uma divisão que você pagou, escolha a
  transação do banco (sugestões com o mesmo valor em ±7 dias), deixe para depois ou marque "paguei
  fora do banco". Sem transação, ela aparece em "Só pendentes" e no relatório diário do Telegram,
  com um interruptor próprio em Configurações → Telegram.
- **Orçamento em abas — Despesas, Investimentos e Receitas:** aportes em investimentos saem das
  despesas e ganham aba própria, medida em aportes líquidos (aportes − resgates). Juros e
  dividendos continuam em Receitas. Orçamentos de despesa em categorias de investimento são
  migrados automaticamente.
- **Dashboard personalizável:** "Personalizar" deixa ocultar, reordenar (arrastando ou com ▲ ▼)
  e mudar a largura de cada bloco (⅕ a inteira); os ocultos voltam por "Adicionar visualização".
  O layout fica salvo no seu perfil e vale em qualquer dispositivo.
- **Card "Investido no mês" e evolução patrimonial:** o dashboard mostra os aportes líquidos do
  mês e um gráfico mês a mês do patrimônio total (contas + investimentos) e líquido (descontado
  IR/IOF). Cartões ficam de fora.
- **Despesas por categoria com todas as despesas:** a rosca soma todas as categorias e as barras ao
  lado servem de legenda, com valor e percentual do período inteiro.
- **Painel de cartões no dashboard:** visão global (compras no mês, fatura atual, próximas
  faturas, total do ano e média mensal) e um bloco por cartão com fechamento/vencimento, limite
  comprometido (fatura atual + parcelas futuras) e disponível.
- **Busca global:** campo no topo (atalho Ctrl/⌘ K ou /) para achar páginas, configurações,
  contas, faturas e transações.

### Alterado

- **Investimento não é despesa no dashboard:** aportes em categorias de investimento saem das
  saídas (e resgates, das entradas) e passam a aparecer em "Investido". O resumo do assistente
  (MCP, chat e Telegram) segue a mesma regra.
- Dashboard: cards renomeados para "Saldo em contas" e "… no mês"; gráfico de entradas e saídas
  com o resultado como linha tracejada na cor de destaque e granularidade semanal por padrão;
  barras com largura proporcional ao período (dia < semana < mês); seletor de período no topo; o
  bloco "Período consolidado" saiu.
- Layout mais largo no desktop e tipografia mais suave: textos e ícones deixaram o quase-preto por
  tons de ardósia, e o item ativo da barra lateral ganhou a cor de destaque.
- Todos os gráficos passaram a usar Apache ECharts. Na Visão Geral de investimentos, valor (R$) e
  rentabilidade (%) viraram vistas separadas em vez de dois eixos no mesmo gráfico, e CDI, SELIC,
  IPCA e Ibovespa ganharam cores próprias e distinguíveis.

### Corrigido

- **Estorno no cartão abate a despesa:** crédito numa conta de cartão (estorno, crédito de compra)
  contava como receita, inflando as entradas. Agora reduz a despesa da categoria no dashboard e no
  orçamento; crédito categorizado como Renda (ex.: cashback) continua receita.
- **Compra de cartão aparecia como entrada (+R$)** na lista e no detalhe de transações; o sinal
  agora segue o tipo do lançamento.
- Criar uma divisão "Eu paguei" sem escolher ninguém deixava avançar e falhava no fim; agora o
  wizard exige ao menos uma pessoa.

## [0.8.0] — 2026-11-17

### Segurança

- **Freio de força-bruta no login e na recuperação de senha:** após 5 tentativas malsucedidas em
  15 minutos, as próximas são bloqueadas por 15 minutos (contado por e-mail e por IP). Fecha a
  porta à força-bruta do segundo fator (TOTP) e da recuperação de senha.
- **Cabeçalhos de segurança em todas as respostas HTTP:** Content-Security-Policy, HSTS,
  X-Content-Type-Options, X-Frame-Options e Referrer-Policy — defesa contra clickjacking,
  MIME-sniffing e downgrade de conexão. O mini app do Telegram mantém a CSP afrouxada de que
  precisa.

## [0.7.0] — 2026-11-13

### Adicionado

- **Assistente com IA dentro do Mango:** botão no canto superior direito da topbar. No desktop abre
  um painel à direita (a página continua usável) que pode ser expandido; no celular o chat ocupa a
  tela toda, numa topbar nova. Respostas em streaming com o Axon, várias conversas (histórico
  cifrado por sete dias), parar, gerar de novo e copiar. Alterações sugeridas pela IA aparecem num
  card para você aplicar ou descartar — a única exceção, como no Telegram, é a ordem exata "marque a
  transação N como revisada", aplicada na hora. Usa o mesmo provedor, consentimento e cota diária da
  conversa pelo Telegram.
- **Separar caixinhas do Nubank:** aba **Compras** no painel de renda fixa da Carteira — selecione
  aplicações e mova para um ativo com o nome da caixinha. O Pluggy manda cada aporte como "CDB - NU
  FINANCEIRA…" sem o nome da caixinha, então a separação é manual; depois dela, aportes recorrentes
  (mesma taxa, valor e dia do mês) seguem sozinhos para a caixinha certa, e os demais caem numa
  "caixa de entrada" para classificar.
- **Alterar credencial do Pluggy** em Configurações → Conexões: troque o clientSecret (girado no
  Pluggy) sem recriar as conexões; a credencial é testada ao salvar.

### Alterado

- Renda fixa bancária aparece com nome curto ("CDB · Nu Financeira") em vez da razão social inteira.

### Corrigido

- Sync de investimentos falhava quando o Pluggy mandava as taxas de um movimento (`expenses`) como
  objeto — caso das caixinhas/RDB do Nubank.

## [0.6.0] — 2026-11-13

### Adicionado

- **App instalável:** manifest e ícones do PWA — instalado na tela inicial, o mango abre em janela
  própria, sem a barra de endereço (reinstale o atalho existente para valer).

### Alterado

- **API de sincronização:** `POST /api/sync` e `POST /api/itens-pluggy/{id}/sincronizar` agora só
  disparam o sync e respondem `202` com o status; o resultado sai em `GET /api/sync/status`.

### Corrigido

- **Sincronização:** "Atualizar" não mostra mais "falha ao sincronizar" quando o sync demora — ele
  roda em segundo plano em vez de estourar o timeout do reverse proxy.
- **Sincronização:** a busca incremental vai até o último sync bem-sucedido, para não deixar buraco
  de transações se o sync ficar parado mais de 30 dias.

## [0.5.0] — 2026-11-06

### Adicionado

- **Orçamentos:** linha "Não planejado" com o gasto em categorias sem orçamento no mês e
  transações de cada linha direto na tabela.
- **Aviso de orçamento no Telegram:** ao passar de um percentual configurável (Preferências),
  no máximo um aviso por categoria por mês, com opção de desligar por categoria.

### Corrigido

- **Telegram:** mensagens saem formatadas (negrito, itálico, listas, código, links, citações,
  spoiler e tabelas alinhadas) em vez de exibir o Markdown cru (`**`); se o Telegram recusar a
  formatação, a mensagem é reenviada como texto puro.
- **Orçamentos:** o mês corrente não virava no fuso de Brasília (data interpretada em UTC no
  navegador).

## [0.4.0] — 2026-10-29

### Adicionado

- **Telegram v2:** miniapp HTTPS com revisão de transações, rascunhos por sessão e assistente de
  divisão de contas; comandos independentes de IA e processamento durável dos updates.
- **Inteligência artificial no Telegram:** provedores Axon e OpenAI-compatible, credenciais
  administrativas cifradas, consentimento individual, histórico de sete dias e limites de uso.
  Axon recebe autorização MCP temporária por execução, isolada por usuário. Exclusões, lotes
  e efeitos propagados exigem confirmação no Mango.
- **Revisão atômica:** prévia de efeitos, detecção de conflitos e idempotência para revisões,
  assinaturas/regras contextuais e criação de divisões. IA e miniapp começam desligados.

- **Telegram:** bot exclusivo por instalação, token cifrado e vínculo confirmado individualmente
  em Configurações → Telegram. Relatório opcional com até dez pendências após a rotina diária,
  com proteção contra reenvio em entregas incertas. Guia em [docs/telegram.md](docs/telegram.md).
- **Sincronização automática diária:** configuração em Conexões, com horário ajustável (08:00 Brasília por padrão), nos modos
  local e self-hosted, com recuperação do dia ao abrir e retentativas sem repetir relatórios.
  Sync e relatórios começam desligados.

### Alterado

- O CRUD `/api/config-telegram` foi substituído pelas operações verificadas `/api/telegram`.
  IDs antigos exigem nova vinculação; nenhum dado financeiro é alterado pela migração.

### Corrigido

- **Vínculo de investimentos em objetivos:** o seletor agora reúne as posições por ativo, como na
  carteira, e informa quantas estão disponíveis. Selecionar um grupo vincula suas posições livres
  em uma única operação; um conflito cancela o lote inteiro, sem transferir vínculos existentes.

## [0.3.0] — 2026-10-21

### Adicionado

- **MCP para agentes de IA:** Claude Code, Codex, Open WebUI, VS Code ou um bot no n8n podem
  consultar e editar seus dados pelo endereço `/mcp`. O que dá para fazer:
  - listar e buscar transações com todos os filtros da tela;
  - revisar e categorizar em lote;
  - ver contas, cartões e faturas;
  - acompanhar objetivos e orçamentos;
  - gerenciar assinaturas;
  - rachar despesas e ver quanto cada pessoa deve.

  Respostas em tabela markdown (ou lista, para chats sem tabela). Gráficos chegam como imagem, com
  versão interativa nos clientes que suportam. Liga, desliga, permissão (só leitura ou leitura e
  escrita) e token ficam em **Configurações → MCP**. Configurações do sistema nunca ficam
  acessíveis por ali. Guia em [docs/mcp.md](docs/mcp.md).

### Corrigido

- **Gasto no cartão abatia as saídas do dashboard.** O banco manda a compra de cartão com o sinal
  oposto ao da conta corrente, e o dashboard somava com sinal. Por isso saídas, gasto por categoria
  e a série mensal saíam menores, ou até negativos, para quem usa cartão. Agora vale a grandeza de
  cada lançamento.
- **Valor guardado dos objetivos chegava como texto no Postgres** (`"500000"` em vez de número).

## [0.2.0] — 2026-08-28

### Adicionado

- **Listagem de transações mais limpa por padrão** — dois filtros novos, ambos ligados quando você
  abre a página, em **Mais filtros**:
  - **Ocultar pagamentos de fatura**: o débito que quita a fatura do cartão sai da lista. Ele não é
    um gasto novo — as compras que ele paga já estão ali —, e vê-lo ao lado delas só atrapalha a
    conferência. Se você recategorizar um pagamento à mão, ele volta a aparecer: a sua decisão vale
    mais que a do banco.
  - **Ocultar lançamentos futuros**: uma compra em 6× chega como seis lançamentos, um por mês, e os
    cinco que ainda não aconteceram ficavam no topo da lista, empurrando o presente para baixo.
    Agora a lista termina em hoje — o histórico anterior continua inteiro. Nada é apagado: desligue
    o filtro para ver também o que está por vir, e o detalhe da fatura segue mostrando todas as
    parcelas.

- **Data de início da revisão** — em Configurações → Preferências dá para dizer a partir de quando
  você quer revisar suas transações. Conectar uma conta traz o histórico inteiro dela, e a fila de
  revisão nascia com anos de lançamentos que ninguém vai conferir. O que vem antes da data escolhida
  passa a aparecer como **"Ignorada"**: sai da contagem do dashboard e do filtro "Só pendentes", mas
  **não** é marcado como revisado — nada é reescrito, e você ainda pode revisar uma delas à mão.
  Mudar ou apagar a data tem efeito na hora, sem perder nada. Em branco (o padrão) tudo continua como
  antes: todo o histórico pede revisão.
- **Gestão de categorias** — dá para criar categorias próprias ("Pet", "Faculdade"), desativar as
  do banco que você não usa e ensinar o sistema a categorizar sozinho. Tudo numa aba nova em
  Configurações → Categorias.
  - **Categorias próprias**: nascem disponíveis em transações, orçamentos, assinaturas e divisões,
    como qualquer outra, com um **ícone à sua escolha** (44 opções) que aparece junto delas em toda
    a interface, igual às do banco. Só você as vê. Excluir é recusado se ela estiver em uso em algum
    orçamento.
  - **Ativar/desativar**: some dos seletores; desativar uma categoria-mãe alcança as filhas. A
    escolha é sua, não da instância — cada pessoa esconde o que quiser. Transação que o banco
    classificar numa categoria desativada passa a aparecer como "Desconhecida", com um ícone de
    interrogação — distinto da etiqueta genérica, porque é o único estado que pede uma ação sua.
  - **Regras automáticas**: um texto (exato ou "contém") mapeia para uma categoria, valendo para o
    histórico inteiro e para o que chegar depois. Dá para criar da própria transação, pelo atalho
    "Sempre categorizar «X» assim".
  - **Parcelas coerentes**: mudar a categoria de uma parcela muda todas as parcelas daquela compra.
    O agrupamento lê a descrição do cartão ignorando o contador ("Decolar Com **1/6**") e o sufixo
    societário ("DECOLAR COM **LTDA** 5/6") — é o que faz as parcelas de uma mesma compra se
    reconhecerem mesmo quando o banco não manda estabelecimento nem valor total. O aviso na tela
    passa a dizer quantas parcelas foram junto, em vez de prometer a propagação de antemão.
  - **Assinaturas mandam na categoria**: cobrança vinculada a uma assinatura usa a categoria dela e
    não é editável na transação — altere na assinatura e todas as cobranças acompanham.
  - A ordem de decisão é explícita: assinatura → seu ajuste manual → regra → sugestão do banco. Uma
    regra criada depois nunca desfaz uma correção que você fez à mão numa transação específica.
  - A migration é aditiva e roda sozinha na subida do container.

- **Descrição própria e observações na transação** — dá para escrever o que a transação realmente
  foi ("almoço com o time") em vez de conviver com o texto do banco, e anotar uma observação livre.
  Quando há descrição própria, ela vira o título na listagem e a do banco desce para o subtítulo;
  transações com observação ganham um ícone de nota. A busca passa a procurar também nesses dois
  campos. Ambos são editados no painel de detalhe e ficam protegidos do re-sync do Pluggy, que
  segue reescrevendo só a descrição de origem. A migration é aditiva (duas colunas anuláveis, sem
  backfill) e roda sozinha na subida do container.

## [0.1.1] — 2026-08-21

### Corrigido

- **Divisão de contas quebrava no PostgreSQL** — a aba Pessoas (`GET /api/divisao/pessoas`)
  devolvia HTTP 500 sempre que a lista misturava quem tem atividade recente com quem não tem, o que
  acontece quando a simplificação de dívidas traz uma contraparte sem despesa em comum. A ordenação
  comparava um `datetime` com fuso (o PostgreSQL devolve `TIMESTAMPTZ`) com um `datetime.min` sem
  fuso. Só afetava o PostgreSQL — ou seja, exatamente o self-hosted; no SQLite passava despercebido.

### Modificado

- O CI passa a resolver a versão do Node por `frontend/.nvmrc`, que não existia — o job de frontend
  falhava em toda execução desde que o workflow foi criado.
- Um teste de rota removida deixa de depender de haver build da SPA em `frontend/dist`. Com o build
  presente, o catch-all do `mount_spa` casa o caminho e um POST inválido vira 405 em vez de 404 — o
  teste passava na máquina do desenvolvedor e falhava no CI, que não builda o frontend.

## [0.1.0] — 2026-08-21

Primeira versão publicada. Imagem única servindo API e interface, instalável por Docker/Portainer.

### Adicionado

- **Importação por Open Finance (Pluggy):** conexão de instituições, sincronização incremental de
  contas, cartões, transações e investimentos, com throttle por item.
- **Transações:** categorização automática com override manual, detecção de transferências entre
  contas próprias (pareamento de duas pernas por valor e data) e marcação de "revisada".
- **Cartões e faturas:** modelo explícito de competência × caixa, para o gasto no cartão não ser
  contado duas vezes no fluxo de caixa.
- **Orçamentos:** limites mensais por categoria, materialização mensal automática e acompanhamento
  de consumo.
- **Objetivos:** metas com contas e investimentos vinculados, e progresso calculado.
- **Assinaturas:** detecção automática de recorrências a partir do histórico, cadastro manual e
  total mensal.
- **Investimentos:** renda fixa, ações e FIIs com proventos e dividend yield; snapshot diário de
  saldo; comparação com IBOV, CDI, SELIC e IPCA; fundamentos de FII a partir dos dados abertos da
  CVM.
- **Fontes de renda:** cadastro e acompanhamento das entradas recorrentes.
- **Divisão de contas:** despesas compartilhadas entre usuários da mesma instância, com otimização
  de acertos.
- **Dashboard:** visão consolidada do mês.
- **Multiusuário (self-hosted):** convites, administração de usuários, contas do tipo "somente
  divisão" com escopo restrito e isolamento de dados por usuário em todos os repositórios.
- **Interface:** SPA em React/TypeScript, tema claro/escuro, cor de destaque configurável e o
  mascote mango.
- **Assistente `/setup`:** primeiro acesso cria o usuário dono, ativa o 2FA e conecta o Pluggy.
- **Distribuição:** imagem multi-arquitetura (`linux/amd64`, `linux/arm64`) publicada no GHCR a cada
  tag, e stack pronta para o Portainer em [`deploy/docker-compose.yml`](deploy/docker-compose.yml).
  Migrations e carga inicial de categorias rodam no boot do container.

### Segurança

- Autenticação por senha (bcrypt) com **2FA (TOTP)** obrigatório, sessões no servidor e proteção
  CSRF nas mutações.
- Credenciais do Pluggy e token da brapi **cifrados em repouso** (Fernet).
- Guarda de boot que recusa subir em `self_hosted` com as chaves de desenvolvimento do repositório
  ou com chaves vazias.
- Suporte a segredos por arquivo em `/run/secrets/` (Docker secrets), além de variáveis de ambiente.
- Padrões de deploy endurecidos a partir de um deploy real em VM com Portainer e reverse proxy: a
  porta do app é publicada só em `127.0.0.1` (porta publicada pelo Docker não passa pelo `INPUT` do
  firewall do host), `POSTGRES_PASSWORD` é obrigatória — sem mais `mango/mango` —, o cookie de
  sessão nasce `Secure` e `FORWARDED_ALLOW_IPS` fica explícito para quem roda o proxy em container.

### Problemas conhecidos

- Os endpoints de autenticação ainda não têm rate-limiting nem lockout. Ver **Problemas conhecidos**
  em [ROADMAP.md](ROADMAP.md) antes de expor a instância à internet aberta.

[Não publicado]: https://github.com/CaioFerreiraB/mango/compare/v0.10.0...HEAD
[0.10.0]: https://github.com/CaioFerreiraB/mango/compare/v0.9.0...v0.10.0
[0.9.0]: https://github.com/CaioFerreiraB/mango/compare/v0.8.0...v0.9.0
[0.8.0]: https://github.com/CaioFerreiraB/mango/compare/v0.7.0...v0.8.0
[0.7.0]: https://github.com/CaioFerreiraB/mango/compare/v0.6.0...v0.7.0
[0.6.0]: https://github.com/CaioFerreiraB/mango/compare/v0.5.0...v0.6.0
[0.5.0]: https://github.com/CaioFerreiraB/mango/compare/v0.4.0...v0.5.0
[0.4.0]: https://github.com/CaioFerreiraB/mango/compare/v0.3.0...v0.4.0
[0.3.0]: https://github.com/CaioFerreiraB/mango/compare/v0.2.0...v0.3.0
[0.2.0]: https://github.com/CaioFerreiraB/mango/compare/v0.1.1...v0.2.0
[0.1.1]: https://github.com/CaioFerreiraB/mango/compare/v0.1.0...v0.1.1
[0.1.0]: https://github.com/CaioFerreiraB/mango/releases/tag/v0.1.0
