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
4. Em contas completas, ative **Receber relatório diário de pendências**. Use **Enviar teste** para conferir o destino.

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


## Miniapp: revisão e divisões

No self-hosted, o administrador habilita **Miniapp do Telegram** e confirma a origem pública
HTTPS do Mango (por exemplo, `https://financas.exemplo.com`, sem caminho). O Mango configura o
menu **Abrir Mango** do bot. O relatório diário passa a abrir diretamente a revisão no miniapp.
Desktop continua usando o link normal do relatório.

A sessão do miniapp é separada do login web e dura uma hora. Abra pelo botão do bot; links abertos
fora do Telegram não autenticam. É preciso ter confirmado o vínculo no Mango. Desvincular ou
pausar o bot revoga as autorizações. Não é criada sessão administrativa.

Na revisão, **Salvar e próxima** grava todas as alterações juntas; **Pular** mantém o rascunho
na sessão e **Anterior** permite voltar, inclusive a uma transação já salva. Arrastar o cabeçalho
só navega. Criar assinatura ou regra acontece no salvamento final. Efeitos propagados exigem
conferência; alterações concorrentes pedem recarregamento. Sem pendências, a seção desaparece.

`/split` abre o assistente de divisão já conhecido: despesa, pagador, forma de divisão,
participantes e conferência. O rateio preserva centavos. Contas somente divisão também podem
vincular o Telegram e usar essas funções, sem relatórios financeiros ou conversa geral com IA.

| Comando | Função |
|---|---|
| `/start`, `/ajuda` | Vínculo e funções disponíveis para a conta |
| `/revisar` | Pendências e botão para revisão |
| `/split` | Nova divisão no miniapp; desktop explica o requisito self-hosted |
| `/divisoes` | Saldos e acesso às divisões |
| `/resumo` | Resumo financeiro do mês para contas completas |
| `/cancelar` | Cancela propostas e revoga autorizações em andamento; não desfaz alterações concluídas |
| `/limpar` | Confirma a exclusão do histórico local e cancela propostas |

Esses comandos funcionam com a IA desligada. Somente conversas privadas e mensagens de texto.

## Inteligência artificial

Em **Configurações → Inteligência artificial**, o administrador escolhe **Axon** ou **API
OpenAI-compatible**. Salve endpoint/chave, teste a conexão e depois ative. O provedor genérico
exige o nome do modelo e suporte a tool calling; está disponível também no desktop. Cada pessoa
ativa separadamente a conversa, após ver qual provedor receberá seus dados. A interface de
conversa fica exclusivamente no Telegram.

Padrões: 50 mensagens por pessoa/dia e 500 por instalação/dia, em America/Sao_Paulo; histórico
cifrado de sete dias, contexto das últimas vinte interações completas, seis rodadas de ferramentas
no provedor genérico e 120 segundos por solicitação. Limpar o histórico não restaura a cota do dia.
A retenção é verificada periodicamente enquanto o Mango está aberto.

Escritas são preparadas e conferidas no servidor. Exclusões, lotes e propagação sempre pedem
**Confirmar/Cancelar**, com validade de dez minutos. Chamadas individuais sucessivas também
formam um lote. Para evitar que texto bancário autorize escrita, a dispensa inicial de botão é
restrita à instrução inequívoca **“Marque a transação 123 como revisada”**, com os mesmos id e
argumentos. Outras alterações individuais passam pela conferência. O modelo não confirma.

`/limpar` apaga o histórico guardado no Mango; não apaga mensagens no Telegram, traces nem
registros do provedor. Não há repetição automática de execução após timeout ou reinício. Em
entrega incerta, confira os dados ou a proposta antes de formular outro pedido.

## Preparar o Axon

É necessário Axon com o protocolo de delegação 1 (ADR-055). Uma versão antiga não conclui o teste.
No Axon, o operador:

1. Registra um MCP global HTTP HTTPS apontando exatamente para `https://seu-mango/mcp`, com
   `auth.type: delegated`, sem credencial estática, `user_access: false` e allowlist explícita de tools.
2. Configura um Assistant privado com esse alias, flow com ferramentas e acesso somente ao
   serviço da instalação, por exemplo `svc:mango`. Use um único alias delegado por Assistant.
3. Define limites de execução no Assistant, incluindo até seis iterações de ferramentas. Os
   parâmetros de geração enviados pelo cliente não substituem a política do Assistant.
4. Desativa captura de conteúdo nos destinos de observabilidade dessa integração e evita logs
   HTTP de depuração. `x-axon-store: false` desliga a conversa persistida, não os traces.
5. Cria a chave do serviço com acesso a exatamente um Assistant compatível.

No Mango, informe a base incluindo `/private/v1` e a chave. O teste consulta `/models`; não há
campo de modelo no formulário Axon. Ausência, ambiguidade, protocolo incompatível ou endpoint
MCP diferente geram erro. Cada instalação precisa de seu próprio serviço, Assistant e registro MCP.

A chave autentica a instalação no Axon. A identidade da pessoa vem de uma credencial Mango opaca,
com hash no banco, vinculada a usuário, execução, bot e vínculo, válida por cinco minutos e revogada
no término/cancelamento. O Axon a recebe no header separado e a encaminha apenas ao MCP autorizado.
Ela nunca é enviada ao modelo. O Mango verifica novamente a identidade e o alcance a cada chamada.

Não há provisionamento automático, túnel nem serviço central. Mango e Axon devem alcançar os
respectivos endpoints HTTPS. Para uma API de IA em rede privada, o operador pode liberar seu
hostname em `IA_HOSTS_PRIVADOS` (lista separada por vírgulas); redirecionamentos não são seguidos.

## Atualização e homologação

A migration `d73b915eaf02` acrescenta tabelas sem alterar tokens, vínculos ou preferências existentes.
IA e miniapp começam desligados. Execute as migrations antes de iniciar a nova versão. Mantenha
um processo Mango por bot e a chave de cifragem usada pela instalação.

Antes de liberar: teste dois usuários simultâneos no mesmo Assistant; revisão com propagação,
confirmação expirada e cancelada; `/split`; fila vazia; reinício durante uma execução; Telegram
Android/iOS e HTTPS real. Os testes automatizados usam provedores simulados e não substituem essa
homologação com bot e instalação Axon de teste.
