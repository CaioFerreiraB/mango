"""Repositório de divisão de despesas (§4.11).

Visibilidade multi-usuário (criador, pagador OU qualquer participante enxerga a despesa) — não
cabe no `UserScopedRepository` genérico (coluna única de posse), por isso é uma classe própria.
Só o criador pode editar/excluir (`obter_como_criador`); quitar/reabrir é mais permissivo (ver
`app/services/divisao.py`).
"""

from sqlalchemy import delete, or_, select
from sqlalchemy.orm import Session

from app.models.divisao import DivisaoDespesa, DivisaoParticipante

EscopoDivisao = str  # "todas" | "minhas" | "comigo" | "arquivadas" (validado no schema/router)


class DivisaoDespesaRepository:
    def __init__(self, db: Session, usuario_id: int) -> None:
        self.db = db
        self.usuario_id = usuario_id

    def _visivel(self):
        participante_de = select(DivisaoParticipante.divisao_id).where(
            DivisaoParticipante.usuario_id == self.usuario_id
        )
        return or_(
            DivisaoDespesa.criado_por_usuario_id == self.usuario_id,
            DivisaoDespesa.pago_por_usuario_id == self.usuario_id,
            DivisaoDespesa.id.in_(participante_de),
        )

    def visiveis(self) -> list[DivisaoDespesa]:
        """Toda despesa em que sou envolvido, sem filtro de arquivada/escopo (uso: agregações)."""
        return list(self.db.scalars(select(DivisaoDespesa).where(self._visivel())).all())

    def listar(self, escopo: EscopoDivisao = "todas") -> list[DivisaoDespesa]:
        query = select(DivisaoDespesa).where(self._visivel())
        query = query.where(DivisaoDespesa.arquivada.is_(escopo == "arquivadas"))
        if escopo == "minhas":
            query = query.where(DivisaoDespesa.criado_por_usuario_id == self.usuario_id)
        elif escopo == "comigo":
            query = query.where(DivisaoDespesa.criado_por_usuario_id != self.usuario_id)
        return list(self.db.scalars(query.order_by(DivisaoDespesa.id.desc())).all())

    def obter(self, despesa_id: int) -> DivisaoDespesa | None:
        """Qualquer envolvido (criador, pagador ou participante) pode ver."""
        return self.db.scalars(
            select(DivisaoDespesa).where(DivisaoDespesa.id == despesa_id, self._visivel())
        ).first()

    def obter_como_criador(self, despesa_id: int) -> DivisaoDespesa | None:
        """Só quem criou — usado antes de editar/excluir."""
        return self.db.scalars(
            select(DivisaoDespesa).where(
                DivisaoDespesa.id == despesa_id,
                DivisaoDespesa.criado_por_usuario_id == self.usuario_id,
            )
        ).first()

    def participantes(self, despesa_id: int) -> list[DivisaoParticipante]:
        return list(
            self.db.scalars(
                select(DivisaoParticipante).where(DivisaoParticipante.divisao_id == despesa_id)
            ).all()
        )

    def criar(self, **campos) -> DivisaoDespesa:
        despesa = DivisaoDespesa(criado_por_usuario_id=self.usuario_id, **campos)
        self.db.add(despesa)
        self.db.flush()  # id disponível sem commitar (linhas de participantes vêm no mesmo commit)
        return despesa

    def atualizar(self, despesa: DivisaoDespesa, **campos) -> DivisaoDespesa:
        for chave, valor in campos.items():
            setattr(despesa, chave, valor)
        self.db.flush()
        return despesa

    def definir_participantes(self, despesa_id: int, linhas: list[tuple[int, int]]) -> None:
        """Substitui todas as linhas de participantes da despesa pelas informadas."""
        self.db.execute(
            delete(DivisaoParticipante).where(DivisaoParticipante.divisao_id == despesa_id)
        )
        for usuario_id, valor_centavos in linhas:
            self.db.add(
                DivisaoParticipante(
                    divisao_id=despesa_id, usuario_id=usuario_id, valor_centavos=valor_centavos
                )
            )
        self.db.flush()

    def remover(self, despesa: DivisaoDespesa) -> None:
        self.db.delete(despesa)
        self.db.commit()
