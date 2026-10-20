# AGENTS.md — Brasil Saúde

Instruções para qualquer agente de IA que trabalhe neste repositório.

## Idioma e tom

- Toda resposta, comentário, documentação, mensagem de erro e commit em **português do Brasil**.
- Código didático: docstring de módulo, docstring em função pública e comentário que explica o
  **motivo** (com analogia quando o trecho for difícil). Comentário que mente é pior que nenhum.
- Explique a decisão antes do comando. Sem jargão vazio.

## Identidade do projeto

- **Brasil Saúde** — painel público de vigilância e responsabilização em saúde.
- Nasceu do modelo `projeto_loop` (<https://github.com/Georgebecker/projeto_loop>).
- Origem da base e divergências: [`docs/BASE_PROJETO_LOOP.md`](docs/BASE_PROJETO_LOOP.md).
- Antes de planejar qualquer mudança, confira a base: `python scripts/conferir_base.py`.

## Regras que não se negociam

1. **Nenhum valor de chave em arquivo versionado.** O `.env` é local, pertence ao dono e não
   deve ser alterado sem pedido explícito. A chave vive na variável de ambiente do Windows.
2. **Nenhum número de saúde sem fonte, período de referência e data de validação.** Dado não
   coletado não é dado: nunca inventar valor, URL ou data.
3. **Uma mudança pequena por ciclo**: hipótese → mudança → teste → métrica real →
   **ACEITO** (fica) ou **REJEITADO** (reverte). Registro em `log_loop.md`.
4. **Escopo do agente do Loop**: só os caminhos permitidos em
   `meu-loop-agente/program.md`. `meu-loop-agente/**`, `.env`, `.githooks/**` e
   `.github/**` são proibidos para ele.
5. **Decisão não trivial** vai para `NOTES.md`; o número da iteração, para
   `meu-loop-agente/log.md`.
6. **Privacidade**: nunca publicar dado individual identificável; agregar antes de expor.
7. **Capturas de tela**: no máximo 5 por projeto, com legenda explicativa, e só depois da
   suíte verde.

## Comandos do dia a dia

```powershell
.\.venv\Scripts\Activate.ps1
python -m pytest -q
python -m ruff check .
python meu-loop-agente/verificar_iteracao.py estado
python meu-loop-agente/medir_qualidade.py --detalhe
```

## Antes de dizer "pronto"

- A suíte e o lint passam de verdade (saída lida, não presumida).
- O que foi prometido no README existe no código.
- Nada de segredo em arquivo; `git status` sem `.env` e sem dado bruto.
