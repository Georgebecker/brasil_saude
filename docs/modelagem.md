# Modelagem de dados — Brasil Saúde

> Documento exigido pela **MAD** (Metodologia de Administração de Dados):
> a modelagem é decidida **antes** do código e fica registrada com nomes,
> tipos, origem e transformação de cada campo. Se o banco mudar, este arquivo
> muda no mesmo commit.

## 1. Princípio

O banco tem uma regra que vale mais que qualquer otimização: **número sem
proveniência não entra**. Toda tabela de fato aponta para `fonte`, e a chave
estrangeira é verificada pelo SQLite (`PRAGMA foreign_keys = ON`). O painel
pode ficar vazio; não pode ficar mentiroso.

Segunda regra: **agregação antes de exposição**. O banco não guarda
notificação individual — só contagens por UF/semana e por município/semana.
Nenhum campo identifica pessoa (sem nome, sem data de nascimento, sem CNS).

## 2. Visão geral

```
                 ┌────────────┐
                 │   fonte    │  proveniência (órgão, URL, licença, coleta)
                 └─────┬──────┘
        ┌──────────────┼───────────────┬──────────────┐
        │              │               │              │
┌───────▼──────┐ ┌─────▼──────┐ ┌──────▼──────┐ ┌─────▼──────┐
│ caso_semana  │ │   repasse  │ │  clima_dia  │ │ alerta_ears│
└───────┬──────┘ └─────┬──────┘ └──────┬──────┘ └─────┬──────┘
        │              │               │              │
        │        ┌─────▼──────┐  ┌─────▼──────┐       │
        └────────► municipio  │  │    uf      │◄──────┘
                 └────────────┘  └────────────┘
                        ▲               ▲
                        │               │
                 ┌──────┴───────────────┴─────┐
                 │      responsavel           │
                 └────────────────────────────┘
```

## 3. Tabelas

### 3.1 `fonte` — a escritura do dado

| Campo | Tipo | Origem | Regra |
|---|---|---|---|
| `id` | TEXT (PK) | decisão do projeto | estável, em `snake_case` (`sinan_dengue`, `inmet`, `ibge_localidades`, …) |
| `nome` | TEXT | decisão do projeto | nome legível na tela |
| `orgao` | TEXT | fonte | órgão responsável (IBGE, MS, INMET, Fiocruz) |
| `url` | TEXT | fonte | URL https exata usada na coleta |
| `licenca` | TEXT | fonte | licença/termos declarados |
| `periodo_referencia` | TEXT | fonte | período coberto (ex.: `2025`, `2022`) |
| `coletado_em` | TEXT | sistema | ISO-8601 UTC no momento da gravação |
| `status` | TEXT | sistema | `ok`, `parcial` ou `falhou` |
| `detalhe` | TEXT | sistema | mensagem curta (ex.: “3 estações sem sensor”) |

**Transformação:** nenhuma. É o registro bruto da origem.

### 3.2 `uf` e `municipio` — denominador comum

| Tabela | Campo | Tipo | Origem | Observação |
|---|---|---|---|---|
| `uf` | `sigla` | TEXT (PK) | IBGE | `SP` |
| `uf` | `codigo_ibge` | TEXT | IBGE | `35` |
| `uf` | `regiao` | TEXT | IBGE | `Sudeste` |
| `uf` | `populacao` | INTEGER | IBGE (Censo 2022) | usado para incidência por 100 mil |
| `uf` | `populacao_ano` | INTEGER | IBGE | `2022` |
| `municipio` | `codigo_ibge` | TEXT (PK) | IBGE | 7 dígitos |
| `municipio` | `uf` | TEXT (FK) | IBGE | ligação com `uf.sigla` |
| `municipio` | `latitude`/`longitude` | REAL | — | reservado; o MVP não usa coordenada de município |

**Transformação:** a resposta aninhada do IBGE (`microrregiao.mesorregiao.UF`
ou `regiao-imediata`) é achatada para `uf`. Município sem UF identificável é
**descartado e contado**, nunca chutado.

### 3.3 `caso_semana` — o coração epidemiológico

| Campo | Tipo | Origem | Regra |
|---|---|---|---|
| `uf` | TEXT (FK) | campo de UF da notificação | residência, quando disponível |
| `ano` | INTEGER | ano da semana epidemiológica | 2000–2100 |
| `semana` | INTEGER | semana epidemiológica (`SEM_NOT`) | 1–53 |
| `casos` | INTEGER | contagem de notificações | `>= 0` (CHECK) |
| `fonte_id` | TEXT (FK) | — | obrigatório |

**Chave primária:** `(uf, ano, semana, fonte_id)`.

