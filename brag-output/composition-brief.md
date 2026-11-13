# Hyperframes Composition Brief: mango

Criar vídeo local de 25 segundos em 1920 × 1080 / 30 fps a partir de brag-plan.md.
Saída: brag-output/composition/index.html e brag-output/brag.mp4.

## Material obrigatório

Capturas reais com fixtures fictícias em composition/assets/screens/, logo em
assets/mango-logo.png e fonte em assets/manrope-latin-wght-normal.woff2.
Preservar cores, componentes e hierarquia do produto. Não usar screenshots antigos
do README, pois não foram auditados para dados pessoais.

## Composição

Montagem limpa com enquadramentos amplos e aproximações intencionais. A tela do app
é a protagonista, títulos curtos têm áreas próprias. Gancho e encerramento podem
usar a marca maior. Nada de gráficos falsos, métricas inventadas como promessa,
gradientes decorativos, confete ou partículas. Dados de demonstração são rotulados.
Capturas podem ser recortadas para dar leitura, sem esconder o contexto da ação.
Títulos até 96 px e margens seguras de 90 px. Manrope, branco, tinta #111519,
fundo #F6F5FB e violeta do produto em sRGB. Sem alterar UI de produção.

O roteiro e seus cinco intervalos em brag-plan.md são o contrato criativo.
Manter apenas 1 mensagem principal por cena e holds de pelo menos 0,3 s por palavra.
A revisão deve usar capturas de antes/depois da interação real, com cursor animado
até o controle correspondente. Usar movimento para orientar, não para agitar números.

## Áudio

assets/music/bed.mp3 é o vol. 12 do brag. Usar data-volume=0.30, fade in 0.3 e
fade out 1.2. SFX locais discretos. Cues: 3.27, 8.74 (strong), 14.20, 20.19.
Arquivo de metadados em assets/music/cues.json. Audio-reactive treatment: none,
intencional pela estabilidade visual do assunto. Nenhuma narração.

## Runtime e validação

Usar Hyperframes instalado localmente e suas referências atuais de format, motion,
runtimes, look e CLI. Na versão 0.8.189, estas substituem os antigos nomes de
domain skills hyperframes-core/animation/creative/keyframes citados pelo brag.
Um root de duração 25 s, GSAP determinístico e pausado registrado em __timelines.
Assets locais, sem CDNs. Todos os quadros devem funcionar por seek independente.
Rodar lint, check (incluindo contraste e layout), snapshots e render; examinar os
quadros decodificados do MP4. Sem publicação remota ou telemetria.
