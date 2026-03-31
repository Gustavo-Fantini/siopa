# HISTORY_CLEANUP.md

Guia para reescrever o histórico Git e remover segredos acidentalmente comitados.

IMPORTANTE: Reescrever histórico altera commits antigos e exigirá force-push. Combine com o time antes.

## Opção A) git filter-repo (recomendado)
Pré-requisitos:
- Git >= 2.22
- Instalar filter-repo: https://github.com/newren/git-filter-repo

### 1. Remover arquivos específicos do histórico
```
# Ex.: remover .env e app.db do histórico inteiro
git filter-repo --invert-paths --path .env --path app.db --force
```

### 2. Remover por padrão (glob)
```
# Remover todos os .env do histórico
git filter-repo --path-glob "*.env" --invert-paths --force
```

### 3. Remover padrões comuns (exemplo)
Crie um arquivo `paths-to-remove.txt` com linhas como:
```
.env
*.env
app.db
logs/
data/
```
Execute:
```
git filter-repo --invert-paths --paths-from-file paths-to-remove.txt --force
```

### 4. Regravar autores/emails (opcional)
```
git filter-repo --mailmap my-mailmap.txt --force
```

### 5. Atualizar remoto (force push)
```
git remote -v
# Certifique-se de que o remoto está correto

git push origin --force --all
git push origin --force --tags
```

## Opção B) BFG Repo-Cleaner (alternativa simples)
- https://rtyley.github.io/bfg-repo-cleaner/

### 1. Remover senhas e chaves por padrão
```
java -jar bfg.jar --replace-text banned.txt
```
`banned.txt` exemplo:
```
password==>***REMOVED***
OPENWEATHER_API_KEY==>***REMOVED***
WEATHERAPI_KEY==>***REMOVED***
```

### 2. Remover arquivos grandes/sensíveis
```
java -jar bfg.jar --delete-files "*.env" --delete-folders logs,data
```

### 3. Finalizar
```
git reflog expire --expire=now --all
git gc --prune=now --aggressive

git push origin --force --all
```

## Pós-limpeza (obrigatório)
- Revogue e gere novas chaves nos provedores (OpenWeather, etc.).
- Avise colaboradores para refazer o clone (`git clone`) ou resetar hard para o novo histórico.
- Abra um PR/commit atualizando `.env.example` e `.gitignore` se necessário.

## Checklist
- [ ] Segredos identificados
- [ ] Histórico reescrito
- [ ] Force push executado
- [ ] Chaves rotacionadas
- [ ] Colaboradores avisados
