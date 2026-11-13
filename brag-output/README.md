# Vídeo de apresentação do mango

Vídeo de 25 segundos, horizontal (1920 × 1080, 30 fps), em português, com textos
e trilha instrumental. Capturas do frontend real com dados fictícios, sem narração.

## Arquivos para o site

- `brag.mp4`: H.264/AAC, yuv420p e faststart para reprodução na web.
- `brag.jpg`: capa extraída de um momento estável do dashboard; também é o frame zero do MP4.
- `captions.vtt`: legendas em português, incluindo contexto da interação.
- `embed.html`: trecho de incorporação com controles, descrição acessível e créditos.
- `share-copy.txt`: texto curto para divulgação.

Copie o MP4, a capa e as legendas para `/videos/mango/` no site e adapte os caminhos
de `embed.html` ao projeto. O player usa `preload="none"` e não inicia sozinho.
Mantenha o crédito da trilha junto do vídeo (ver `CREDITS.md`).
Esta pasta não publica nem modifica o site automaticamente.

## Editar e renderizar novamente

Requisitos: Node 22+, FFmpeg/FFprobe e Chrome/Chromium compatível com Hyperframes.

```bash
cd brag-output
npm install
npx hyperframes browser ensure
npm run preview
npm run render
```

É possível reutilizar um navegador existente definindo `HYPERFRAMES_BROWSER_PATH`
com o caminho do executável. `HYPERFRAMES_FFMPEG_PATH` e
`HYPERFRAMES_FFPROBE_PATH` são opcionais para binários fora do PATH.

`render.mjs` executa check, renderiza localmente, escolhe a capa em 5,4 s, aplica-a
somente ao primeiro quadro e verifica duração, dimensões, áudio e formato de pixel.
Se editar o roteiro, ajuste também o timestamp da capa, as legendas e o tempo esperado
no script. Os arquivos temporários ficam em `.render-tmp/` (ignorados pelo Git).

O roteiro está em `brag-plan.md`; a composição editável está em
`composition/index.html`. As dependências visuais e de áudio são locais.
Hyperframes 0.8.189 e Playwright 1.64.1 estão fixados no package.json.
O render desativa telemetria e não usa serviço de renderização remoto.

## Refazer as capturas

Com as dependências de `frontend/` instaladas, inicie o servidor de demonstração
em um terminal, a partir da raiz do projeto:

```bash
cd brag-output
npm run serve:demo
```

Ele usa a configuração e a interface existentes, com leitura de `.env`, variáveis
`VITE_` do ambiente e proxy para o backend desativados. Escuta somente em
`http://127.0.0.1:5177`.

Em outro terminal:

```bash
cd brag-output
npm run capture
```

O script usa um contexto novo de navegador e responde às chamadas da API com
fixtures locais; chamadas desconhecidas e solicitações externas são bloqueadas.
Não depende de backend, login, banco de dados ou `.env`. O script guarda as capturas
e coordenadas da interação em `composition/assets/screens/`.

Se o Playwright estiver instalado em outro local, `PLAYWRIGHT_MODULE` pode apontar
para seu `index.mjs`. Para a instalação padrão, use `npx playwright install chromium`
se o navegador ainda não estiver disponível.

Para reutilizar outro Chromium instalado, defina `CHROMIUM_EXECUTABLE` com o caminho
do executável antes de rodar a captura.

## Verificação da entrega

O `hyperframes check` passou nos testes de runtime, layout, animação e contraste
(18/18 verificações de texto editorial WCAG AA). Restam sete avisos de organização
da composição: cenas no mesmo arquivo e repetição do logo; não há erros de validação.
Os quadros decodificados do MP4 foram inspecionados, incluindo a confirmação da
revisão em 12,6 s. A validação automática de contraste não examina os textos dentro
das capturas rasterizadas do app.

A captura foi repetida com `serve-demo.mjs`: nenhum erro JavaScript ou solicitação
inesperada, e a mutação de revisão foi atendida pela fixture. O vídeo contém 750
quadros, duração de 25 s, trilha AAC e índice MP4 antes dos dados de mídia (faststart).