**Transformação (ETL):** agrupar por UF e `SEM_NOT`, contando linhas. Não
filtramos por classificação final no MVP: a tela diz **“notificações”**, não
“casos confirmados”. Filtro por `classi_fin` fica no roadmap, porque descartar
notificação em investigação subestimaria o presente.

**Lacuna:** semana ausente **não** é gravada como zero. O serviço reconstrói a
grade e marca `None`; o EARS não avalia janela com lacuna.

### 3.4 `caso_municipio_semana`

Mesma estrutura de `caso_semana`, com `municipio_codigo` no lugar de `uf`.
Usada para (a) alertas de clima nos municípios com maior incidência e
(b) detalhe municipal no roadmap. No MVP é preenchida quando a fonte entrega
granularidade municipal (InfoDengue/SINAN).

### 3.5 `repasse` — orçamento

| Campo | Tipo | Origem | Regra |
|---|---|---|---|
| `uf` | TEXT (FK) | UF do favorecido | obrigatório |
| `municipio_codigo` | TEXT (FK) | quando o repasse é municipal | opcional |
| `data` | TEXT | data do empenho/pagamento | ISO `AAAA-MM-DD` |
| `valor` | REAL | valor em reais | sem arredondar na entrada |
| `descricao` | TEXT | ação/programa | texto da fonte, não inventado |
| `url_fonte` | TEXT | link do registro | https |
| `coletado_em` | TEXT | sistema | ISO-8601 |

**Transformação:** nenhuma agregação na entrada; soma é feita na consulta
(`orcamento.resumo`). Assim o painel pode mudar de recorte sem recoletar.

### 3.6 `clima_dia` — meteorologia

| Campo | Tipo | Origem | Regra |
|---|---|---|---|
| `estacao` | TEXT (PK parcial) | código INMET | `A701` |
| `uf` | TEXT (FK) | cadastro da estação | |
| `municipio_codigo` | TEXT (FK) | mapeamento estação→município | pode ser nulo |
| `data` | TEXT (PK parcial) | dia da medição | ISO |
| `precipitacao_mm` | REAL | coluna de chuva | nulo = sem sensor, **não** zero |
| `temp_max_c`/`temp_min_c` | REAL | temperaturas | nulo permitido |
| `fonte_id` | TEXT (FK) | — | |

**Chave primária:** `(estacao, data)`.

### 3.7 `alerta_ears` — derivado, não fonte

| Campo | Tipo | Regra |
|---|---|---|
| `uf`, `ano`, `semana` | chave | |
| `metodo` | TEXT | `C1`, `C2` ou `C3` |
| `observado` | INTEGER | valor da semana |
| `esperado` | REAL | média das 7 semanas da janela |
| `limite` | REAL | média + k × desvio |
| `anomalo` | INTEGER | 1/0 |
| `calculado_em` | TEXT | quando a faixa foi produzida |

**Transformação:** `src/ears.py`. Regravar o período é seguro (idempotente):
o alerta é recalculável a partir dos casos.

### 3.8 `responsavel` — responsabilização

`uf`, `cargo`, `nome`, `url_fonte`, `atualizado_em`. Guarda **apenas** cargo
público e nome de quem ocupa o cargo — dado público por definição. Nunca
dado pessoal de terceiro.

### 3.9 `log_coleta` e `meta`

`log_coleta` é a caixa-preta do ETL (início, fim, status, quantos registros).
`meta` guarda estados simples (`ibge_coletado_em`, versão do esquema).

## 4. Índices

- `idx_repasse_uf_data (uf, data)` — consulta da aba orçamentária.
- Chaves primárias já criam índice para as consultas do mapa e da série.

## 5. Privacidade e LGPD

| Dado | Guardamos? | Por quê |
|---|---|---|
| Notificação individual | **não** | desnecessária para o painel; risco de reidentificação |
| Nome de paciente, CNS, data de nascimento | **não** | dado pessoal sensível |
| Município agregado | sim | unidade mínima útil para vigilância pública |
| Nome de gestor público | sim | informação pública, cargo eletivo/nomeado |

Agregação mínima: UF/semana e município/semana. Não publicamos célula com
contagem que permita identificar pessoa (as fontes já entregam agregados).

## 6. Evolução prevista

1. `caso_semana` ganhar `classi_fin` como dimensão (provável/confirmado/descartado).
2. `clima_dia` receber `estacao_lat`/`clima_dia.estacao_lon` para mapa de calor.
3. Migração para PostgreSQL com `schema_migrations` (ver
   [`dba/migracao_enterprise.md`](dba/migracao_enterprise.md)).
