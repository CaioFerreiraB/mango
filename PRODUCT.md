# Product

## Register

product

## Users

Pessoa física no Brasil cuidando das **próprias finanças** — gastos do dia a dia, cartões,
orçamentos, objetivos e investimentos. Dois contextos de uso, mesma base de código:

- **Desktop (local):** monousuário, sem login, dados sempre locais (app via pywebview).
- **Self-hosted:** multiusuário com dados isolados, acesso web + mobile (PWA).

O trabalho central não é "lançar dados" e sim **revisar e entender** o que o Open Finance (Pluggy)
já importou: conferir transações, marcar transferências/revisadas, categorizar, acompanhar limites e
metas. Há também o usuário **"somente divisão"**, que usa apenas a divisão de contas.

## Product Purpose

Substituir a planilha de finanças pessoais por um sistema que **importa sozinho** (Open Finance),
trata corretamente competência × caixa (faturas de cartão), separa transferências das entradas/saídas
reais e dá visão de orçamentos, objetivos e investimentos. Moeda única **BRL**, valores sempre
exatos (centavos). Sucesso = o usuário confia nos números e revisa o mês em minutos, não horas.

## Brand Personality

Sóbrio, preciso, confiável. A voz é direta e em português claro, sem jargão financeiro nem
"gamificação". O sentimento-alvo é **calma e controle** — dinheiro é assunto sensível; a interface
tranquiliza por clareza e exatidão, nunca por alarme ou entusiasmo forçado.

## Anti-references

- Dashboard-SaaS genérico (cards iguais com ícone+título+número, fundo creme/bege "de IA").
- Fintech neon/gamificada (confete, medalhas, gradientes berrantes sobre saldo).
- "Mar de gráficos" decorativos que competem com o dado.
- Planilha crua exposta como UI (grades sem hierarquia, tudo no mesmo peso).

## Design Principles

1. **A ferramenta some na tarefa.** Familiaridade ganha (padrão Linear/Stripe): navegação e
   componentes previsíveis; surpresa só onde agrega.
2. **O dado fala primeiro.** Densidade quando útil, zero ruído decorativo. Cor e peso destacam o que
   importa (valores, pendências), não molduras.
3. **Confiança por precisão.** Centavos exibidos com exatidão; positivo × negativo sempre legível;
   cortes de período no fuso America/Sao_Paulo. Nada de número ambíguo.
4. **Nenhum estado órfão.** Toda tela cobre vazio (que ensina o próximo passo), carregando (skeleton)
   e erro (claro, com saída). O esqueleto já nasce com esse vocabulário.
5. **Sobriedade com dado sensível.** Privacidade e calma acima de espetáculo; o self-hosted deixa
   claro que o administrador controla o banco.

## Accessibility & Inclusion

Alvo **WCAG 2.1 AA**. Texto de corpo ≥ 4.5:1 (≥ 3:1 para texto grande); foco sempre visível;
operação completa por teclado; `prefers-reduced-motion` honrado em toda animação. **Cor nunca é o
único portador de significado** — entradas/saídas se distinguem também por sinal (+/−) e contexto,
não só por verde/vermelho (daltonismo). Português (pt-BR) como idioma base.
