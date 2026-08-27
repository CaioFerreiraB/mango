"""ETL de fundamentos de FII a partir dos dados abertos da CVM (ponte ISIN → CNPJ → fundamentos).

Fontes (público, sem token): Informe Mensal (`geral`/`complemento`/`ativo_passivo`) + Informe
Trimestral (`imovel`). CSV `;`, latin1, chaveado por (CNPJ, Data_Referencia, Versao) → maior
`Versao` por (CNPJ, mês). Sem pandas — só stdlib (`zipfile`/`csv`/`io`). Preço e proventos não vêm
daqui (seguem de brapi/Pluggy). Ver `docs/dev/descoberta-fundamentos-fii.md`.

Segurança: base URL fixa por config (nunca de input de usuário, SSRF); `CvmError` redigido (só
rota/status). O ZIP baixado é sempre apagado após o parse (no `finally`). Acionado pelo scheduler
self_hosted e por uma thread no boot do local (throttle por idade dos dados).

`ponytail:` nomes de coluna e rótulos de alocação são um subconjunto curado com candidatos
alternativos (conferir nos dicionários META da CVM contra dado real); coluna ausente degrada p/
nulo/omitida, nunca quebra o parse.
"""

from __future__ import annotations

import csv
import io
import logging
import re
import tempfile
import zipfile
from dataclasses import dataclass, field
from datetime import UTC, date, datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path

import httpx
from sqlalchemy import distinct, select
from sqlalchemy.orm import Session

from app.config import settings
from app.models.fii_fundamento import FiiFundamento, FiiFundamentoAlocacao
from app.models.investimento import Investimento
from app.services.periodo import SP

logger = logging.getLogger("app.cvm")

_transport: httpx.BaseTransport | None = None  # p/ testes (MockTransport)
_TIMEOUT_S = 120.0
_CNPJ_COLS = ("CNPJ_Fundo_Classe", "CNPJ_Fundo")

# Alocação: rótulo de exibição → colunas do `ativo_passivo` (somadas). Colunas de **subtotal** de
# categoria (não somar com as sub-linhas, que dobrariam o valor). Colunas confirmadas no dado real.
_ALOCACAO: dict[str, tuple[str, ...]] = {
    "Imóveis": ("Direitos_Bens_Imoveis",),  # subtotal (inclui terrenos/obras/venda)
    "CRI/CRA": ("CRI", "CRI_CRA"),
    "Cotas de FII": ("FII", "Outras_Cotas_FI"),
    "SPE / ações de FII": ("Acoes_Sociedades_Atividades_FII", "Cotas_Sociedades_Atividades_FII"),
    "Ações": ("Acoes", "Fundo_Acoes"),
    "Debêntures": ("Debentures", "Cedulas_Debentures"),
    "LCI/LCA": ("LCI", "LCI_LCA"),
    "Títulos públicos": ("Titulos_Publicos",),
    "Caixa e liquidez": ("Disponibilidades", "Total_Necessidades_Liquidez"),
}


class CvmError(RuntimeError):
    """Falha ao obter/ler dado da CVM — mensagem já redigida (sem corpo)."""

    def __init__(self, msg: str, status: int | None = None):
        super().__init__(msg)
        self.status = status


@dataclass
class AlocacaoBruta:
    classe: str
    valor_centavos: int
    pct: Decimal


@dataclass
class FundamentoBruto:
    isin: str
    cnpj: str
    nome: str | None = None
    administrador_nome: str | None = None
    administrador_cnpj: str | None = None
    data_funcionamento: date | None = None
    segmento: str | None = None
    mandato: str | None = None
    tipo_gestao: str | None = None
    tipo: str | None = None
    patrimonio_liquido_centavos: int | None = None
    num_cotistas: int | None = None
    valor_patrimonial_cota_centavos: int | None = None
    dividend_yield_12m_pct: Decimal | None = None
    vacancia_pct: Decimal | None = None
    inadimplencia_pct: Decimal | None = None
    data_referencia: date | None = None
    data_referencia_trimestral: date | None = None
    alocacao: list[AlocacaoBruta] = field(default_factory=list)


# --- parsing (puro/testável: recebe qualquer coisa que ZipFile abra — Path ou BytesIO) ---------


def _col(row: dict, *names: str) -> str | None:
    for n in names:
        v = row.get(n)
        if v is not None and v.strip() != "":
            return v.strip()
    return None


