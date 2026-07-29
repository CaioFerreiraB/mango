"""Fundamentos de FII (§4.9): ETL da CVM (parse offline via ZIP em memória), ingestão com o ZIP
apagado ao fim, e a leitura /posicao/fundamentos (P/VP, IDOR, indisponível). SQLite + Postgres."""

import io
import zipfile
from datetime import date
from decimal import Decimal

import httpx
import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.fii_fundamento import FiiFundamento
from app.models.investimento import Investimento
from app.models.pluggy import CredencialPluggy, ItemPluggy
from app.models.usuario import Usuario
from app.services import cvm_fii

ISIN = "BRGGRCCTF002"
CNPJ = "26.614.291/0001-00"

_GERAL = (
    "CNPJ_Fundo_Classe;Data_Referencia;Versao;Nome_Fundo_Classe;Codigo_ISIN;Nome_Administrador;"
    "CNPJ_Administrador;Data_Funcionamento;Segmento_Atuacao;Mandato;Tipo_Gestao\n"
    f"{CNPJ};2025-06-30;1;GGR COVEPI RENDA FII;{ISIN};Vórtx DTVM;22.610.500/0001-88;"
    "2017-07-14;Logística;Renda;Ativa\n"
    # Outro fundo, fora dos ISINs alvo → deve ser ignorado.
    "99.999.999/0001-99;2025-06-30;1;OUTRO FII;BROUTRXCTF009;Adm X;00.000.000/0001-00;"
    "2020-01-01;Papel;Títulos e Valores Mobiliários;Passiva\n"
)


def _complemento() -> str:
    cab = (
        "CNPJ_Fundo_Classe;Data_Referencia;Versao;Patrimonio_Liquido;Total_Numero_Cotistas;"
        "Valor_Patrimonial_Cotas;Percentual_Dividend_Yield_Mes\n"
    )
    linhas = []
    # 13 meses (2024-06 .. 2025-06): só os 12 mais recentes contam no DY. O DY vem como fração
    # (0.005 = 0,5%/mês) → o parser soma e multiplica por 100.
    meses = [(2024, m) for m in range(6, 13)] + [(2025, m) for m in range(1, 7)]
    for ano, mes in meses:
        dy = "0.0999" if (ano, mes) == (2024, 6) else "0.005"
        linhas.append(f"{CNPJ};{ano}-{mes:02d}-28;1;900000.00;500;9.99;{dy}")
    # Versão 2 do mês mais recente vence (DY 0.005, PL/cotistas/VP definitivos).
    linhas.append(f"{CNPJ};2025-06-28;2;1000000.00;1000;10.35;0.005")
    return cab + "\n".join(linhas) + "\n"


# Colunas reais do ativo_passivo: `Direitos_Bens_Imoveis` é o subtotal de imóveis (sem sub-linhas).
_ATIVO_PASSIVO = (
    "CNPJ_Fundo_Classe;Data_Referencia;Versao;Total_Investido;Direitos_Bens_Imoveis;CRI;"
    "Disponibilidades\n"
    f"{CNPJ};2025-06-30;1;1000.00;250.00;650.00;100.00\n"
)

# Vacância/inadimplência: arquivo `inf_trimestral_fii_imovel_<ano>.csv` (regex exato no parser);
# os percentuais vêm como fração (0.042 = 4,2%).
_IMOVEL = (
    "CNPJ_Fundo_Classe;Data_Referencia;Versao;Percentual_Vacancia;Percentual_Inadimplencia;Area\n"
    f"{CNPJ};2025-06-30;1;0.042;0.018;1000\n"
    f"{CNPJ};2025-06-30;1;0.060;0.000;1000\n"  # mesmo peso → média 5.10 / 0.90 (após ×100)
    f"{CNPJ};2025-03-31;1;0.990;0.990;1000\n"  # trimestre antigo → ignorado
)


