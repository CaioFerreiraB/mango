"""First-run setup (§4.1, §4.3, #15): cria o usuário dono + conexão Pluggy + sessão.

O wizard de instalação é conceito do **self-hosted** (subir a instância e abrir a URL). No `local`
o usuário é implícito ([app.security.current_user]) e o setup não se aplica.

Fluxo em 2 passos para **garantir que o 2FA funciona antes de concluir**:
1. `iniciar_setup` valida os dados — inclusive a conexão do Pluggy **ao vivo** (a credencial
   autentica e o `itemId` existe nela) —, gera o segredo TOTP (se `ativar_totp`) e devolve um
   **ticket cifrado** (Fernet, com validade); nada é gravado no banco ainda. O ticket carrega os
   dados do setup de ida e volta pelo cliente, opaco para ele (cifrado com a chave do servidor).
2. `confirmar_setup` exige o código do autenticador quando há segredo no ticket; só então grava
   usuário + credencial + item + sessão, num **único commit** (atômico — não usa os repositórios,
   que commitam por passo). 2FA é opcional (§5.2, #15): se `ativar_totp=False` no passo 1, o
   ticket carrega `totp_secret=None` e o passo 2 conclui sem código, com `totp_login_habilitado`
   já nascendo `False` — a conta fica sem a "prova de posse" que a recuperação de senha exige.
"""

import json
from datetime import date

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.config import settings
from app.exceptions import ConflictError, ValidationError
from app.models.pluggy import CredencialPluggy, Instituicao, ItemPluggy
from app.models.usuario import Sessao, Usuario
from app.pluggy.client import PluggyClient, PluggyError
from app.schemas.setup import PluggyCredenciais, SetupRequest
from app.security import encryption, passwords, totp
from app.security.sessions import nova_sessao

_TICKET_TTL = 900  # 15 min entre exibir o QR e confirmar o código


def precisa_setup(db: Session) -> bool:
    """True quando a instância self-hosted ainda não tem dono. Local nunca precisa de setup."""
    if settings.app_mode != "self_hosted":
        return False
    return db.scalar(select(func.count()).select_from(Usuario)) == 0


def _validar_conexao_pluggy(pluggy: PluggyCredenciais) -> None:
    """Confere a conexão ao vivo, antes de gravar qualquer coisa: a credencial autentica e o
    `itemId` existe nela. Sem isso o erro só apareceria no primeiro sync, muito depois."""
    with PluggyClient(pluggy.client_id, pluggy.client_secret) as client:
        try:
            client.autenticar()
        except PluggyError:
            raise ValidationError(
                "credenciais do Pluggy inválidas — confira o clientId e o clientSecret"
            ) from None
        try:
            client.item(pluggy.item_id)
        except PluggyError:
            raise ValidationError("itemId não encontrado para essas credenciais") from None


def iniciar_setup(db: Session, payload: SetupRequest) -> tuple[str | None, str]:
    """Passo 1: valida, gera o TOTP (se pedido) e sela o ticket. Devolve (totp_secret|None,
    setup_ticket)."""
    if settings.app_mode != "self_hosted":
        raise ConflictError("setup disponível apenas no modo self-hosted")
    if not precisa_setup(db):
        raise ConflictError("instância já configurada")

    _validar_conexao_pluggy(payload.pluggy)  # nada é persistido neste passo, nem em caso de sucesso

    totp_secret = totp.gerar_secret() if payload.ativar_totp else None
    ticket = encryption.encrypt(
        json.dumps(
            {
                "nome": payload.nome.strip(),
                "email": payload.email,
                "senha": payload.senha,
                "data_nascimento": (
                    payload.data_nascimento.isoformat() if payload.data_nascimento else None
                ),
                "salario_mensal_centavos": payload.salario_mensal_centavos,
                "formacao": payload.formacao,
                "ocupacao": payload.ocupacao,
                "pluggy": payload.pluggy.model_dump(),
                "totp_secret": totp_secret,
            }
        )
    )
    return totp_secret, ticket


def confirmar_setup(
    db: Session, ticket: str, codigo_totp: str | None, request=None
) -> tuple[Usuario, Sessao]:
    """Passo 2: valida o código (quando há segredo no ticket) e só então persiste tudo. Levanta
    ValidationError se não bater."""
    if settings.app_mode != "self_hosted":
        raise ConflictError("setup disponível apenas no modo self-hosted")
    if not precisa_setup(db):
        raise ConflictError("instância já configurada")

    bruto = encryption.unseal(ticket, ttl=_TICKET_TTL)
    if bruto is None:
        raise ValidationError("ticket de setup inválido ou expirado; recomece o cadastro")
    dados = json.loads(bruto)

    totp_secret = dados["totp_secret"]
    if totp_secret is not None:
        if not totp.verificar(totp_secret, codigo_totp or ""):
            raise ValidationError("código incorreto")

    usuario = Usuario(
        nome=dados["nome"],
        email=dados["email"],
        senha_hash=passwords.hash_password(dados["senha"]),
        totp_secret_cifrado=totp_secret,  # EncryptedStr cifra em repouso (§5.5); None se pulou
        totp_login_habilitado=totp_secret is not None,
        data_nascimento=(
            date.fromisoformat(dados["data_nascimento"]) if dados["data_nascimento"] else None
        ),
        salario_mensal_centavos=dados["salario_mensal_centavos"],
        formacao=dados["formacao"],
        ocupacao=dados["ocupacao"],
        tipo="completo",
        ativo=True,
        is_admin=True,  # dono da instância (§4.11/§5.2) — único por instância, gerencia usuários
    )
    db.add(usuario)
    db.flush()  # atribui usuario.id sem commitar

    credencial = CredencialPluggy(
        usuario_id=usuario.id,
        client_id_cifrado=dados["pluggy"]["client_id"],
        client_secret_cifrado=dados["pluggy"]["client_secret"],
    )
    db.add(credencial)
    db.flush()

    # Vínculo manual da instituição (opcional). O usuário acabou de nascer, então não há linha
    # anterior a reaproveitar — cria direto, no mesmo commit (os repositórios commitam por passo).
    instituicao_manual_id = None
    escolhida = dados["pluggy"].get("instituicao")
    if escolhida:
        instituicao = Instituicao(
            usuario_id=usuario.id,
            nome=escolhida["nome"],
            pluggy_connector_id=escolhida["pluggy_connector_id"],
            logo_url=escolhida["logo_url"],
        )
        db.add(instituicao)
        db.flush()
        instituicao_manual_id = instituicao.id

    db.add(
        ItemPluggy(
            usuario_id=usuario.id,
            credencial_id=credencial.id,
            pluggy_item_id=dados["pluggy"]["item_id"],
            instituicao_manual_id=instituicao_manual_id,
        )
    )

    sessao = nova_sessao(usuario.id, request)
    db.add(sessao)

    db.commit()
    db.refresh(usuario)
    db.refresh(sessao)
    return usuario, sessao
