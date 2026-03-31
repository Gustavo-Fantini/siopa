# SECURITY.md

Este documento descreve práticas de segurança, proteção de segredos e como reportar vulnerabilidades no projeto SIOPA.

## Política de Divulgação
- Reporte vulnerabilidades de forma privada por e-mail/contato do repositório.
- Não crie issues públicas com detalhes exploráveis.
- Aguarde coordenação para divulgação responsável após correção.

## Proteção de Segredos
- Nunca comite `.env` reais. Use `.env.example` como template.
- Revogue e rotacione chaves comprometidas imediatamente.
- Use variáveis de ambiente para tokens (OpenWeather, WeatherAPI, etc.).
- Limite escopo e permissões das chaves (princípio do menor privilégio).

## Armazenamento Seguro
- Não armazene segredos em README, comentários, capturas de tela ou logs.
- Logs não devem conter tokens; revise antes de anexar em issues.

## Dependências
- Instale sempre via `pip install -r requirements.txt`.
- Atualize com segurança: avalie changelogs antes de subir versões.

## Atualizações e Patches
- Correções de segurança devem ser revisadas e testadas (CI local) antes do merge.
- Aplique hotfixes em branches dedicadas e faça release notes.

## Relato de Vulnerabilidades
Inclua no contato (privado):
- Descrição clara do problema e impacto
- Passos de reprodução
- Ambiente (SO, versão Python)
- Exploit PoC minimamente necessário

## Checklist de Segurança (pré-release)
- [ ] `.env.example` sem segredos
- [ ] `.gitignore` cobre `.env`, `data/`, `logs/`, `models/`, `.venv/`
- [ ] Logs sem segredos
- [ ] Dependências auditadas