def _num(s: str | None) -> Decimal | None:
    if s is None:
        return None
    t = s.strip().replace(" ", "")
    if not t or t.upper() in ("NA", "N/A", "NULL", "-", "NAO DISPONIVEL"):
        return None
    if "," in t and "." in t:
        t = t.replace(".", "").replace(",", ".")  # pt-BR 1.234.567,89
    elif "," in t:
        t = t.replace(",", ".")
    try:
        return Decimal(t)
    except InvalidOperation:
        return None


def _centavos(s: str | None) -> int | None:
    v = _num(s)
    return round(v * 100) if v is not None else None


def _inteiro(s: str | None) -> int | None:
    v = _num(s)
    return int(v) if v is not None else None


def _data(s: str | None) -> date | None:
    if not s:
        return None
    t = s.strip()
    for fmt, corte in (("%Y-%m-%d", 10), ("%d/%m/%Y", 10), ("%Y-%m", 7)):
        try:
            return datetime.strptime(t[:corte], fmt).date()
        except ValueError:
            continue
    return None


def _rows(zf: zipfile.ZipFile, prefixo: str) -> list[dict]:
    """Linhas (dict, chaves com trim) do 1º CSV do zip cujo nome contém `prefixo`."""
    nome = next(
        (n for n in zf.namelist() if prefixo in n.lower() and n.lower().endswith(".csv")), None
    )
    return _ler(zf, nome)


def _rows_re(zf: zipfile.ZipFile, padrao: str) -> list[dict]:
    """Como `_rows`, mas casando o nome por regex — usado no trimestral, onde `imovel` (a que tem
    vacância/inadimplência) coexiste com `alienacao_imovel`, `imovel_desempenho`, etc."""
    nome = next((n for n in zf.namelist() if re.search(padrao, n.lower())), None)
    return _ler(zf, nome)


def _ler(zf: zipfile.ZipFile, nome: str | None) -> list[dict]:
    if nome is None:
        return []
    with zf.open(nome) as raw:
        texto = io.TextIOWrapper(raw, encoding="latin-1", newline="")
        return [
            {(k or "").strip(): v for k, v in r.items()}
            for r in csv.DictReader(texto, delimiter=";")
        ]


def _chave(row: dict) -> tuple[date, int]:
    return (_data(_col(row, "Data_Referencia")) or date.min, _inteiro(_col(row, "Versao")) or 0)


def _latest_por_cnpj(rows: list[dict], cnpjs: set[str]) -> dict[str, dict]:
    """Linha mais recente (maior Data_Referencia, desempate maior Versao) por CNPJ alvo."""
    melhor: dict[str, tuple[tuple[date, int], dict]] = {}
    for r in rows:
        cnpj = _col(r, *_CNPJ_COLS)
        if cnpj is None or cnpj not in cnpjs:
            continue
        k = _chave(r)
        if cnpj not in melhor or k > melhor[cnpj][0]:
            melhor[cnpj] = (k, r)
    return {c: r for c, (_, r) in melhor.items()}


def _dy_12m_por_cnpj(complemento: list[dict], cnpjs: set[str]) -> dict[str, Decimal | None]:
    """DY 12M = soma do `Percentual_Dividend_Yield_Mes` nos até 12 meses mais recentes (maior
    Versao por mês)."""
    por: dict[str, dict[date, tuple[int, Decimal | None]]] = {}
    for r in complemento:
        cnpj = _col(r, *_CNPJ_COLS)
        if cnpj is None or cnpj not in cnpjs:
            continue
        dref = _data(_col(r, "Data_Referencia"))
        if dref is None:
            continue
        versao = _inteiro(_col(r, "Versao")) or 0
        dy = _num(_col(r, "Percentual_Dividend_Yield_Mes"))
        if dy is not None and abs(dy) > 1:  # fração > 100%/mês = artefato (evento) → ignora o mês
            dy = None
        meses = por.setdefault(cnpj, {})
        if dref not in meses or versao >= meses[dref][0]:
            meses[dref] = (versao, dy)
    out: dict[str, Decimal | None] = {}
    for cnpj, meses in por.items():
        ultimos = sorted(meses)[-12:]
        vals = [meses[m][1] for m in ultimos if meses[m][1] is not None]
        # `Percentual_Dividend_Yield_Mes` vem como fração (0.01 = 1%); ×100 → percentual.
        out[cnpj] = sum(vals) * 100 if vals else None
    return out


def _alocacao(row: dict) -> list[AlocacaoBruta]:
    valores: dict[str, Decimal] = {}
    for label, cols in _ALOCACAO.items():
        soma = sum((_num(row.get(c)) or Decimal(0)) for c in cols)
        if soma > 0:
            valores[label] = soma
    total = sum(valores.values())
    if total <= 0:
        return []
    # pct sobre a soma dos buckets → o donut fecha em ~100% (evita subtotal duplicado).
    return [
        AlocacaoBruta(label, round(v * 100), round(v / total * 100, 4))
        for label, v in valores.items()
    ]


