"""Política compartilhada entre Axon/MCP e provedor genérico; modelo nunca confirma."""

import json
import re
import secrets
from datetime import UTC, datetime, timedelta

from mcp.server.mcpserver import Context, MCPServer
from mcp.server.mcpserver.exceptions import ToolError
from mcp_types import CallToolResult, TextContent
from pydantic import Field
from sqlalchemy import inspect, select

from app.db.atomic import atomica
from app.db.session import SessionLocal
from app.mcp.api import _tool_db
from app.models.integracao import OperacaoIntegracao
from app.security.current_user import _aware
from app.services.integracao_auth import resolver
from app.services.operacoes import bloquear_operacao, serializar, versao

LEITURAS = frozenset(
    {
        "listar_transacoes",
        "buscar_transacoes",
        "obter_transacao",
        "listar_categorias",
        "listar_contas",
        "obter_conta",
        "listar_cartoes",
        "listar_faturas",
        "obter_fatura",
        "listar_objetivos",
        "obter_objetivo",
        "listar_assinaturas",
        "listar_candidatos_assinatura",
        "listar_orcamentos",
        "listar_pessoas_divisao",
        "saldos_divisao",
        "listar_divisoes",
        "resumo_financeiro",
        "resumo_investimentos",
        "listar_investimentos",
        "listar_fontes_de_renda",
        "grafico",
    }
)
ESCRITAS = frozenset(
    {
        "atualizar_transacoes",
        "vincular_objetivo",
        "criar_assinatura",
        "atualizar_assinatura",
        "rejeitar_candidato_assinatura",
        "excluir_assinatura",
        "criar_divisao",
        "quitar_divisao",
        "reabrir_divisao",
        "excluir_divisao",
    }
)
DIVISAO = frozenset(
    {
        "listar_pessoas_divisao",
        "saldos_divisao",
        "listar_divisoes",
        "criar_divisao",
        "quitar_divisao",
        "reabrir_divisao",
        "excluir_divisao",
    }
)


class ContextoInterno(Context):
    autorizacao: str = Field(repr=False, exclude=True)

    @property
    def headers(self):
        return {"authorization": self.autorizacao}


def snapshot(db, usuario_id):
    from app.models.conta import Conta
    from app.models.investimento import Investimento
    from app.models.objetivo import Objetivo
    from app.repositories.divisao import DivisaoDespesaRepository
    from app.services.operacoes import estado

    resultado = estado(db, usuario_id)
    for model in (Conta, Investimento, Objetivo):
        resultado[model.__tablename__] = {
            str(o.id): {c.key: getattr(o, c.key) for c in inspect(model).columns}
            for o in db.scalars(
                select(model).where(model.usuario_id == usuario_id).with_for_update()
            )
        }
    from app.services.divisao import enriquecer

    resultado["divisao"] = {
        str(o.id): enriquecer(db, usuario_id, o).model_dump(mode="json")
        for o in DivisaoDespesaRepository(db, usuario_id).visiveis()
    }
    return resultado


def resposta(texto, dados=None):
    return CallToolResult(content=[TextContent(type="text", text=texto)], structuredContent=dados)


async def chamar_real(server, nome, args, ctx, db):
    marcador = _tool_db.set(db)
    try:
        return await MCPServer.call_tool(server, nome, args, ctx)
    finally:
        _tool_db.reset(marcador)


