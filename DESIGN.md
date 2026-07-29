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
- **Neutros (`mist`):** cinzas levemente frios (hue ~214) para superfícies, bordas e texto —
  `--background/card/muted/secondary/accent/border/input/ring` **não** derivam do accent.
- **Semânticos:** `destructive` (vermelho) para ações destrutivas/erro. Tokens próprios para
  **valores financeiros** — `--positive` e `--negative` (não derivam do accent; badge tem variantes
  `positive`/`negative` em pílula para deltas). Regra: valor nunca depende **só** de cor
  (ver PRODUCT.md / a11y).
- **Charts:** rampa `--chart-1..5` derivada do accent (monocromática por matiz).

## Typography

- **Uma família:** **Manrope** (variable, `@fontsource-variable/manrope`), via `--font-sans`;
  `--font-heading` aponta para a mesma — sem par display/corpo (registro de produto).
- **Escala em rem fixa** (não fluida): hierarquia por peso/tamanho discretos, contraste comedido
  (proporção ~1.125–1.2). Medida de prosa 65–75ch; tabelas podem correr mais densas.

## Spacing & Radius

- **Raio base** `--radius: 0.625rem`, com escala `sm/md/lg/xl/2xl…` derivada. Cantos suaves,
  consistentes entre componentes.
- Espaçamento da escala Tailwind; ritmo variado (não um único gap padrão). Conteúdo central em
  `max-w-6xl` com padding responsivo (`p-4 md:p-6`).

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
  (dashboard/renda), `subscriptions` (assinaturas), `scared`/`super-scared` (alertas, com
  gradação), `thumbs-up` (celebração/sucesso), `hang-loose`/`surf`/`mango-juice`/`bar-scene`
  (empty states leves).
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
- Ilustração é decoração progressiva: `alt=""` quando não carrega informação, e a tela precisa
  funcionar sem ela.

## Motion

- Transições de **150–250 ms**, ease-out; movimento comunica **estado** (hover, foco, abrir/fechar),
  nunca decoração. Sem sequência coreografada no load (produto carrega para a tarefa).
- `prefers-reduced-motion: reduce` desliga/encurta toda animação (ex.: o toggle de tema usa
  `motion-reduce:transition-none`).

## Layout & Iconography

- **App shell:** sidebar à esquerda (offcanvas no mobile via `sheet`) + header fixo com
  `SidebarTrigger`, breadcrumb (derivado do `handle` das rotas) e troca de tema. Conteúdo no
  `Outlet` do React Router. Responsividade **estrutural** (colapsar/empilhar), não tipografia fluida.
- **Ícones:** **lucide** apenas (um set). Marca: ícone `Citrus` em badge da cor primária + wordmark
  "mango".
