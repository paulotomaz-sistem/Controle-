# Controle+ — pacote Python para GitHub e Render

Este pacote é uma aplicação **Python/Flask**, não Node.js.

## Arquivos que precisam ficar na raiz do repositório

`app.py`, `requirements.txt`, `render.yaml`, `Procfile`, `.python-version`,
`index.html`, `sistema.html`, `usuarios.html`, `historico.html`,
`cadastro.html` e `baixa.html`.

## Publicar no GitHub

1. Extraia este ZIP.
2. Envie o **conteúdo** desta pasta para a raiz do repositório GitHub.
3. Confira no GitHub que `app.py`, `requirements.txt` e `render.yaml`
   aparecem logo na primeira tela do repositório, sem uma pasta extra envolvendo tudo.
4. Não envie banco de dados, backups ou arquivos `.env`.

## IMPORTANTE: corrigir o serviço do Render

O log anterior mostrou `Using Node.js` e `yarn`. Isso confirma que o serviço
antigo foi criado com runtime Node. **Não continue fazendo deploy nesse serviço**:
o runtime dele não é corrigido apenas trocando o comando de inicialização.

Crie um serviço Python novo a partir deste repositório:

1. No Render, escolha **New + → Blueprint**.
2. Conecte o repositório GitHub que contém estes arquivos na raiz.
3. O Render deve detectar este `render.yaml` e criar o serviço com runtime Python.
4. Quando solicitado, informe `INITIAL_ADMIN_PASSWORD` com uma senha forte.
5. Confirme a criação do serviço e aguarde a instalação via `pip`.

Se preferir criar **Web Service** manualmente, escolha runtime **Python 3**,
Build Command `pip install -r requirements.txt` e Start Command
`gunicorn app:app --workers 1 --threads 4 --timeout 120`.

O arquivo `render.yaml` configura um disco persistente em `/var/data`.
O uso de disco persistente pode exigir um plano pago do Render. Se sua conta
não permitir disco, não remova essa configuração sem decidir antes como
armazenar o banco: o armazenamento local temporário pode perder os dados
em reinicializações ou novos deploys.

## Primeiro acesso

O banco SQLite é criado automaticamente no primeiro início. O usuário inicial
é `gerente`; a senha é a que você definir em `INITIAL_ADMIN_PASSWORD`.

O banco original não está neste pacote para evitar publicar dados operacionais
no GitHub. O primeiro deploy começa com banco vazio. Para manter registros
antigos, faça uma migração privada do arquivo SQLite para o disco persistente.

## Teste local

```bash
python -m venv .venv
# Windows: .venv\\Scripts\\activate
# Linux/macOS: source .venv/bin/activate
pip install -r requirements.txt
python app.py
```

Abra `http://127.0.0.1:5000`.