def _derivar_tipo(mandato: str | None, segmento: str | None) -> str | None:
    """tijolo | papel | hibrido | fof — heurística sobre mandato/segmento (o `Mandato` costuma vir
    vazio no dado real, então o segmento manda). `ponytail:` sem o breakdown fino, FoF não é
    separável de papel com precisão → papel como aproximação."""
    m = (mandato or "").lower()
    s = (segmento or "").lower()
    if "brido" in m or "brido" in s or "multi" in s:  # híbrido / multicategoria
        return "hibrido"
    if "tulos" in m or "valores mobili" in m or "receb" in s or "papel" in s:
        return "papel"
    tijolo = ("imóve", "imove", "laje", "shopping", "log", "residencial", "hosp", "hotel", "varejo")
    if any(k in s for k in tijolo) or "renda" in m or "desenvolvimento" in m:
        return "tijolo"
    return None


def _media_pct(pares: list[tuple[Decimal | None, Decimal]]) -> Decimal | None:
    """Média ponderada dos percentuais (vacância/inadimplência vêm como fração → ×100)."""
    validos = [(v, p) for v, p in pares if v is not None and p > 0]
    if not validos:
        return None
    peso = sum(p for _, p in validos)
    return round(sum(v * p for v, p in validos) / peso * 100, 4) if peso > 0 else None


def _parse_mensal(zip_srcs, isins: set[str]) -> dict[str, FundamentoBruto]:  # noqa: ANN001
    """`zip_srcs`: uma fonte ou uma lista delas (ZipFile aceita Path ou BytesIO). Vários anos são
    concatenados — o dedup por (CNPJ, mês, Versao) dá o trailing-12M do DY sem dobrar linhas."""
    alvo = {i.strip().upper() for i in isins if i}
    if not alvo:
        return {}
    fontes = zip_srcs if isinstance(zip_srcs, list) else [zip_srcs]
    geral: list[dict] = []
    complemento: list[dict] = []
    ativo_passivo: list[dict] = []
    for src in fontes:
        with zipfile.ZipFile(src) as zf:
            geral += _rows(zf, "geral")
            complemento += _rows(zf, "complemento")
            ativo_passivo += _rows(zf, "ativo_passivo")

    # Ponte ISIN → CNPJ. Um ISIN pode aparecer para >1 CNPJ na CVM (colisão/reuso — ex.: um fundo
    # exclusivo homônimo com o mesmo ISIN de um listado). Coletamos os candidatos e desempatamos
    # pelo nº de cotistas: o fundo do ticker tem muitos cotistas; o exclusivo, poucos.
    cand: dict[str, dict[str, tuple[tuple[date, int], dict]]] = {}
    for r in geral:
        isin = (_col(r, "Codigo_ISIN", "Codigo_Isin") or "").upper()
        cnpj = _col(r, *_CNPJ_COLS)
        if isin not in alvo or cnpj is None:
            continue
        k = _chave(r)
        por_cnpj = cand.setdefault(isin, {})
        if cnpj not in por_cnpj or k > por_cnpj[cnpj][0]:
            por_cnpj[cnpj] = (k, r)
    if not cand:
        return {}

    comp = _latest_por_cnpj(complemento, {c for d in cand.values() for c in d})

    def _cotistas(cnpj: str) -> int:
        return _inteiro(_col(comp.get(cnpj) or {}, "Total_Numero_Cotistas")) or 0

    por_isin: dict[str, tuple[tuple[date, int], dict, str]] = {}
    for isin, por_cnpj in cand.items():
        cnpj = max(por_cnpj, key=_cotistas)  # desempate: o fundo listado (mais cotistas)
        k, r = por_cnpj[cnpj]
        por_isin[isin] = (k, r, cnpj)

    cnpjs = {cnpj for _, _, cnpj in por_isin.values()}
    dy = _dy_12m_por_cnpj(complemento, cnpjs)
    aloc = _latest_por_cnpj(ativo_passivo, cnpjs)

    out: dict[str, FundamentoBruto] = {}
    for isin, (_, grow, cnpj) in por_isin.items():
        crow = comp.get(cnpj) or {}
        fb = FundamentoBruto(
            isin=isin,
            cnpj=cnpj,
            nome=_col(grow, "Nome_Fundo_Classe", "Nome_Fundo"),
            administrador_nome=_col(grow, "Nome_Administrador"),
            administrador_cnpj=_col(grow, "CNPJ_Administrador"),
            data_funcionamento=_data(_col(grow, "Data_Funcionamento")),
            segmento=_col(grow, "Segmento_Atuacao"),
            mandato=_col(grow, "Mandato"),
            tipo_gestao=_col(grow, "Tipo_Gestao"),
            patrimonio_liquido_centavos=_centavos(_col(crow, "Patrimonio_Liquido")),
            num_cotistas=_inteiro(_col(crow, "Total_Numero_Cotistas", "Numero_Total_Cotistas")),
            valor_patrimonial_cota_centavos=_centavos(
                _col(crow, "Valor_Patrimonial_Cotas", "Valor_Patrimonial_Cota")
            ),
            dividend_yield_12m_pct=dy.get(cnpj),
            data_referencia=_data(_col(crow, "Data_Referencia")) or _chave(grow)[0],
            alocacao=_alocacao(aloc[cnpj]) if cnpj in aloc else [],
        )
        fb.tipo = _derivar_tipo(fb.mandato, fb.segmento)
        out[isin] = fb
    return out


