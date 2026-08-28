"""Categoria (§4.5): taxonomia do Pluggy + categorias personalizadas do usuário.

`GET /categories` do Pluggy é a base (seed idempotente, `usuario_id` NULL = linha global,
compartilhada por todos). `POST /categories` do Pluggy retorna 405 → categoria nova é **nossa**,
gravada na mesma tabela com `usuario_id` preenchido. Manter tudo numa tabela só preserva as 6 FKs
que já apontam para `categoria.pluggy_id` (transação ×2, assinatura, orçamento ×2, divisão), então
categoria personalizada funciona em orçamento/assinatura/divisão com integridade referencial real.

ATENÇÃO (S3): a tabela deixou de ser puramente global — toda leitura filtra
`usuario_id IS NULL OR usuario_id = <atual>` e toda escrita exige `usuario_id = <atual>`. O
`CategoriaRepository` é o único ponto que faz isso; não consultar `Categoria` direto fora dele.

`ativa` não é coluna: é a **ausência** de linha em `categoria_desativada` — o estado é por usuário e
uma linha global é compartilhada, então não caberia como flag na própria categoria.
"""

from sqlalchemy import ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.enums import TIPO_MATCH, check_in
from app.models.mixins import TimestampMixin, UserOwnedMixin

# Prefixo do id gerado para categoria personalizada. NÃO-numérico de propósito: as regras abaixo
# decidem por prefixo de id do Pluggy e o frontend escolhe o ícone pelos 2 primeiros dígitos — um id
# personalizado numérico sequestraria as duas.
PREFIXO_PERSONALIZADA = "u"

# Categorias-chave da taxonomia do Pluggy (§4.4, confirmadas na descoberta). Moram aqui, e não no
# serviço que as usa, porque hoje têm dois consumidores em camadas diferentes — `transferencia.py`
# (marca o pagamento de fatura como transferência) e o repositório de transação (filtra a listagem).
# O repositório não pode importar do serviço: `transferencia.py` importa `TransacaoRepository`.
CATEGORIA_PAGAMENTO_FATURA = "05100000"
PREFIXO_MESMA_TITULARIDADE = "04"


class Categoria(Base):
    __tablename__ = "categoria"
    __table_args__ = (
        # Nome único por usuário. As linhas globais têm `usuario_id` NULL e NULL nunca conflita
        # em UNIQUE (SQLite e Postgres) → o seed do Pluggy fica isento sem precisar de exceção.
        UniqueConstraint("usuario_id", "description", name="uq_categoria_usuario_id_description"),
    )

    # A maioria tem 8 dígitos, mas o 3º nível chega a 9 (ex.: 200300000) — 16 dá folga (e cabe o
    # id personalizado, "u" + 12 hex = 13). Postgres impõe o VARCHAR(n) (o SQLite não), então
    # subdimensionar quebra o seed no PG.
    pluggy_id: Mapped[str] = mapped_column(String(16), primary_key=True)
    # NULL = taxonomia global do Pluggy; preenchido = categoria criada pelo usuário.
    usuario_id: Mapped[int | None] = mapped_column(
        ForeignKey("usuario.id", ondelete="CASCADE"), index=True
    )
    description: Mapped[str] = mapped_column(String(255), nullable=False)  # inglês (ou o nome dado)
    description_translated: Mapped[str | None] = mapped_column(String(255))  # pt-BR
    parent_id: Mapped[str | None] = mapped_column(
        ForeignKey("categoria.pluggy_id", ondelete="RESTRICT"), index=True
    )
    # Nome de ícone lucide (kebab-case), só para categoria personalizada: a do Pluggy tira o ícone
    # da raiz do `pluggy_id`, que é fixa. NULL = sem escolha do usuário → o cliente cai no padrão.
    # Sem CHECK aqui — a allowlist vive na fronteira (`app/enums.ICONE_CATEGORIA`), ver lá o porquê.
    icone: Mapped[str | None] = mapped_column(String(40))


class CategoriaDesativada(Base):
    """Conjunto de exclusão: a categoria está desativada PARA ESTE usuário (§4.5).

    Ausência de linha = ativa. Modelado como conjunto (e não como flag `ativa`) porque a linha de
    `categoria` é compartilhada entre usuários e porque assim não há default para migrar: nasce
    vazio e só cresce quando o usuário desativa algo.
    """

    __tablename__ = "categoria_desativada"

    usuario_id: Mapped[int] = mapped_column(
        ForeignKey("usuario.id", ondelete="CASCADE"), primary_key=True
    )
    categoria_id: Mapped[str] = mapped_column(
        String(16), ForeignKey("categoria.pluggy_id", ondelete="CASCADE"), primary_key=True
    )


class RegraCategorizacao(UserOwnedMixin, TimestampMixin, Base):
    """Mapeia o nome de uma transação para uma categoria, automaticamente (§4.5).

    `texto_normalizado` (minúsculo, sem acento, espaços colapsados) é o que casa de fato — `texto`
    guarda o que o usuário digitou, para exibir. Casar em Python (e não com `LIKE`) mantém a
    normalização idêntica à do matching e evita `LIKE` com entrada do usuário.

    `categoria_id` é CASCADE: apagar uma categoria personalizada leva junto as regras que apontam
    para ela (a UI avisa antes). RESTRICT deixaria o usuário sem forma de excluir a categoria.
    """

    __tablename__ = "regra_categorizacao"
    __table_args__ = (
        UniqueConstraint("usuario_id", "texto_normalizado", "tipo_match"),
        check_in("tipo_match", TIPO_MATCH, "tipo_match"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    texto: Mapped[str] = mapped_column(String(120), nullable=False)
    texto_normalizado: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    tipo_match: Mapped[str] = mapped_column(String(8), nullable=False)  # exato | contem
    categoria_id: Mapped[str] = mapped_column(
        String(16),
        ForeignKey("categoria.pluggy_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
