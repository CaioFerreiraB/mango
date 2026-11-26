# Design

Sistema visual da SPA do mango. Os tokens vivem em `frontend/src/index.css` (Tailwind v4,
`@theme`), gerados a partir do preset **shadcn `b5vp08Sh6`** (style `radix-nova`, base neutra
`mist`) e estendidos com tokens próprios. shadcn/ui é mantido como código próprio em
`frontend/src/components/ui`. Este documento descreve o sistema; o CSS é a fonte de verdade.

## Theme

- **Claro e escuro**, alternados pela classe `.dark` no `<html>` (ThemeProvider; opção Sistema segue
  `prefers-color-scheme`). `color-scheme: light dark` declarado no HTML.
- **Accent do usuário:** a cor principal é uma preferência (Configurações → Preferências do
  sistema), persistida em `Usuario.accent` e espelhada em `localStorage["accent"]`
  (`frontend/src/lib/accent.ts` aplica no boot, antes do primeiro paint — sem flash). Estado =
  atributo `data-accent` no `<html>`; **sem atributo = violeta default**.
- Estratégia de cor: **Restrained** (padrão de produto) — superfícies neutras + um acento. O acento
  carrega ação primária, seleção, indicador de estado e a **tinta da sidebar/fundo**; nunca
  compete com dados.

## Color (OKLCH)

- **Primária (accent):** default violeta `oklch(0.491 0.27 292)` claro / `oklch(0.432 0.232 292)`
  escuro. Presets: violeta, tangerina, lima, azul, rosa, grafite (`ACCENTS` em `lib/accent.ts` tem
  os hex para swatches; ids antigos manga/verde/teal migrados em `c4f8a2e61d07`). Cores **vivas**
  (tangerina, lima — e grafite no escuro, que vira cinza-claro) levam **texto escuro por cima**
  (`--primary-foreground` do preset), como o verde do Wise: nunca escurecer a cor para caber
  branco — era o que deixava o antigo manga com cara de ferrugem.
