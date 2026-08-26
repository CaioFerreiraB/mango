"""Repositório de transação (Pluggy-owned): read/narrow + upsert do sync (Fase 1)."""

from datetime import datetime

from sqlalchemy import func, or_, select

from app.models.transacao import Transacao
from app.repositories.base import UserScopedRepository

# Campos do usuário — o re-sync NUNCA os sobrescreve (§4.5/§4.4).
CAMPOS_USUARIO = (
    "eh_transferencia",
    "revisada",
    "categoria_override_id",
    "categoria_ajustada_usuario",
    "descricao_usuario",
    "observacoes",
    "contraparte_id",
    "transferencia_origem",
    "assinatura_id",
    "nao_e_assinatura",
    "investimento_transacao_id",
)

_CAT_EFETIVA = func.coalesce(Transacao.categoria_override_id, Transacao.categoria_pluggy_id)
# Valor efetivo em reais: valor na moeda da conta (internacional), senão o `amount` cru.
_VALOR_EFETIVO = func.coalesce(
    Transacao.amount_in_account_currency_centavos, Transacao.amount_centavos
)

# Ordenação (allowlist — nunca interpolar nome de coluna, S4). Por valor usa o efetivo em reais.
ORDENACAO = {"date": Transacao.date, "amount_centavos": _VALOR_EFETIVO}


def _escape_like(termo: str) -> str:
    return termo.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


class TransacaoRepository(UserScopedRepository[Transacao]):
    model = Transacao

    def get_by_pluggy_id(self, pluggy_transaction_id: str) -> Transacao | None:
        return self.db.scalars(
            self._scoped().where(Transacao.pluggy_transaction_id == pluggy_transaction_id)
        ).first()

    def listar_filtrado(
        self,
        *,
        inicio: datetime | None = None,
        fim: datetime | None = None,
        conta_id: int | None = None,
        categoria_id: str | None = None,
        fatura_id: int | None = None,
        tipo: str | None = None,
        revisada: bool | None = None,
        eh_transferencia: bool | None = None,
        assinatura_id: int | None = None,
        tem_assinatura: bool | None = None,
        busca: str | None = None,
        order: str = "date",
        descendente: bool = True,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[Transacao], int]:
        """Listagem filtrada + paginada, sempre dentro do escopo do usuário (S3/S4)."""
        filtros = [self._scope() == self.usuario_id]
        if inicio is not None:
            filtros.append(Transacao.date >= inicio)
        if fim is not None:
            filtros.append(Transacao.date < fim)
        if conta_id is not None:
            filtros.append(Transacao.conta_id == conta_id)
        if categoria_id is not None:
            filtros.append(_CAT_EFETIVA == categoria_id)
        if fatura_id is not None:
            filtros.append(Transacao.bill_id == fatura_id)
        if tipo is not None:
            filtros.append(Transacao.type == tipo)
        if revisada is not None:
            filtros.append(Transacao.revisada.is_(revisada))
        if eh_transferencia is not None:
            filtros.append(Transacao.eh_transferencia.is_(eh_transferencia))
        # Assinatura específica tem precedência sobre o "qualquer/nenhuma" (tem_assinatura).
        if assinatura_id is not None:
            filtros.append(Transacao.assinatura_id == assinatura_id)
        elif tem_assinatura is not None:
            filtros.append(
                Transacao.assinatura_id.is_not(None)
                if tem_assinatura
                else Transacao.assinatura_id.is_(None)
            )
        if busca:
            termo = f"%{_escape_like(busca)}%"
            filtros.append(
                or_(
                    Transacao.description.ilike(termo, escape="\\"),
                    Transacao.merchant_nome.ilike(termo, escape="\\"),
                    Transacao.descricao_usuario.ilike(termo, escape="\\"),
                    Transacao.observacoes.ilike(termo, escape="\\"),
                )
            )

        total = self.db.scalar(select(func.count()).select_from(Transacao).where(*filtros))
        coluna = ORDENACAO.get(order, Transacao.date)
        ordem = coluna.desc() if descendente else coluna.asc()
        itens = self.db.scalars(
            select(Transacao)
            .where(*filtros)
            .order_by(ordem, Transacao.id.desc())
            .limit(limit)
            .offset(offset)
        ).all()
        return list(itens), total or 0

    def upsert_by_pluggy_id(self, pluggy_transaction_id: str, **fields) -> Transacao:
        obj = self.get_by_pluggy_id(pluggy_transaction_id)
        if obj is None:
            return self.create(pluggy_transaction_id=pluggy_transaction_id, **fields)
        for campo in CAMPOS_USUARIO:
            fields.pop(campo, None)
        return self.update(obj, **fields)
