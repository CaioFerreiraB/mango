# Brag Plan: mango

Vídeo de apresentação para o site, pt-BR, 1920 × 1080, 30 fps, 25 segundos.
Direção escolhida: demonstração do produto, textos e trilha, sem narração.

## O produto e o ângulo

O mango reúne finanças pessoais, importação via Open Finance, revisão de
transações e planejamento. Código aberto, atualmente distribuído para hospedagem
própria. A ideia é mostrar a passagem de números dispersos para um mês compreensível.
Tom `polished`: calmo, preciso e próximo, sem promessas de economia ou gamificação.

## As nove respostas do brag

1. **O que é:** controle financeiro pessoal para brasileiros, com dados importados via Pluggy.
2. **Afirmação central:** “sem planilha”, do README; a tarefa central é revisar e entender.
3. **Gancho visual:** “Menos planilha. Mais clareza.” junto do dashboard real.
4. **UI:** dashboard, revisão de uma transação e orçamento; objetivo como apoio se legível.
5. **Duração mínima satisfatória:** 25 s para três demonstrações e leitura confortável.
6. **Tom:** polished; clareza e controle, identidade visual existente.
7. **Som:** trilha limpa e constante, dois cliques discretos e um acento de transição.
8. **Legenda:** mango: suas contas, transações e planos em uma visão mais clara.
9. **Fluxo:** entender o mês → conferir uma transação importada → acompanhar o orçamento.

## Identidade e fontes

- Manrope variável, a mesma fonte do frontend, servida localmente.
- Branco e fundo violeta muito claro (#F6F5FB), tinta quase preta; accent do produto
  `oklch(0.491 0.27 292.581)` convertido para sRGB quando necessário ao renderizador.
- Logo oficial e capturas das rotas originais. Não redesenhar componentes.
- Mascote adicional somente resolvido por `ilustracao(AVATAR_PADRAO, cena)`.
- Fontes dos claims: README.md, PRODUCT.md, routes/dashboard, routes/transacoes,
  routes/orcamentos e routes/objetivos. Não prometer tempo real, SaaS ou app para baixar.

## Storyboard

| Tempo | Cena | Texto principal | Ação / transição |
|---|---|---|---|
| 0–3,27 s | Gancho com marca e detalhe real do dashboard | Menos planilha. Mais clareza. | Headline entra rápido e permanece; tela se abre para a próxima cena. |
| 3,27–8,74 s | Dashboard real | Seu mês, em uma visão. | Mostra saldo, entradas, saídas; foco nos dados. Apoio: Importação via Open Finance. |
| 8,74–14,20 s | Transações reais | Importe. Revise. Pronto. | Cursor seleciona uma transação e confirma a revisão; corte entre capturas dos estados reais. |
| 14,20–20,19 s | Orçamento real | Dê direção aos seus planos. | Enquadramento evidencia consumo por categoria; objetivo pode entrar como detalhe, sem competir com leitura. |
| 20,19–25 s | Encerramento com marca | Conheça o mango. | Código aberto. No seu servidor. Logo permanece estável por mais de 2 s. |

Os textos explicativos são camadas editoriais do vídeo, não funcionalidades novas.
Dados numéricos e identidade da pessoa são fictícios. Captura usa contexto novo de
navegador, respostas locais interceptadas e bloqueio de rede externa; nenhum banco,
credencial ou .env é lido. “Demonstração com dados fictícios” aparece no vídeo.

## Som e ritmo

Trilha: Happy Beats / Business Moves, vol. 12, Sascha Ende (ende.app), CC BY 4.0.
Ganho 0,28–0,35; fade de entrada curto e saída de 1,2 s. Sem narração.
SFX: cliques baixos na interação e uma batida suave na revelação; sem som de moedas.
Music cue guidance: preset do brag, ~109,96 BPM. Entrada de UI em 3,27 s,
troca em 8,74 s (strong cue), planejamento em 14,20 s e outro em 20,19 s.
Leitura prevalece sobre sincronismo. Títulos ficam imóveis depois de entrar.
Audio-reactive treatment: none; a estabilidade dos dados financeiros é parte da direção.
O crédito da trilha estará no arquivo de créditos e na integração de exemplo do site.

## Entrega

MP4 H.264/AAC com faststart; JPEG de capa escolhido num momento legível e aplicado
ao frame zero; composição editável, script de captura, texto de divulgação e exemplo
de incorporação acessível. Criação e renderização locais; publicação fora deste escopo.
