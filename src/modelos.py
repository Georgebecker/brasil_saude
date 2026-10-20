"""Contratos de saída da API do painel (Pydantic).

Por que modelar a resposta: o frontend é JavaScript puro, sem build. Um
contrato explícito aqui evita que uma mudança no banco quebre a tela em
silêncio — o teste da API compara com estes modelos.

Convenção de nomes: português, sem abreviação obscura. `casos`, `esperado`,
`limite`, `anomalo` são os mesmos termos que aparecem no gráfico e no texto
metodológico.
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class PontoSerie(BaseModel):
    """Um ponto do gráfico: a semana, o observado e a faixa do EARS."""

    ano: int
    semana: int
    rotulo: str
    casos: int | None = Field(default=None, description="None quando a semana não foi publicada")
    esperado: float | None = None
    limite: float | None = None
    anomalo: bool | None = None


class SerieUF(BaseModel):
    """Série completa de uma UF, com o método de detecção usado."""

    uf: str
    metodo: str
    semanas: list[PontoSerie]
    ultima: PontoSerie | None = None


class SituacaoUF(BaseModel):
    """Linha do mapa: situação da última semana disponível."""

    uf: str
    nome: str
    codigo_ibge: str
    regiao: str | None = None
    ano: int
    semana: int
    casos: int | None = None
    populacao: int | None = None
    incidencia: float | None = Field(
        default=None, description="Casos por 100 mil habitantes na semana"
    )
    disponivel: bool
    esperado: float | None = None
    limite: float | None = None
    anomalo: bool | None = None


class Repasse(BaseModel):
    """Um repasse federal de saúde para a UF."""

    id: int
    data: str
    valor: float
    descricao: str
    url_fonte: str


class ResumoOrcamento(BaseModel):
    """O que o painel mostra na aba de recursos."""

    uf: str
    disponivel: bool
    total: float = 0.0
    quantidade: int = 0
    periodo: str | None = None
    repasses: list[Repasse] = Field(default_factory=list)
    aviso_metodologico: str


class AlertaClima(BaseModel):
    """Condição meteorológica favorável a arbovirose em um município."""

    municipio_codigo: str
    municipio: str
    uf: str
    casos: int | None = None
    incidencia: float | None = None
    chuva_7d_mm: float | None = None
    temp_media_c: float | None = None
    nivel: str
    explicacao: str
    estacao: str
    data_referencia: str
    url_fonte: str


class Responsavel(BaseModel):
    """Quem responde legalmente pela saúde no estado (governador e secretário)."""

    uf: str
    cargo: str
    nome: str
    url_fonte: str
    atualizado_em: str


class FonteInfo(BaseModel):
    """Proveniência exibida na seção "Fontes e Metodologia"."""

    id: str
    nome: str
    orgao: str
    url: str
    licenca: str | None = None
    periodo_referencia: str | None = None
    coletado_em: str
    status: str
    detalhe: str | None = None


class Saude(BaseModel):
    """Resumo operacional: o painel está de pé e com dados até quando?"""

    status: str
    banco: str
    ufs: int
    municipios: int
    casos: int
    repasses: int
    clima: int
    ultima_semana: str | None
    fontes_ok: int
    fontes_com_problema: int
