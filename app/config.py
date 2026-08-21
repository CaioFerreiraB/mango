"""Configuração da aplicação (mesma base p/ self-hosted e local — varia só por env)."""

from pathlib import Path
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict

# Chaves de DESENVOLVIMENTO, versionadas no repo. Em produção (self-hosted) defina
# ENCRYPTION_KEY/SECRET_KEY no ambiente do container (§5.5) — nunca confie nestas: rodar
# self-hosted com elas = qualquer um decifra as credenciais do banco (a guarda de boot em
# `chaves_inseguras()` recusa isso). Gerar uma nova chave Fernet:
#   python -c "import os,base64; print(base64.urlsafe_b64encode(os.urandom(32)).decode())"
_DEV_ENCRYPTION_KEY = "3CPNFKQBk0AU10njLXpJ2sj9ZB_-MeviTY3tixSptxE="
_DEV_SECRET_KEY = "dev-insecure-secret-change-me"

# Docker/Swarm secrets: cada segredo é um arquivo cujo nome é o campo em minúsculas
# (`/run/secrets/encryption_key`). Só declaramos o diretório quando ele existe — apontar para um
# caminho ausente faz o pydantic-settings emitir warning em todo boot fora de container.
# Precedência: variável de ambiente vence o arquivo, então use um ou outro, nunca os dois.
_SECRETS_DIR = "/run/secrets" if Path("/run/secrets").is_dir() else None


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        secrets_dir=_SECRETS_DIR,
    )

    # `local` = desktop monousuário (usuário implícito); `self_hosted` = multiusuário.
    app_mode: Literal["local", "self_hosted"] = "local"

    # SQLite por padrão (dev/local); Postgres por env no self-hosted/CI.
    database_url: str = "sqlite:///./mango.db"

    # Assinatura de sessão (§5.2). Usado pelo fluxo de auth da Fase 1.
    secret_key: str = _DEV_SECRET_KEY

    # Cifragem em repouso de credenciais/segredos (§5.5).
    encryption_key: str = _DEV_ENCRYPTION_KEY

    # Cookie de sessão `Secure` (só trafega em HTTPS). Padrão seguro p/ produção (reverse proxy
    # com TLS, §5.1/§5.3). No teste local em http://localhost o compose seta como `false`.
    session_cookie_secure: bool = True

    # Boot: aplica migrations e popula a taxonomia de categorias (§5.4).
    run_migrations_on_boot: bool = True
    seed_categorias_on_boot: bool = True

    # Integração Pluggy (§4.3). Base URL fixa por config — nunca vem de request de usuário (SSRF).
    pluggy_base_url: str = "https://api.pluggy.ai"
    # Janela do sync incremental (dias para trás a partir de agora, com margem sobre o último sync).
    sync_janela_dias: int = 30
    # Tolerância de datas no pareamento de transferências de duas pernas (§4.4).
    sync_pareamento_dias: int = 3
    # Throttle do sync manual por item (minutos) — respeita o limite do Pluggy e evita abuso (S5).
    sync_min_intervalo_min: int = 5

    # Indicadores de mercado (§4.9/§5.6). CDI/SELIC/IPCA vêm do BCB SGS (sem chave); IBOV e
    # preços históricos de renda variável vêm do brapi.dev e exigem token (gratuito) — sem
    # token, IBOV sai da lista e a reconstrução do passado da carteira é pulada.
    brapi_base_url: str = "https://brapi.dev/api"
    # Fallback quando o usuário não gravou o token no perfil (cifrado). Preferir o do perfil.
    brapi_token: str = ""

    # Fundamentos de FII via dados abertos da CVM (§4.9). Base URL fixa por config (SSRF); o job
    # de ETL baixa o ZIP anual, filtra pelos ISINs em carteira e apaga o arquivo. `enabled=False`
    # desliga a ingestão (mantém a leitura do que já está no banco).
    cvm_base_url: str = "https://dados.cvm.gov.br/dados/FII/DOC"
    cvm_ingestao_enabled: bool = True
    # Idade máxima dos fundamentos antes de re-ingerir (o Informe Mensal chega ~15–30d após o mês).
    cvm_max_idade_dias: int = 20

    # Detecção automática de assinaturas (§4.7): mínimo de ocorrências para caracterizar
    # recorrência e tolerância relativa de variação de valor entre elas.
    assinatura_min_ocorrencias: int = 3
    assinatura_tolerancia_valor: float = 0.15

    @property
    def is_sqlite(self) -> bool:
        return self.database_url.startswith("sqlite")

    def chaves_inseguras(self) -> list[str]:
        """Nomes das chaves inservíveis para produção (guarda de boot S2).

        Cobre dois casos: o default versionado no repo e o valor **vazio** — num container, uma
        variável de ambiente não definida vira string vazia na substituição do compose, e sem esta
        checagem o boot passaria para só quebrar depois, na primeira cifragem.
        """
        inseguras = []
        if not self.encryption_key.strip() or self.encryption_key == _DEV_ENCRYPTION_KEY:
            inseguras.append("ENCRYPTION_KEY")
        if not self.secret_key.strip() or self.secret_key == _DEV_SECRET_KEY:
            inseguras.append("SECRET_KEY")
        return inseguras


settings = Settings()
