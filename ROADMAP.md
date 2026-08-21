# Roadmap

O que vem pela frente no mango, em ordem de prioridade. **Sem datas** — este é um projeto pessoal e
o ritmo varia; a ordem é um compromisso maior que o calendário. O que já saiu está no
[CHANGELOG.md](CHANGELOG.md); o destino do produto, em [PRODUCT.md](PRODUCT.md).

---

## Problemas conhecidos

Coisas em aberto que afetam quem já roda o mango. Estão no topo de propósito.

### Sem rate-limiting na autenticação — **prioridade máxima**

Os endpoints de autenticação não têm throttle, backoff nem lockout. O impacto real está em
`POST /api/auth/recuperar-senha`, que prova posse **apenas** com o código TOTP de 6 dígitos: com uma
janela de validação de ±1 intervalo, o espaço efetivo é de algumas centenas de milhares de códigos, e
sem limite de tentativas ele é varrível por quem souber o e-mail da conta. `POST /api/auth/login`
tem o mesmo problema, em grau menor.

**Enquanto não estiver corrigido:** não exponha a instância diretamente à internet aberta. Rode em
rede local, atrás de VPN (Tailscale/WireGuard) ou atrás de um reverse proxy que já limite taxa nesses
caminhos.

**Correção planejada:** limite por IP **e** por conta-alvo nos dois endpoints, com backoff
exponencial e lockout temporário, mais invalidação de códigos TOTP já usados dentro da janela (evita
replay).

### Menores, em avaliação

- `GET /api/usuarios/buscar` com termo vazio lista membros da instância e casa por e-mail — é o que
  alimenta a divisão de contas, mas expõe mais do que o necessário a uma conta "somente divisão".
  Avaliar termo mínimo e nunca casar/retornar e-mail.
- `/docs`, `/redoc` e `/openapi.json` são públicos também em `self_hosted`. Não vazam dados, mas
  entregam o mapa da API. Avaliar desabilitar fora de desenvolvimento.

---

## Próximo

### Notificações no Telegram

A configuração já está modelada e persistida; falta a entrega. Bot opcional, configurado no primeiro
uso, com o passo a passo para capturar o `chat_id` depois do `/start` (o bot não inicia conversa).

- Aviso de novas transações reconhecidas, **agregado por sync** — uma mensagem, não uma por transação.
- Lembrete de transações não revisadas, 2×/dia em horários escolhidos, enquanto houver pendência.
- Resumo diário e resumo semanal, cada um ativável em separado.

### Endurecimento para exposição pública

Além do rate-limiting acima: revisão dos cabeçalhos de segurança e das políticas de sessão, e uma
decisão sobre a documentação da API em produção.

---

## Depois

### Modo local (desktop)

O segundo modo de deploy previsto desde o início: monousuário, sem login, dados sempre no disco da
máquina, empacotado com **pywebview**. A base de código já separa os dois modos por `APP_MODE`, mas o
empacotamento e a distribuição do executável ainda não existem.

### PWA

Instalação na tela inicial e uso confortável no celular, sobre a mesma SPA.

### Entrada de dados fora do Open Finance

Deliberadamente fora da v1, que importa **exclusivamente** via Pluggy:

- lançamento manual de transações;
- importação de OFX.

---

## Fora de escopo

Para deixar claro o que o mango **não** pretende ser:

- Multi-moeda — o alvo é pessoa física no Brasil, tudo em BRL e no fuso `America/Sao_Paulo`.
- Contabilidade empresarial, notas fiscais, folha.
- Gamificação, metas motivacionais, "score financeiro".
- SaaS hospedado por nós. O mango é self-hosted: o banco é seu.