def _parse_trimestral(
    zip_src,
    cnpjs: set[str],  # noqa: ANN001
) -> dict[str, tuple[Decimal | None, Decimal | None, date | None]]:
    with zipfile.ZipFile(zip_src) as zf:
        imovel = _rows_re(zf, r"fii_imovel_\d{4}\.csv$")  # exato: não pega alienacao/desempenho
    if not imovel:
        return {}
    # Trimestre mais recente por CNPJ, depois agrega os imóveis daquele trimestre.
    max_dref: dict[str, date] = {}
    for r in imovel:
        cnpj = _col(r, *_CNPJ_COLS)
        dref = _data(_col(r, "Data_Referencia"))
        if cnpj is None or cnpj not in cnpjs or dref is None:
            continue
        if cnpj not in max_dref or dref > max_dref[cnpj]:
            max_dref[cnpj] = dref
    buckets: dict[str, list[tuple[Decimal | None, Decimal | None, Decimal]]] = {}
    for r in imovel:
        cnpj = _col(r, *_CNPJ_COLS)
        if cnpj not in max_dref or _data(_col(r, "Data_Referencia")) != max_dref[cnpj]:
            continue
        vac = _num(_col(r, "Percentual_Vacancia"))
        inad = _num(_col(r, "Percentual_Inadimplencia"))
        peso = _num(_col(r, "Percentual_Imovel_Total_Investido", "Area")) or Decimal(1)
        buckets.setdefault(cnpj, []).append((vac, inad, peso))
    return {
        cnpj: (
            _media_pct([(v, p) for v, _, p in itens]),
            _media_pct([(i, p) for _, i, p in itens]),
            max_dref[cnpj],
        )
        for cnpj, itens in buckets.items()
    }


# --- download + upsert ------------------------------------------------------------------------


def _baixar(url: str) -> Path:
    """Baixa um ZIP da CVM p/ arquivo temporário; devolve o caminho (o chamador apaga)."""
    try:
        with httpx.Client(transport=_transport, timeout=_TIMEOUT_S, follow_redirects=True) as http:
            resp = http.get(url)
    except httpx.HTTPError as e:
        raise CvmError(f"GET {url}: falha de rede ({type(e).__name__})") from None
    if resp.status_code >= 400:
        raise CvmError(f"GET {url} -> HTTP {resp.status_code}", status=resp.status_code)
    with tempfile.NamedTemporaryFile(delete=False, suffix=".zip", prefix="cvm_fii_") as f:
        f.write(resp.content)
        return Path(f.name)


def _mensal(isins: set[str], anos: list[int]) -> dict[str, FundamentoBruto]:
    """Baixa o Informe Mensal de cada ano (tolera 404 por ano — começo do ano ainda não publicado),
    parseia junto e apaga todos os ZIPs no fim."""
    caminhos: list[Path] = []
    try:
        for ano in anos:
            url = f"{settings.cvm_base_url}/INF_MENSAL/DADOS/inf_mensal_fii_{ano}.zip"
            try:
                caminhos.append(_baixar(url))
            except CvmError as e:
                if e.status == 404:
                    continue
                raise
        return _parse_mensal(caminhos, isins) if caminhos else {}
    finally:
        for p in caminhos:
            p.unlink(missing_ok=True)


def _trimestral(cnpjs: set[str], ano: int) -> dict:
    url = f"{settings.cvm_base_url}/INF_TRIMESTRAL/DADOS/inf_trimestral_fii_{ano}.zip"
    caminho = _baixar(url)
    try:
        return _parse_trimestral(caminho, cnpjs)
    finally:
        caminho.unlink(missing_ok=True)


