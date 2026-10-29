# Telegram e sincronização diária

A integração é opcional e começa desligada, nos modos local e self-hosted. Cada instalação usa
um bot exclusivo. O token pertence à instalação; cada pessoa confirma seu próprio Telegram e
recebe somente suas transações.

## Configurar a instalação

Em **Configurações → Telegram**, somente administradores veem o bloco **Bot desta instalação**.
Os demais usuários veem o próprio vínculo e a preferência de relatório.

O administrador:

1. Cria um bot com `/newbot` no [BotFather](https://t.me/BotFather).
2. Cola o token em **Bot desta instalação** e seleciona **Salvar e validar token**.
3. Ativa **Integração Telegram**. Não é preciso configurar webhook nem abrir uma porta pública.

O botão **Revisar no Mango** usa automaticamente o endereço com que a instalação foi acessada ao
salvar, ativar ou validar o bot. Não é necessário informar uma URL; a origem do navegador mantém
o endereço público mesmo quando a API fica atrás de um proxy. Em endereços de loopback
(`localhost`, `127.0.0.1` ou `::1`), o relatório é enviado sem o botão.

**Validar conexão do bot** testa o token salvo sem enviar dados financeiros. Tokens são cifrados
em repouso e nunca exibidos pela API. Trocar o token do mesmo bot preserva vínculos; trocar de bot
exige confirmação e nova vinculação de todos. Remover o bot preserva a configuração do sync.

Use um processo da aplicação por instalação, como no Dockerfile padrão. Não compartilhe o mesmo
bot com outra instalação ou ferramenta: somente um consumidor pode receber seus updates. Um
webhook já existente causa erro de configuração; o Mango não o remove automaticamente.

## Configurar a sincronização

Em **Configurações → Conexões**, ative **Sincronização automática diária** e escolha o horário.
O padrão é 08:00 no fuso America/Sao_Paulo. No self-hosted, somente o administrador altera essa
configuração, que vale para todos os usuários ativos de conta completa com conexões bancárias.
No modo local, o próprio usuário configura. A sincronização independe da integração Telegram.

## Vincular sua conta

1. Selecione **Vincular Telegram** e **Abrir Telegram**.
2. No Telegram, toque em **Iniciar** e volte ao Mango.
3. Confira nome, username e ID apresentados e selecione **Confirmar minha conta**.
4. Ative **Receber relatório diário de pendências**. Use **Enviar teste** para conferir o destino.

O link expira em dez minutos e só pode ser usado uma vez. Se recarregar a página sem guardar o
link, gere um novo. Não é necessário descobrir ou informar IDs manualmente. Grupos não são aceitos.
Desvincular desativa o relatório e cancela envios ainda pendentes. Uma identidade Telegram só pode
estar ligada a uma conta Mango por instalação. IDs do CRUD antigo precisam de nova confirmação.

## O que chega no relatório

Após o sync completo, o bot envia a quantidade e até dez transações mais recentes, com data,
descrição e valor. O resumo respeita a data de corte de revisão e oculta lançamentos futuros e
pagamentos de fatura, como a lista padrão. Débitos têm sinal negativo e créditos positivo, inclusive
quando o banco envia compras de cartão com valor positivo. Sem pendências, não há mensagem.

A sincronização importa os dados disponíveis no Pluggy; não força uma nova coleta no banco.
Sync manual não dispara mensagens adicionais. Desativar Telegram não desativa o sync automático.
Ativar o relatório depois de uma rotina concluída vale para a próxima rotina diária.

No modo local, o Mango precisa estar aberto. Ao abrir depois do horário, recupera somente a rotina
do dia atual. Não acumula relatórios dos dias em que ficou fechado. O mesmo vale após reinício do
self-hosted.

## Falhas e recuperação

- Erros de sync transitórios têm até três tentativas: a inicial, mais uma após cinco minutos e
  outra após quinze minutos. Falha parcial não autoriza relatório e não interrompe outros usuários.
- Uma falha de entrega não repete o sync. O prazo pedido pelo Telegram em caso de limite é respeitado.
- Se a entrega ficar incerta (por exemplo, timeout depois do envio), não há reenvio automático
  naquele dia. Isso evita duplicatas; o erro aparece nas configurações.
- Token revogado suspende o transporte. Substitua-o ou valide a conexão e ative a integração.
- Se bloquear o bot, o relatório individual é desligado. Desbloqueie e ative o relatório novamente.

Revisão por botões e conversa com LLM/Axon ficam para versões futuras.
