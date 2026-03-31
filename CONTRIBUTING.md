# CONTRIBUTING.md

Obrigado por contribuir com o SIOPA! Este guia descreve como propor mudanças de forma organizada.

## Fluxo de Trabalho
1. Crie um fork do repositório.
2. Crie uma branch descritiva:
   - `feat/<escopo>-<resumo>`
   - `fix/<escopo>-<resumo>`
   - `docs/<escopo>-<resumo>`
3. Faça commits pequenos e objetivos.
4. Abra um Pull Request (PR) para `main` com descrição clara.

## Commits
- Use mensagens imperativas e curtas:
  - `feat(api): adiciona endpoint de análise de imagem`
  - `fix(upload): corrige validação de tamanho`
  - `docs(readme): inclui guia de instalação`

## Padrões de Código
- Python 3.10/3.11
- Formatação: `black`
- Lint: `flake8`
- Testes: `pytest`

## Ambiente de Desenvolvimento
```
python -m venv .venv
.venv\\Scripts\\activate  # Windows
# source .venv/bin/activate  # Linux/macOS
pip install -r requirements.txt
```

## Testes
```
pytest -q
```

## Diretrizes para PRs
- Descreva o problema e a solução.
- Inclua passos de reprodução, se relevante.
- Marque a issue relacionada.
- Adicione prints/logs apenas quando necessário para entendimento.

## Segurança
- Não comitar segredos.
- Consulte `SECURITY.md` para políticas e reporte de vulnerabilidades.

## Código de Conduta
- A participação neste projeto implica concordância com o `CODE_OF_CONDUCT.md`.
