# Controle+ — pronto para GitHub e Render

Aplicação web Flask com páginas HTML e banco SQLite.

## Arquivos

- `app.py`: servidor Flask e API.
- `index.html`, `sistema.html`, `usuarios.html`, `historico.html`, `cadastro.html`, `baixa.html`: telas.
- `requirements.txt`: dependências Python.
- `render.yaml`: configuração do serviço Python no Render e disco persistente.
- `.env.example`: exemplo de configuração local.

## Publicar no GitHub

1. Extraia este ZIP.
2. Crie um repositório no GitHub.
3. Envie **o conteúdo desta pasta** para a raiz do repositório (o `app.py`, `requirements.txt` e `render.yaml` devem ficar na raiz).
4. Não envie banco de dados, backups ou arquivos `.env`. O `.gitignore` já exclui esses arquivos.

## Publicar no Render

**Opção recomendada:** no Render, selecione **New + → Blueprint**, conecte o repositório e deixe o Render ler o `render.yaml`.

Se criar um Web Service manualmente, configure:

- Runtime: `Python 3`
- Build Command: `pip install -r requirements.txt`
- Start Command: `gunicorn app:app --workers 1 --threads 4 --timeout 120`
- `SECRET_KEY`: gere uma chave aleatória forte.
- `INITIAL_ADMIN_PASSWORD`: defina uma senha forte para o primeiro acesso.
- `FLASK_ENV`: `production`
- `DATABASE_PATH`: `/var/data/controleplus.db`

Anexe um Persistent Disk montado em `/var/data`. O `render.yaml` já declara um disco de 1 GB. Se o Render estiver executando `yarn` ou Node.js, o serviço foi criado com runtime incorreto: crie um novo Web Service Python ou use o Blueprint deste repositório.

## Primeiro acesso e banco de dados

O banco será criado automaticamente no primeiro início. O usuário inicial é `gerente`; a senha será exatamente a que você informar em `INITIAL_ADMIN_PASSWORD`. Em produção, o app não inicia se essa senha ou `SECRET_KEY` estiverem ausentes.

O banco de dados original não foi incluído neste pacote, para evitar publicar dados operacionais no GitHub. Assim, o primeiro deploy inicia com banco vazio e companhias padrão. Para preservar os registros existentes, faça uma migração privada do arquivo SQLite para o disco persistente do Render; não coloque o `.db` no repositório público.

## Rodar localmente

```bash
python -m venv .venv
# Windows: .venv\\Scripts\\activate
# Linux/macOS: source .venv/bin/activate
pip install -r requirements.txt
python app.py
```

Abra `http://localhost:5000`. No ambiente local, se ainda não houver gerente, a senha inicial de desenvolvimento é `1234`; altere-a após entrar. Não use essa senha em produção.
