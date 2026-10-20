"""Acesso à rede com retry, espera crescente e mensagem de erro honesta.

As APIs públicas do governo caem, mudam de formato e às vezes respondem 429.
A política do projeto (seção 8 do contrato) é: tentar de novo com espera
crescente, usar o cache local quando existir e **nunca** mostrar stack trace
para quem está vendo o painel.

Analogia: é como ligar para um cartório que vive com a linha ocupada. Você
tenta de novo, espera um pouco mais a cada tentativa e, se não conseguir,
anota no protocolo que a ligação não completou — em vez de inventar o teor do
documento.
"""

from __future__ import annotations

import json
import random
import time
from dataclasses import dataclass
from pathlib import Path

import requests

from src import config

# Status que valem nova tentativa: instabilidade do servidor ou excesso de
# requisições. Um 404 não melhora tentando de novo — falhar rápido é melhor.
STATUS_TRANSITORIOS = {408, 425, 429, 500, 502, 503, 504}


class FalhaDeRede(RuntimeError):
    """Erro de rede já explicado em português, pronto para ir à interface."""


@dataclass
class Resposta:
    """Resultado de uma chamada: conteúdo, URL final e status."""

    conteudo: bytes
    url: str
    status: int
    tipo: str

    def json(self) -> object:
        """Interpreta o corpo como JSON, com mensagem clara se não for."""
        try:
            return json.loads(self.conteudo.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as erro:
            raise FalhaDeRede(f"resposta de {self.url} não é JSON válido: {erro}") from erro

    def texto(self) -> str:
        """Corpo como texto — usado por CSV e HTML."""
        return self.conteudo.decode("utf-8", errors="replace")


class ClienteHTTP:
    """Cliente pequeno com retry exponencial e backoff com "ruído".

    O ruído (jitter) evita que várias coletas falhem e voltem no mesmo
    milissegundo, o que só pioraria a fila do servidor público.
    """

    def __init__(
        self,
        *,
        tentativas: int | None = None,
        tempo_limite: float | None = None,
        espera_base: float = 1.0,
        sessao: requests.Session | None = None,
    ) -> None:
        self.tentativas = tentativas or config.TENTATIVAS_REDE
        self.tempo_limite = tempo_limite or config.TEMPO_LIMITE_SEGUNDOS
        self.espera_base = espera_base
        self.sessao = sessao or requests.Session()
        self.sessao.headers.update({"User-Agent": config.USER_AGENT})

    def obter(
        self, url: str, *, params: dict | None = None, timeout: float | None = None
    ) -> Resposta:
        """GET com retry; devolve `Resposta` ou levanta `FalhaDeRede` explicada."""
        ultimo_erro = "sem detalhe"
        for tentativa in range(1, self.tentativas + 1):
            try:
                resposta = self.sessao.get(
                    url, params=params, timeout=timeout or self.tempo_limite
                )
            except requests.RequestException as erro:
                ultimo_erro = f"{type(erro).__name__}: {erro}"
            else:
                if resposta.status_code < 400:
                    return Resposta(
                        conteudo=resposta.content,
                        url=resposta.url,
                        status=resposta.status_code,
                        tipo=resposta.headers.get("Content-Type", ""),
                    )
                ultimo_erro = f"HTTP {resposta.status_code}"
                if resposta.status_code not in STATUS_TRANSITORIOS:
                    raise FalhaDeRede(
                        f"{url} respondeu {resposta.status_code}; não adianta repetir"
                    )
            if tentativa < self.tentativas:
                espera = self.espera_base * (2 ** (tentativa - 1))
                time.sleep(espera + random.uniform(0, 0.5))
        raise FalhaDeRede(f"{url} falhou após {self.tentativas} tentativas ({ultimo_erro})")

    def obter_json(self, url: str, *, params: dict | None = None) -> object:
        """Atalho para endpoints JSON."""
        return self.obter(url, params=params).json()

    def baixar(self, url: str, destino: Path, *, sobrescrever: bool = False) -> Path:
        """Baixa um arquivo para o disco, de forma atômica.

        Grava em `.parcial` e só renomeia quando termina: um download
        interrompido nunca deixa um arquivo "válido" pela metade, que depois
        seria lido como se fosse o dado inteiro.
        """
        destino.parent.mkdir(parents=True, exist_ok=True)
        if destino.exists() and not sobrescrever:
            return destino
        temporario = destino.with_suffix(destino.suffix + ".parcial")
        resposta = self.obter(url)
        temporario.write_bytes(resposta.conteudo)
        temporario.replace(destino)
        return destino
