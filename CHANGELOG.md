# Changelog

Todas as mudanças relevantes deste projeto são registradas aqui.

O formato segue [Keep a Changelog](https://keepachangelog.com/pt-BR/1.1.0/) e o versionamento segue
[SemVer](https://semver.org/lang/pt-BR/). Enquanto a versão for **0.x**, mudanças incompatíveis podem
sair numa versão *minor* — a superfície pública (API HTTP, variáveis de ambiente, schema do banco)
ainda está se assentando. Cada versão publicada tem uma imagem correspondente em
`ghcr.io/caioferreirab/mango`; instruções de upgrade em [deploy/README.md](deploy/README.md).

## [Não publicado]

### Adicionado

- **Listagem de transações mais limpa por padrão** — dois filtros novos, ambos ligados quando você
  abre a página, em **Mais filtros**:
  - **Ocultar pagamentos de fatura**: o débito que quita a fatura do cartão sai da lista. Ele não é
    um gasto novo — as compras que ele paga já estão ali —, e vê-lo ao lado delas só atrapalha a
    conferência. Se você recategorizar um pagamento à mão, ele volta a aparecer: a sua decisão vale
    mais que a do banco.
  - **Ocultar lançamentos futuros**: uma compra em 6× chega como seis lançamentos, um por mês, e os
    cinco que ainda não aconteceram ficavam no topo da lista, empurrando o presente para baixo.
    Agora a página começa no dia de hoje. Nada é apagado — desligue o filtro para ver o quadro
    inteiro, e o detalhe da fatura continua mostrando todas as parcelas.

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

[Não publicado]: https://github.com/CaioFerreiraB/mango/compare/v0.1.1...HEAD
[0.1.1]: https://github.com/CaioFerreiraB/mango/compare/v0.1.0...v0.1.1
[0.1.0]: https://github.com/CaioFerreiraB/mango/releases/tag/v0.1.0
