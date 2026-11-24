"""Schemas de `transacao` (Pluggy-owned): leitura + update estreito (flags/override §4.5)."""

from datetime import datetime
from typing import Annotated, Literal

from pydantic import BaseModel, Field, field_validator

from app.models.transacao import Transacao
from app.schemas.auto import read_model
from app.services.categoria_resolucao import Origem

_TransacaoColunas = read_model(Transacao)


class DivisaoDaTransacao(BaseModel):
    """Resumo da divisão vinculada a uma transação (só o pagador vê — a transação é dele)."""

    id: int
    valor_total_centavos: int
    # Parte dos outros participantes (o que eles devem a quem pagou). Nunca muda com o vínculo.
    outros_centavos: int
    # O que conta no orçamento/dashboard: valor da transação − parte dos outros (mínimo 0). Igual
    # à parte do usuário quando a transação tem o valor da divisão; senão a diferença fica com ele.
    minha_parte_centavos: int


class DivisaoLancamento(BaseModel):
    """Divisão que entra na lista de transações sem ser uma transação do usuário (RF08): paga
    por outra pessoa (minha parte) ou paga por mim sem transação (pendente / fora do banco)."""

    origem: Literal["divisao"] = "divisao"
    divisao_id: int
    data: datetime
    descricao: str | None
    categoria_id: str | None
    valor_total_centavos: int
    minha_parte_centavos: int
    pago_por_nome: str
    pago_por_mim: bool
    sem_transacao: bool
    pendente: bool


class TransacaoRead(_TransacaoColunas):  # type: ignore[misc, valid-type]
    """Colunas + a categoria já resolvida (§4.5).

    Os quatro campos-fonte (`categoria_pluggy_id`, `_override_`, `_regra_`, `assinatura_id`)
    continuam expostos para a UI mostrar o que veio de onde, mas quem quer "a categoria desta
    transação" lê `categoria_efetiva_id` — replicar a precedência no cliente daria divergência.
    Preenchidos pelo router; os defaults valem para quem construir o schema sem contexto.
    """

    categoria_efetiva_id: str | None = None
    categoria_origem: Origem = "desconhecida"
    # Quantas OUTRAS parcelas da mesma compra o PATCH recategorizou junto (§4.5). Só o PATCH
    # preenche; na listagem é sempre 0. Existe para a UI dizer o que de fato aconteceu — o aviso
    # "aplicada a todas as parcelas" era emitido só por `total_installments > 1`, e mentia quando
    # o agrupamento não achava irmã nenhuma.
    parcelas_atualizadas: int = 0
    origem: Literal["transacao"] = "transacao"
    divisao: DivisaoDaTransacao | None = None


class TransacaoUpdate(BaseModel):
    """Só os campos do usuário (§4 crud.md). `exclude_unset` no router → patch parcial."""

    eh_transferencia: bool | None = None
    revisada: bool | None = None
    # Categorias do Pluggy vão até 9 dígitos (ex.: 200300000) — 16 dá folga (igual ao model).
    categoria_override_id: str | None = Field(default=None, max_length=16)
    categoria_ajustada_usuario: bool | None = None
    # Vínculo com assinatura (§4.7): id (posse validada no router) ou None p/ desvincular.
    assinatura_id: int | None = None
    # "Não é assinatura": suprime detecção/sugestão para esta transação (§4.7).
    nao_e_assinatura: bool | None = None
    # Vínculo com um provento de investimento (§4.9): id do movimento (posse validada no router,
    # pelo investimento pai) ou None p/ desvincular.
    investimento_transacao_id: int | None = None
    # Texto do usuário (§4.5): descrição própria (substitui a do banco na listagem) e observação
    # livre. `None` limpa o campo.
    descricao_usuario: str | None = Field(default=None, max_length=255)
    observacoes: str | None = Field(default=None, max_length=2000)

    @field_validator("descricao_usuario", "observacoes")
    @classmethod
    def _vazio_vira_nulo(cls, v: str | None) -> str | None:
        """Campo apagado na UI chega como "" — guardar isso quebraria o fallback para o texto
        do banco (string vazia não é null)."""
        return v.strip() or None if v is not None else None


ItemListagem = Annotated[TransacaoRead | DivisaoLancamento, Field(discriminator="origem")]


class TransacaoListagem(BaseModel):
    """Página server-side p/ a tabela (§5.3): itens + total para a paginação. Mistura transações
    e lançamentos de divisão (`origem`) numa ordem só."""

    items: list[ItemListagem]
    total: int