- **Derivação (relative color syntax):** um preset define o par `--primary` (e, se a cor for
  viva/clara, o `--primary-foreground` escuro) em `html[data-accent="x"]` + variante `.dark` em `frontend/src/index.css`; todos os demais tons
  derivam via `oklch(from var(--primary) …)` dentro do bloco `@supports` — **nunca duplicar tokens
  derivados num preset**. Derivam: `--primary-foreground`, `--sidebar`
  (`oklch(0.972 0.009 h)` = #F6F5FB no violeta), `--sidebar-accent` (pill do item ativo),
  `--sidebar-primary`, `--sidebar-border` e a rampa `--chart-1..5`. Os blocos `:root`/`.dark`
  estáticos são o fallback para engines sem RCS.
- **Superfícies (identidade aprovada em 2026-11-26):** página e sidebar **brancas e contínuas**
  (sem "corpo flutuante"); superfícies **neutras** — o accent **nunca** pinta fundo de card nem de
  página. Cards brancos **sem borda**, só profundidade (`--shadow-card`: contato quase invisível +
  sombra difusa e baixa, como o Wise; no escuro, fio de borda no lugar). Card clicável sobe 3px
  com `--shadow-card-hover` (`superficie-interativa`). Raio de card `rounded-2xl`; botões em
  pílula. O accent aparece em: ícones e linhas (`text-accent-icone` = cor **exata** do accent),
  texto realçado (`text-accent-ink`, ajustado p/ 4,5:1), botão primário/aba ativa
  (`bg-marca-forte` + `text-primary-foreground`), fundo claro de atalhos redondos
  (`color-mix(in oklab, var(--primary) 13%, var(--background))` — **sempre oklab**: em oklch o
  matiz 0 do branco puxa para o rosa), relevo atrás do mascote e gráficos.
- **Tinta do texto:** slate (`--foreground` `oklch(0.3 0.016 255)`; dark off-white `0.93`), nunca
  preto/branco puros. Sidebar um degrau abaixo (`--sidebar-foreground`), ícones mais um
  (`--sidebar-icon`); item ativo = **pílula neutra que desliza** entre os itens (uma só, medida e
  movida por `transform`; ver `usePilulaAtiva` em `app-sidebar.tsx`) com ícone em `accent-icone`;
  seção fechada com a página atual dentro vira o item ativo; seções abrem/fecham animando a altura.
- **Neutros (`mist`):** cinzas levemente frios (hue ~214) para superfícies, bordas e texto —
  `--background/card/muted/secondary/accent/border/input/ring` **não** derivam do accent.
- **Semânticos:** `destructive` (vermelho) para ações destrutivas/erro. Tokens próprios para
  **valores financeiros** — `--positive` `#4268F1` e `--negative` `#F36846` (cores da marca, iguais
  nos dois temas; não derivam do accent) para **preenchimento** (barras, heatmaps, badges). Número
  em **texto** usa `text-positive-ink`/`text-negative-ink` (mesmo matiz com contraste AA por tema) e
  texto **sobre** o preenchimento cheio usa `text-positive-foreground`/`text-negative-foreground`.
  Badge tem variantes `positive`/`negative` em pílula para deltas. Regra: valor nunca depende **só** de cor
  (ver PRODUCT.md / a11y). **Azul só junto do `+`:** `<Valor>` pinta positivo apenas com `sinal`
  (fluxo, resultado, delta); saldo, limite, orçado, meta e restante são grandezas e ficam na cor do
  texto. Negativo segue coral (o "-" já está no texto). `<Valor>` é indivisível
  (`whitespace-nowrap`) salvo com `quebraMoeda`.
- **Estados:** `--success`/`--warning` (+ `-ink`, mesma divisão fill × ink) para status e
  progresso — pago/revisado/concluído, pendente/perto do limite. Nada de paleta crua do Tailwind
  (`amber-500`, `red-600`…) fora de `components/ui`. A escala de consumo do orçamento é
  sucesso → aviso (≥75%) → negativo (≥100%) e **não usa o accent** (o preset tangerina repetiria o
  coral de "estourou").
- **Charts (Apache ECharts):** todo gráfico passa pelo wrapper `components/common/echart.tsx` e
  pelas peças de `components/common/graficos-base.tsx` (`GraficoLinhas`, `GraficoBarras`, `Rosca`,
  `Sparkline`); cores vêm dos tokens resolvidos por `useTemaGrafico`/`useCores`
  (`lib/echart-tema.ts`), que re-renderizam ao trocar tema/accent. Identidade (categoria, classe,
  indicador) usa a **paleta categórica validada** `--chart-cat-1..8` (ordem fixa, nunca ciclada;
  9ª+ em `--chart-cat-outras`); indicadores têm cor fixa por entidade (`COR_INDICADOR`). Uma série
  única/destaque usa o accent; a rampa `--chart-1..6` (derivada do accent) fica para magnitude.
  Um eixo Y por gráfico (R$ e % viram vistas separadas). Tooltip escapa nomes vindos do usuário.

## Typography

- **Uma família:** **Manrope** (variable, `@fontsource-variable/manrope`), via `--font-sans`;
  `--font-heading` aponta para a mesma — sem par display/corpo (registro de produto).
- **Escala em rem fixa** (não fluida): hierarquia por peso/tamanho discretos, contraste comedido
  (proporção ~1.125–1.2). Medida de prosa 65–75ch; tabelas podem correr mais densas.

## Spacing & Radius

- **Raio base** `--radius: 0.625rem`, com escala `sm/md/lg/xl/2xl…` derivada. Cantos suaves,
  consistentes entre componentes.
- Espaçamento da escala Tailwind; ritmo variado (não um único gap padrão). Conteúdo central em
  `max-w-[100rem]` com padding responsivo (`p-4 md:p-6`); telas de formulário limitam a própria
  largura (ex.: Configurações em `max-w-5xl`).

## Components

- **shadcn/ui** (Radix por baixo) como vocabulário único: `button`, `sidebar`, `breadcrumb`,
  `dropdown-menu`, `sheet`, `tooltip`, `separator`, `skeleton`, `avatar`, `input`. Mesma forma de
  botão e mesmos controles em todas as telas.
- **Padrões próprios** em `components/common`: `PageHeader`, `CardDestaque`/`Kpi`/`GRADE_KPI`
  (`kpi.tsx`), `Selo` (status), `EmptyState` (vazio que ensina, com `cena` opcional), `Mascote`,
  `Valor` e `PlaceholderPage`. Todo componente interativo cobre default/hover/focus/active/
  disabled; carregamento usa **skeleton**, não spinner solto.

## Anatomia de página

Toda tela autenticada segue a mesma gramática — é o que faz o app parecer um produto só.

1. **`PageHeader`** (`components/common/page-header.tsx`): `h1` + **uma** linha de descrição
   (sempre presente) à esquerda, ações à direita — no máximo **uma** primária, o resto `outline`.
   No celular as ações ficam na linha do título e viram ícone (`max-sm:sr-only` no rótulo); a
   descrição desce para a largura toda. Exatamente um `h1` visível por tela (o 404 usa
   `EmptyState tituloComo="h1"`). O Dashboard saúda pelo horário de Brasília.
2. **Linha de controles** (período, mês, filtros, busca) logo abaixo; no celular atrás de
   "Filtros" quando forem muitos.
3. **Abas de seção da página** = `TabsList variant="line"` com `w-full justify-start border-b`
   (sublinhado no accent). Troca de visão dentro de card/período = `ToggleGroup size="sm"
   variant="outline"`. Configurações: abas viram `Select` abaixo de `md`.
4. **Herói** = `CardDestaque` — **no máximo um por tela** (`data-destaque`), só onde existe um
   número-âncora (saldo, patrimônio, alocado, total mensal, restante do orçamento, saldo das
   divisões, total da fatura). Card branco como os outros, número grande (800, tabular), linha de
   contexto, gráfico em sangria opcional (`grafico`) e `mascote` opcional **em cena** (abaixo).
   Olho de privacidade quando a página tem modo privacidade. Sozinho na linha: `sm:max-w-md`;
   com KPIs: `col-span-2` numa grade de 2/4 colunas. O Início tem o próprio herói (`FaixaMarca`).
5. **KPIs** = `Kpi` (rótulo, valor `text-lg→xl font-semibold tabular-nums` por container query,
   detalhe opcional, visual em sangria opcional), sem ícone decorativo. Grade padrão `GRADE_KPI`
   (auto-fit, mín. 10rem). Nada de card dentro de card (o antigo `StatChip` saiu).
6. **Conteúdo**: cards/tabelas. Card clicável inteiro: `superficie-interativa` (sobe com sombra,
   afunda 1% no clique; `motion-reduce` desliga); linha de lista dentro de card: hover como um
   "card" arredondado (`rounded-xl hover:bg-muted`) com o contêiner tendo o mesmo respiro nos
   quatro lados (`p-2 md:p-3`), sem divisórias.
7. **Status** = `Selo` com tons `neutro|apagado|info|sucesso|aviso|perigo`
   (`components/common/selo-tons.ts`): a mesma palavra tem a mesma cara em qualquer tela
   ("Em aberto" é sempre neutro, "Pendente" sempre aviso, "Atrasada" sempre perigo).
8. **Vazio**: sempre `EmptyState`; tela sem dados **não** mostra herói/KPIs zerados antes do vazio.
9. **Datas em tabela/lista**: `formatDataCurta` (`23 nov`, ano só fora do corrente) — nunca data
   truncada com "…". Coluna inteira de "—" não aparece (Carteira oculta Instituição/Cotação vazias).
10. **Detalhe** (conta, fatura): breadcrumb no desktop; botão "← Voltar" só no mobile.
11. **Início (`/`) é o hub** (usabilidade Nubank): herói com saudação sorteada (`SAUDACOES`) +
    saldo + curva de 30 dias + mascote em cena; 8 atalhos redondos ("Revisar" em amarelo-manga
    com contador); "Precisa da sua atenção" (fila, atrasos, estouros — cada item leva à tela);
    "Seu mês" em 6 seções clicáveis; últimas transações. As análises personalizáveis moram em
    `/dashboard`.

## Illustrations

Mascote do mango em PNG, em `frontend/public/illustrations/avatars/avatar_{1..4}/` com o padrão
`avatar-{n}-{cena}.png`. O usuário escolhe **qual avatar** o representa (Preferências do sistema,
persistido em `Usuario.avatar`); toda ilustração de mascote resolve o caminho **exclusivamente**
via `ilustracao(avatar, cena)` de `frontend/src/lib/illustrations.ts` — nunca hardcodar `avatar_1`.
`AVATARES_DISPONIVEIS` lista os avatares com assets (hoje só o 1; 2–4 aparecem "em breve").

- **Cenas e onde usar:** `default` (perfil/NavUser/geral), `goal` (objetivos), `money`
  (dashboard/renda), `money-v2` (telas públicas: first-run e definição de senha por convite),
  `subscriptions` (assinaturas), `scared`/`super-scared` (alertas, com gradação; `scared` também na
  recuperação de senha), `thumbs-up` (celebração/sucesso), `hang-loose`/`surf`/`mango-juice`/
  `bar-scene` (empty states leves e login).
- **Composição em camadas** — um card ou página compõe livremente **dados + ilustração +
  decorativos**, nesta ordem de empilhamento (z), de trás para frente: decorativos (blobs,
  ícones marca-d'água, gradientes) → ilustração → **dados**. Ilustração pode sobrepor
  decorativos; **nunca sobrepõe dados — dados sempre por cima**.
- **Sangria:** a ilustração pode ir **até a borda do card** (card com `relative overflow-hidden`,
  imagem posicionada absoluta encostando na borda), inclusive cortada pelo raio do card.
- **Padrões de posicionamento** (referências): lateral (mascote ancorado num lado, conteúdo no
  outro), inferior (na base do card), marca-d'água (versão translúcida ao fundo), celebração
  (junto a um resultado positivo), "em cena" (ambiente ilustrado envolvendo o dado). Elementos de
  apoio: icon chips (`size-9 rounded-lg bg-primary/10 text-primary`), badges pílula
  `positive`/`negative` para deltas, progress com trilha tintada (`bg-primary/10`).
- **Onde o mascote aparece (papel = momentos):** estados vazios (`EmptyState cena`), 404, chat,
  telas públicas e **um por herói** — reagindo ao estado quando faz sentido (despesas fixas:
  `scared` com atraso, `thumbs-up` tudo pago; orçamento: `scared` ao estourar). `bar-scene` tem
  fundo próprio: não usar em vazio/herói.
- **Mascote em cena** (`CenaMascote`, `components/common/mascote-cena.tsx`): no canto inferior
  direito do herói, do tronco para cima, **cortado pela borda de baixo** do card, com **curvas de
  nível (relevo topográfico)** no accent atrás, que derivam devagar e somem em direção ao texto.
  Entra subindo uma vez e fica **parado** (sem reagir ao mouse — testado e rejeitado). Tamanho
  pela largura do **card** (container query, não a janela): compacto até `@xl`, médio até `@4xl`,
  grande acima; **nunca** sobrepõe texto (no celular aparecem só cabeça e tronco, dentro da faixa
  do gráfico). A imagem precisa de `max-w-none` (o reset do Tailwind a encolhe). Tooltip de gráfico
  vai para o `body` (`appendTo`), senão fica atrás do mascote.
- **Sidebar: nunca** — ilustração não entra na sidebar; é território de navegação.
- **Telas públicas** (setup, aceite de convite, login, recuperação) usam o `AuthShell`
  (`frontend/src/components/auth/auth-shell.tsx`): painel de marca tintado (`bg-primary/5`, grade de
  pontos decorativa) com logo + wordmark, `h1` e mascote em sangria na base, ao lado do painel de
  formulário — empilhado no mobile (logo → mascote → texto), duas colunas a partir de `md`. Sem
  sessão não há avatar escolhido: a cena resolve no `AVATAR_PADRAO`. A marca nessas telas é o logo
  PNG + wordmark (o badge `Citrus` segue valendo no resto do produto).
- Ilustração é decoração progressiva: `alt=""` quando não carrega informação, e a tela precisa
  funcionar sem ela.

## Motion

- Transições de **150–300 ms** com `--ease-out` (`cubic-bezier(0.23,1,0.32,1)`); movimento
  comunica estado e dá resposta ao toque: card sobe no hover, botão/atalho encolhe no clique,
  atalho se enche de cor a partir do centro e o ícone balança, chevron anda, pílula da sidebar e
  sublinhado das abas deslizam, valores fazem tween ao mudar (`<Valor animado>`), barras crescem
  e gráficos "desenham" na entrada, troca de rota com fade + 8px + leve blur.
- **Coreografia do Início** (skill `choreograph`): herói → mascote → atalhos em onda → seções →
  lista, total ≈ 0,5 s, intervalos encolhendo (`entra` + `--atraso/--dist/--escala/--blur`); o
  invólucro da rota não anima no Início (uma entrada por contêiner).
- `prefers-reduced-motion: reduce` desliga/encurta toda animação (ex.: o toggle de tema usa
  `motion-reduce:transition-none`).

## Layout & Iconography

- **App shell (desktop, ≥ `md`):** sidebar à esquerda (colapsável em ícones; "Recolher menu" no
  rodapé, junto do usuário — não disputa o topo com a navegação) + header com
  `SidebarTrigger`, breadcrumb (derivado do `handle` das rotas) e troca de tema no rodapé da
  sidebar. Conteúdo no `Outlet` do React Router. Responsividade **estrutural**
  (colapsar/empilhar), não tipografia fluida.
- **App shell (mobile, `< md`):** duas peças de navegação.
  - **Topbar (proposta C, "título grande que encolhe"):** no topo é transparente, só com botões
    **redondos** no accent (`BOTAO_TOPO_MOBILE`, `components/layout/topo.ts`: ☰, busca,
    assistente; ícone em `primary-foreground`, sem sombra colorida) — o título grande é o `h1` da
    página. Ao rolar ganha fundo branco **sólido**, cantos de baixo levemente arredondados (ainda
    encostada nas bordas) e sombra leve — sem linha, sem vidro — e o nome da página aparece pequeno
    no centro. O ☰ abre a própria sidebar como gaveta lateral (sheet do shadcn) — a IA completa,
    com seções recolhíveis e o menu do usuário (tema, Sair) no rodapé.
    No mobile as linhas têm 44px e texto 15px, e a linha "Recolher menu" some. Trocar de rota fecha
    a gaveta.
  - **Barra de atalhos** (`frontend/src/components/layout/bottom-nav.tsx`): **pílula flutuante**
    só de **ícones** (nome em `sr-only`/`title`), quase opaca (`bg-background/93` + blur leve),
    `--shadow-pop`, aba ativa numa pílula `bg-marca-forte`, com **Início fixo + 3 atalhos** que o usuário escolhe em
    Configurações → Preferências (`perfil.atalhos_mobile`; catálogo `ATALHOS` e
    `atalhosEfetivos()` em `frontend/src/config/nav.ts` — id desconhecido cai, faltante completa
    com o padrão). Escolher um atalho que já está noutra posição troca os dois de lugar. Conta de
    divisão tem barra fixa (Divisão + Configurações).
  - **Filtros de página** no mobile ficam atrás de um botão "Filtros" (com o resumo do valor atual)
    que abre um drawer inferior — o topo da página não acumula controles. Botões de ação do topo
    viram só ícone (`max-sm:sr-only` no rótulo).
  - **Card de destaque (herói — ver §Anatomia de página):** card branco com o número-âncora
    grande. Mede o próprio espaço (`@container`). Um por tela, no máximo. O olho dele liga o **modo privacidade de todos os cards** do painel
    (valor e tooltip da mini-área mascarados, lembrado no navegador); sem o card de saldo, o olho
    vai para a barra do topo.
  - **Safe area obrigatória:** a barra fica `env(safe-area-inset-bottom)` + 0.75rem acima da borda,
    e o conteúdo reserva `--bottom-nav-h` + safe area + folga no `pb` do `<main>`, senão a barra
    `fixed` cobre o fim da página. Toasts usam o mesmo `mobileOffset`.
  - Escondida por CSS (`md:hidden`), **nunca** por `useIsMobile()` — o hook começa `false` e
    piscaria a barra no primeiro paint do desktop.
  - **Portal para o `body`**, como todo `fixed` do shadcn (sheet, dialog, drawer): dentro do
    `SidebarInset` bastaria um ancestral ganhar `transform`/`filter`/`backdrop-filter` para virar
    o containing block e a barra rolar junto com o conteúdo em vez de ficar presa à viewport.
  - **Ilustração: nunca** — mesma razão da sidebar; é território de navegação.
- **Painéis de detalhe** (transação em `transacao-detalhe.tsx`, ativo em `ativo-drawer.tsx`): um
  único `Drawer` do vaul que troca de eixo — `direction="right"` no desktop (painel flutuante com
  `inset-y-2`) e `direction="bottom"` no mobile (bottom sheet com alça e arraste-para-fechar).
  - Aqui `useIsMobile()` **é permitido**, ao contrário da bottom bar: `direction` é comportamento
    do vaul (eixo da animação e do arraste), não dá para resolver com `md:`, e o painel nasce
    fechado — o `false` do primeiro paint não pisca nada.
  - Overrides de estilo sempre **prefixados por direção** (`data-[vaul-drawer-direction=…]:`), para
    o modo que não está em uso desligar sozinho. Altura fixa no bottom (`h-` **e** `max-h-`, senão
    o `max-h-[80vh]` da base vence) e `paddingBottom: env(safe-area-inset-bottom)` só no mobile.
- **Ícones:** **lucide** apenas (um set). Marca: ícone `Citrus` em badge da cor primária + wordmark
  "mango".
