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
  escuro. Presets: violeta, manga, verde, azul, rosa, teal (`ACCENTS` em `lib/accent.ts` tem os hex
  para swatches).
- **Derivação (relative color syntax):** um preset define **só o par `--primary`**
  (`html[data-accent="x"]` + variante `.dark`) em `frontend/src/index.css`; todos os demais tons
  derivam via `oklch(from var(--primary) …)` dentro do bloco `@supports` — **nunca duplicar tokens
  derivados num preset**. Derivam: `--primary-foreground`, `--sidebar`
  (`oklch(0.972 0.009 h)` = #F6F5FB no violeta), `--sidebar-accent` (pill do item ativo),
  `--sidebar-primary`, `--sidebar-border` e a rampa `--chart-1..5`. Os blocos `:root`/`.dark`
  estáticos são o fallback para engines sem RCS.
- **Layout de cor:** corpo da página **branco** (`--background`) flutuante (`rounded-xl`, sombra)
  sobre fundo `--sidebar`; a sidebar usa a mesma tinta — o fundo atrás do corpo é sempre a cor da
  sidebar.
- **Tinta do texto:** slate (`--foreground` `oklch(0.3 0.016 255)`; dark off-white `0.93`), nunca
  preto/branco puros. Sidebar um degrau abaixo (`--sidebar-foreground`), ícones mais um
  (`--sidebar-icon`); item ativo = pill `--sidebar-accent` + texto/ícone `accent-ink`, hover em
  meia intensidade do pill.
- **Neutros (`mist`):** cinzas levemente frios (hue ~214) para superfícies, bordas e texto —
  `--background/card/muted/secondary/accent/border/input/ring` **não** derivam do accent.
- **Semânticos:** `destructive` (vermelho) para ações destrutivas/erro. Tokens próprios para
  **valores financeiros** — `--positive` e `--negative` (não derivam do accent; badge tem variantes
  `positive`/`negative` em pílula para deltas). Regra: valor nunca depende **só** de cor
  (ver PRODUCT.md / a11y).
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
- **Padrões próprios** em `components/common`: `EmptyState` (vazio que ensina) e `PlaceholderPage`
  (telas ainda não implementadas). Todo componente interativo cobre default/hover/focus/active/
  disabled; carregamento usa **skeleton**, não spinner solto.

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
  apoio: stat-chips sobrepondo painel tintado (`bg-primary/5..10`), icon chips
  (`size-9 rounded-lg bg-primary/10 text-primary`), badges pílula `positive`/`negative` para
  deltas, progress com trilha tintada (`bg-primary/10`).
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

- Transições de **150–250 ms**, ease-out; movimento comunica **estado** (hover, foco, abrir/fechar),
  nunca decoração. Sem sequência coreografada no load (produto carrega para a tarefa).
- `prefers-reduced-motion: reduce` desliga/encurta toda animação (ex.: o toggle de tema usa
  `motion-reduce:transition-none`).

## Layout & Iconography

- **App shell (desktop, ≥ `md`):** sidebar à esquerda (colapsável em ícones) + header com
  `SidebarTrigger`, breadcrumb (derivado do `handle` das rotas) e troca de tema no rodapé da
  sidebar. Conteúdo no `Outlet` do React Router. Responsividade **estrutural**
  (colapsar/empilhar), não tipografia fluida.
- **App shell (mobile, `< md`):** duas peças de navegação.
  - **Menu ☰ (topbar, à esquerda do título):** abre a própria sidebar como gaveta lateral (sheet
    do shadcn) — a IA completa, com seções recolhíveis e o menu do usuário (tema, Sair) no rodapé.
    No mobile as linhas têm 44px e texto 15px, e a linha "Recolher menu" some. Trocar de rota fecha
    a gaveta.
  - **Barra de atalhos** (`frontend/src/components/layout/bottom-nav.tsx`): **pílula flutuante**
    (`inset-x-4`, 0.75rem acima da borda, `rounded-[1.75rem]`, borda neutra suave e sombra **bem
    leve na cor do accent**), com **Início fixo + 3 atalhos** que o usuário escolhe em
    Configurações → Preferências (`perfil.atalhos_mobile`; catálogo `ATALHOS` e
    `atalhosEfetivos()` em `frontend/src/config/nav.ts` — id desconhecido cai, faltante completa
    com o padrão). Escolher um atalho que já está noutra posição troca os dois de lugar. Conta de
    divisão tem barra fixa (Divisão + Configurações). Ícone `size-6` + rótulo curto 11px; ativa é
    `text-accent-ink` (só cor, sem pílula), inativa `text-muted-foreground`.
  - **Filtros de página** no mobile ficam atrás de um botão "Filtros" (com o resumo do valor atual)
    que abre um drawer inferior — o topo da página não acumula controles. Botões de ação do topo
    viram só ícone (`max-sm:sr-only` no rótulo).
  - **Card de destaque (saldo no dashboard, mobile e desktop):** degradê `--destaque-a →
    --destaque-b` (accent com L normalizada 0.44 → 0.29 via RCS), texto branco, ondas SVG
    decorativas atrás do conteúdo. Mede o próprio espaço (`@container`): valor reduz em ⅕ de linha.
    Um por tela, no máximo. O olho dele liga o **modo privacidade de todos os cards** do painel
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