async def despachar(server, nome, args, ctx):
    with SessionLocal() as db:
        token = ctx.headers["authorization"].split(" ", 1)[1]
        user, cred = resolver(db, token)
        if nome not in LEITURAS | ESCRITAS or (user.tipo == "divisao" and nome not in DIVISAO):
            raise ToolError("ferramenta fora do alcance da integração")
        if nome in LEITURAS:
            return await chamar_real(server, nome, args, ctx, db)
        from app.models.integracao import TrabalhoTelegram

        trabalho = db.get(TrabalhoTelegram, cred.trabalho_id)
        mensagem = json.loads(trabalho.evento or "{}").get("message", {}).get("text", "")
        antes = snapshot(db, user.id)
        db.info["operacao_atomica"] = True
        try:
            with db.begin_nested() as sp:
                resultado = await chamar_real(server, nome, args, ctx, db)
                if resultado.is_error or (resultado.structured_content or {}).get("falhas"):
                    raise ToolError("não foi possível preparar a alteração")
                db.flush()
                depois = snapshot(db, user.id)
                sp.rollback()
        finally:
            db.info["operacao_atomica"] = False
        from app.models.transacao import Transacao

        a, b = antes[Transacao.__tablename__], depois[Transacao.__tablename__]
        alteradas = sum(serializar(a.get(k)) != serializar(b.get(k)) for k in a.keys() | b.keys())
        op = db.scalar(
            select(OperacaoIntegracao).where(
                OperacaoIntegracao.trabalho_id == cred.trabalho_id,
                OperacaoIntegracao.tipo == "ia",
                OperacaoIntegracao.status == "preparando",
            )
        )
        dados = (
            json.loads(op.payload)
            if op
            else {"versao": versao(antes), "chamadas": [], "confirmar": False}
        )
        if dados["versao"] != versao(antes):
            raise ToolError("os dados mudaram durante a solicitação; tente novamente")
        chamada = {"nome": nome, "args": args}
        if chamada not in dados["chamadas"]:
            dados["chamadas"].append(chamada)
        # Só uma instrução determinística, ligada ao id e aos argumentos, dispensa o botão.
        # Texto de banco/LLM nunca constitui autorização. Demais escritas pedem conferência.
        explicita = re.fullmatch(
            r"(?:marque|marcar) (?:a )?transa[çc][ãa]o #?(\d+) como revisada[.!]?",
            mensagem.strip(),
            re.IGNORECASE,
        )
        direta = bool(
            explicita
            and nome == "atualizar_transacoes"
            and args == {"ids": [int(explicita[1])], "revisada": True}
        )
        dados["confirmar"] |= not direta or alteradas > 1 or len(dados["chamadas"]) > 1
        afetadas = {k for k in a.keys() | b.keys() if serializar(a.get(k)) != serializar(b.get(k))}
        dados["transacoes"] = sorted(set(dados.get("transacoes", [])) | afetadas)
        dados["efeitos"] = len(dados["transacoes"])
        if op is None:
            op = OperacaoIntegracao(
                id=secrets.token_urlsafe(24),
                usuario_id=user.id,
                trabalho_id=cred.trabalho_id,
                tipo="ia",
                status="preparando",
                expira_em=datetime.now(UTC) + timedelta(minutes=10),
            )
            db.add(op)
        op.payload = serializar(dados)
        db.commit()
        return resposta(
            "Alteração preparada, ainda não aplicada. "
            "O Mango aplicará ao finalizar ou pedirá confirmação.",
            {"status": "preparada", "operacao_id": op.id},
        )


async def aplicar(server, db, user_id, op_id, token):
    with atomica(db):
        op = bloquear_operacao(db, user_id, op_id)
        if not op or op.tipo != "ia" or op.status not in {"pendente", "preparando", "concluida"}:
            raise ToolError("operação indisponível")
        if op.status == "concluida":
            return op.resultado
        if _aware(op.expira_em) < datetime.now(UTC):
            raise ToolError("confirmação expirada")
        dados = json.loads(op.payload)
        if versao(snapshot(db, user_id)) != dados["versao"]:
            raise ToolError("os dados mudaram; solicite uma nova proposta")
        resultados = []
        ctx = ContextoInterno(autorizacao=f"Bearer {token}", mcp_server=server)
        for chamada in dados["chamadas"]:
            result = await chamar_real(server, chamada["nome"], chamada["args"], ctx, db)
            if result.is_error or (result.structured_content or {}).get("falhas"):
                raise ToolError("alteração recusada; nenhuma alteração aplicada")
            resultados.extend(c.text for c in result.content if c.type == "text")
        op.resultado = "\n\n".join(resultados)
        op.status = "concluida"
    return op.resultado