def _zip(arquivos: dict[str, str]) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        for nome, conteudo in arquivos.items():
            zf.writestr(nome, conteudo.encode("latin-1"))  # CVM é latin1
    return buf.getvalue()


def _zip_mensal() -> bytes:
    return _zip(
        {
            "inf_mensal_fii_geral_2025.csv": _GERAL,
            "inf_mensal_fii_complemento_2025.csv": _complemento(),
            "inf_mensal_fii_ativo_passivo_2025.csv": _ATIVO_PASSIVO,
        }
    )


def _zip_trimestral() -> bytes:
    return _zip({"inf_trimestral_fii_imovel_2025.csv": _IMOVEL})


# --- parsing (offline) ----------------------------------------------------------------


def test_parse_mensal_ponte_isin_versao_dy_e_alocacao():
    out = cvm_fii._parse_mensal(io.BytesIO(_zip_mensal()), {ISIN})
    assert set(out) == {ISIN}  # o outro fundo (ISIN fora do alvo) não entra
    fb = out[ISIN]
    assert fb.cnpj == CNPJ
    assert fb.nome == "GGR COVEPI RENDA FII"
    assert fb.administrador_nome == "Vórtx DTVM"  # latin1 decodificado
    assert fb.data_funcionamento == date(2017, 7, 14)
    assert fb.tipo == "tijolo"  # Renda + Logística
    # Versão 2 do mês mais recente vence.
    assert fb.patrimonio_liquido_centavos == 100_000_000
    assert fb.num_cotistas == 1000
    assert fb.valor_patrimonial_cota_centavos == 1035
    # DY 12M = 12 × 0,005 × 100 (o mês 2024-06, 13º, fica de fora; June usa a versão 2 = 0,005).
    assert float(fb.dividend_yield_12m_pct) == pytest.approx(6.0)
    aloc = {a.classe: a for a in fb.alocacao}  # pct sobre a soma dos buckets (1000)
    assert aloc["CRI/CRA"].valor_centavos == 65_000 and aloc["CRI/CRA"].pct == Decimal("65.0000")
    assert aloc["Imóveis"].pct == Decimal("25.0000")
    assert aloc["Caixa e liquidez"].pct == Decimal("10.0000")


def test_parse_mensal_sem_isin_alvo_vazio():
    assert cvm_fii._parse_mensal(io.BytesIO(_zip_mensal()), {"BRXXXXXXXXX9"}) == {}


def test_parse_trimestral_media_do_ultimo_trimestre():
    out = cvm_fii._parse_trimestral(io.BytesIO(_zip_trimestral()), {CNPJ})
    vac, inad, dref = out[CNPJ]
    assert vac == Decimal("5.1000") and inad == Decimal("0.9000")
    assert dref == date(2025, 6, 30)


# --- download + ingestão --------------------------------------------------------------


def test_mensal_apaga_o_zip_ao_fim(tmp_path, monkeypatch):
    criados: list = []

    def fake_baixar(url: str):
        p = tmp_path / "cvm.zip"
        p.write_bytes(_zip_mensal())
        criados.append(p)
        return p

    monkeypatch.setattr(cvm_fii, "_baixar", fake_baixar)
    out = cvm_fii._mensal({ISIN}, [2025])
    assert ISIN in out
    assert not criados[0].exists()  # ZIP apagado no finally (requisito)


def test_sincronizar_upsert_com_trimestral(db: Session, monkeypatch):
    def handler(request: httpx.Request) -> httpx.Response:
        if "inf_mensal" in request.url.path:
            return httpx.Response(200, content=_zip_mensal())
        if "inf_trimestral" in request.url.path:
            return httpx.Response(200, content=_zip_trimestral())
        return httpx.Response(404)

    monkeypatch.setattr(cvm_fii, "_transport", httpx.MockTransport(handler))
    n = cvm_fii.sincronizar_fundamentos_fii(db, {ISIN})
    assert n == 1
    f = db.scalars(select(FiiFundamento).where(FiiFundamento.isin == ISIN)).first()
    assert f is not None
    assert f.valor_patrimonial_cota_centavos == 1035
    assert f.vacancia_pct == Decimal("5.1000")
    assert f.inadimplencia_pct == Decimal("0.9000")
    assert len(f.alocacao) == 3


