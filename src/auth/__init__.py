"""Protótipo de identidade e autorização (Fase 2).

Este pacote **não** é um sistema de autenticação de produção: ele demonstra a
política de acesso (quem pode ver o quê) com tokens assinados localmente. A
integração real com a plataforma gov.br (OAuth2/OIDC) está descrita em
`docs/arquitetura/integracao_servicos.md`.
"""

from __future__ import annotations
