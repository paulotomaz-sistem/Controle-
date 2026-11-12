# Controle+ — Sistema da Secretaria

Aplicação web em Flask com páginas HTML e banco SQLite.

## Estrutura

- `app.py`: servidor Flask e API.
- `index.html`: tela de acesso.
- `sistema.html`, `cadastro.html`, `baixa.html`, `historico.html`, `usuarios.html`: telas do sistema.
- `requirements.txt`: dependências Python.
- `render.yaml`: configuração de deploy no Render.

## Rodar localmente

1. Instale Python 3.10 ou superior.
2. Crie e ative um ambiente virtual.
3. Instale as dependências:

   ```bash
   pip install -r requirements.txt
   ```

4. Configure as variáveis de ambiente (recomendado): `SECRET_KEY` e `INITIAL_ADMIN_PASSWORD`.
5. Inicie:

   ```bash
   python app.py
   ```

6. Abra `http://localhost:5000`.

Na primeira execução, o sistema cria o banco e as tabelas automaticamente. Se `INITIAL_ADMIN_PASSWORD` não for definida, a senha inicial permanece `1234`; defina uma senha forte antes de publicar e altere-a depois do primeiro acesso.

## Publicar no GitHub

1. Crie um repositório novo no GitHub.
2. Envie todos os arquivos desta pasta, mantendo a estrutura.
3. **Não envie banco de dados, backups, `.env` ou senhas.** O `.gitignore` já protege esses arquivos.

## Publicar no Render

1. No Render, escolha **New + → Blueprint** e conecte o repositório GitHub, ou crie um **Web Service** a partir dele.
2. Se usar Blueprint, o Render lê `render.yaml`. Se criar Web Service manualmente, use:
   - Runtime: Python 3
   - Build Command: `pip install -r requirements.txt`
   - Start Command: `gunicorn app:app --workers 1 --threads 4 --timeout 120`
3. Configure as variáveis: `SECRET_KEY` (valor aleatório forte), `INITIAL_ADMIN_PASSWORD` (senha inicial forte), `FLASK_ENV=production` e `DATABASE_PATH=/var/data/controleplus.db`.
4. Anexe um **Persistent Disk** montado em `/var/data` (o `render.yaml` já descreve um disco de 1 GB). SQLite precisa de armazenamento persistente: sem disco, os dados podem ser perdidos em novos deploys/reinicializações.
5. Faça o deploy e abra a URL fornecida pelo Render.

## Banco de dados e migração

O arquivo `controleplus.db` original foi deliberadamente excluído deste pacote para não publicar dados operacionais. O primeiro deploy criará um banco vazio com as tabelas e companhias padrão. Se precisar preservar cadastros existentes, faça uma migração segura do banco para o disco persistente do Render; não coloque o arquivo `.db` no repositório público.

## Segurança

- Defina `SECRET_KEY` e `INITIAL_ADMIN_PASSWORD` no painel do Render, nunca no código.
- Troque a senha inicial assim que entrar no sistema.
- Restrinja o acesso ao repositório e à aplicação conforme a sensibilidade dos dados.
- Faça backups periódicos do banco pelo recurso de backup do sistema e guarde-os em local privado.