# --- leitura /posicao/fundamentos -----------------------------------------------------


def _item(db: Session, usuario: Usuario) -> ItemPluggy:
    cred = CredencialPluggy(
        usuario_id=usuario.id, client_id_cifrado="cid", client_secret_cifrado="sec"
    )
    db.add(cred)
    db.commit()
    db.refresh(cred)
    item = ItemPluggy(
        usuario_id=usuario.id, credencial_id=cred.id, pluggy_item_id=f"item-{usuario.id}"
    )
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


def _fii(db: Session, usuario: Usuario, item: ItemPluggy) -> Investimento:
    inv = Investimento(
        usuario_id=usuario.id,
        item_id=item.id,
        pluggy_investment_id=f"inv-{usuario.id}",
        type="EQUITY",
        subtype="REAL_ESTATE_FUND",
        saldo_centavos=101_200,
        code="GGRC11",
        isin=ISIN,
        quantity=Decimal(100),
        value_unitario=Decimal("10.12"),  # cotação → 1012 centavos
    )
    db.add(inv)
    db.commit()
    db.refresh(inv)
    return inv


def _seed_fundamento(db: Session) -> None:
    db.add(
        FiiFundamento(
            isin=ISIN,
            cnpj=CNPJ,
            nome="GGR COVEPI RENDA FII",
            valor_patrimonial_cota_centavos=1035,
            dividend_yield_12m_pct=Decimal("6.00"),
            data_referencia=date(2025, 6, 30),
        )
    )
    db.commit()


def test_fundamentos_pvp_e_disponivel(db, usuario_a, client_factory):
    item = _item(db, usuario_a)
    inv = _fii(db, usuario_a, item)
    _seed_fundamento(db)
    corpo = (
        client_factory(usuario_a)
        .get("/api/investimentos/posicao/fundamentos", params={"ids": [inv.id]})
        .json()
    )
    assert corpo["disponivel"] is True
    assert corpo["cotacao_centavos"] == 1012
    assert corpo["pvp"] == pytest.approx(0.98, abs=0.001)  # 1012 / 1035
    assert corpo["valor_patrimonial_cota_centavos"] == 1035


def test_fundamentos_indisponivel_antes_da_ingestao(db, usuario_a, client_factory):
    item = _item(db, usuario_a)
    inv = _fii(db, usuario_a, item)  # sem seed do fundamento
    corpo = (
        client_factory(usuario_a)
        .get("/api/investimentos/posicao/fundamentos", params={"ids": [inv.id]})
        .json()
    )
    assert corpo["disponivel"] is False
    assert corpo["cotacao_centavos"] == 1012  # a cotação (Pluggy) ainda vem


def test_fundamentos_nao_fii_indisponivel(db, usuario_a, client_factory):
    item = _item(db, usuario_a)
    inv = Investimento(
        usuario_id=usuario_a.id,
        item_id=item.id,
        pluggy_investment_id="inv-rf",
        type="FIXED_INCOME",
        saldo_centavos=10_000,
    )
    db.add(inv)
    db.commit()
    db.refresh(inv)
    corpo = (
        client_factory(usuario_a)
        .get("/api/investimentos/posicao/fundamentos", params={"ids": [inv.id]})
        .json()
    )
    assert corpo["disponivel"] is False


def test_fundamentos_idor(db, usuario_a, usuario_b, client_factory):
    item = _item(db, usuario_a)
    inv = _fii(db, usuario_a, item)
    _seed_fundamento(db)
    # Usuário B tenta ler a posição de A → 404 (barra IDOR).
    resp = client_factory(usuario_b).get(
        "/api/investimentos/posicao/fundamentos", params={"ids": [inv.id]}
    )
    assert resp.status_code == 404