def _upsert(db: Session, fundamentos: list[FundamentoBruto]) -> None:
    for fb in fundamentos:
        obj = db.scalars(select(FiiFundamento).where(FiiFundamento.isin == fb.isin)).first()
        if obj is None:
            obj = FiiFundamento(isin=fb.isin)
            db.add(obj)
        obj.cnpj = fb.cnpj
        obj.nome = fb.nome
        obj.administrador_nome = fb.administrador_nome
        obj.administrador_cnpj = fb.administrador_cnpj
        obj.data_funcionamento = fb.data_funcionamento
        obj.segmento = fb.segmento
        obj.mandato = fb.mandato
        obj.tipo_gestao = fb.tipo_gestao
        obj.tipo = fb.tipo
        obj.patrimonio_liquido_centavos = fb.patrimonio_liquido_centavos
        obj.num_cotistas = fb.num_cotistas
        obj.valor_patrimonial_cota_centavos = fb.valor_patrimonial_cota_centavos
        obj.dividend_yield_12m_pct = fb.dividend_yield_12m_pct
        obj.vacancia_pct = fb.vacancia_pct
        obj.inadimplencia_pct = fb.inadimplencia_pct
        obj.data_referencia = fb.data_referencia or date.today()
        obj.data_referencia_trimestral = fb.data_referencia_trimestral
        obj.alocacao = [
            FiiFundamentoAlocacao(classe=a.classe, valor_centavos=a.valor_centavos, pct=a.pct)
            for a in fb.alocacao
        ]
    db.commit()


def sincronizar_fundamentos_fii(db: Session, isins: set[str]) -> int:
    """Baixa/parseia o Informe Mensal (+ Trimestral) do ano corrente (fallback ano anterior no
    começo do ano) filtrado pelos `isins`, faz upsert em `fii_fundamento` e apaga os ZIPs."""
    alvo = {i.strip().upper() for i in isins if i}
    if not alvo:
        return 0
    ano = datetime.now(SP).year
    # Ano corrente + anterior → DY trailing-12M real (o ZIP anual só traz os meses daquele ano).
    fundamentos = _mensal(alvo, [ano, ano - 1])
    if not fundamentos:
        return 0

    cnpjs = {fb.cnpj for fb in fundamentos.values()}
    tri: dict = {}
    for a in (ano, ano - 1):  # trimestral é opcional — não falha a ingestão
        try:
            tri = _trimestral(cnpjs, a)
        except CvmError:
            tri = {}
        if tri:
            break
    for fb in fundamentos.values():
        t = tri.get(fb.cnpj)
        if t is not None:
            fb.vacancia_pct, fb.inadimplencia_pct, fb.data_referencia_trimestral = t

    _upsert(db, list(fundamentos.values()))
    return len(fundamentos)


def _isins_em_carteira(db: Session) -> set[str]:
    """ISINs distintos de FII de TODOS os usuários (job de sistema — cruza o isolamento de
    propósito, como `snapshot_saldos_todos`)."""
    return {
        i.strip().upper()
        for i in db.scalars(
            select(distinct(Investimento.isin)).where(
                Investimento.subtype == "REAL_ESTATE_FUND",
                Investimento.isin.is_not(None),
            )
        ).all()
        if i
    }


def atualizar_fundamentos_fii(db: Session) -> None:
    """Ingestão idempotente e throttled — nunca propaga erro (job de fundo)."""
    if not settings.cvm_ingestao_enabled:
        return
    try:
        isins = _isins_em_carteira(db)
        if not isins:
            return
        existentes = db.execute(
            select(FiiFundamento.isin, FiiFundamento.atualizado_em).where(
                FiiFundamento.isin.in_(isins)
            )
        ).all()
        if {i for i, _ in existentes} >= isins:  # já temos todos — checa idade do mais antigo
            mais_antigo = min(_aware(dt) for _, dt in existentes)
            if (datetime.now(UTC) - mais_antigo).days < settings.cvm_max_idade_dias:
                return
        n = sincronizar_fundamentos_fii(db, isins)
        logger.info("fundamentos de FII atualizados: %s fundo(s)", n)
    except CvmError as e:
        logger.warning("ingestão CVM falhou: %s", e)
    except Exception:  # noqa: BLE001 - job de fundo nunca derruba o caller
        logger.exception("ingestão CVM: erro inesperado")


def _aware(dt: datetime) -> datetime:
    return dt if dt.tzinfo is not None else dt.replace(tzinfo=UTC)
