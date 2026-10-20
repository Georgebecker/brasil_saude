"""Serviços independentes do painel (MDSOA): epidemiologia, orçamento e clima.

Cada serviço tem o seu próprio contrato e os seus próprios testes. A rota HTTP
apenas traduz o serviço para JSON — a regra de negócio mora aqui, não na rota.
"""

from __future__ import annotations
