"""Schemas de despesa fixa (docs/dev/despesas-fixas.md)."""

from datetime import date
from typing import Literal

from pydantic import BaseModel, Field, model_validator

from app.models.despesa_fixa import DespesaFixa
from app.schemas.auto import read_model

Frequencia = Literal["semanal", "quinzenal", "mensal", "trimestral", "semestral", "anual"]
SituacaoDespesa = Literal[
    "atrasada", "vence_hoje", "em_aberto", "paga", "pulada", "em_dia", "inativa"
]
SituacaoOcorrencia = Literal["atrasada", "vence_hoje", "aberta", "paga", "pulada"]

_Colunas = read_model(DespesaFixa, overrides={"frequencia": Frequencia})


class DespesaFixaRead(_Colunas):  # type: ignore[misc, valid-type]
    """Colunas + indicadores calculados no momento da leitura (RF11)."""

    proximo_vencimento: date | None = None
    qtd_atrasos: int = 0
    situacao: SituacaoDespesa = "em_dia"


def _fim_depois_do_inicio(inicio: date | None, fim: date | None) -> None:
    if inicio is not None and fim is not None and fim < inicio:
        raise ValueError("a data de término deve ser igual ou posterior à de início")


class DespesaFixaCreate(BaseModel):
    descricao: str = Field(min_length=1, max_length=255)
    valor_centavos: int = Field(gt=0)
    frequencia: Frequencia
    dia_vencimento: int = Field(ge=1, le=31)
    inicio: date
    fim: date | None = None

    @model_validator(mode="after")
    def _periodo(self):
        _fim_depois_do_inicio(self.inicio, self.fim)
        return self


class DespesaFixaUpdate(BaseModel):
    """PATCH parcial (`exclude_unset`). `fim=None` torna a despesa permanente; os demais campos
    não aceitam nulo (são obrigatórios no modelo)."""

    descricao: str | None = Field(default=None, min_length=1, max_length=255)
    valor_centavos: int | None = Field(default=None, gt=0)
    frequencia: Frequencia | None = None
    dia_vencimento: int | None = Field(default=None, ge=1, le=31)
    inicio: date | None = None
    fim: date | None = None
    ativa: bool | None = None

    @model_validator(mode="after")
    def _sem_nulos(self):
        for campo in self.model_fields_set - {"fim"}:
            if getattr(self, campo) is None:
                raise ValueError(f"{campo} não pode ser nulo")
        _fim_depois_do_inicio(self.inicio, self.fim)
        return self


class OcorrenciaRead(BaseModel):
    id: int
    despesa_fixa_id: int
    vencimento: date
    valor_centavos: int
    status: Literal["aberta", "paga", "pulada"]
    situacao: SituacaoOcorrencia
    pago_em: date | None
    qtd_transacoes: int


class OcorrenciaUpdate(BaseModel):
    status: Literal["aberta", "paga", "pulada"]
    pago_em: date | None = None  # só com `paga`; omitido → hoje


class Contagem(BaseModel):
    qtd: int
    centavos: int


class ResumoItem(BaseModel):
    ocorrencia_id: int
    despesa_id: int
    descricao: str
    vencimento: date
    valor_centavos: int
    situacao: SituacaoOcorrencia


class DespesaFixaResumo(BaseModel):
    """Mês corrente, só despesas ativas: pagas/abertas do mês, atrasadas de qualquer mês."""

    mes: str
    tem_despesas: bool
    pagas: Contagem
    abertas: Contagem
    atrasadas: Contagem
    puladas: int
    proximos: list[ResumoItem]
