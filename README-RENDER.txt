CONTROLE+ — DEPLOY NO RENDER

1. Extraia este ZIP.
2. Envie o conteúdo da pasta Controle+ para a raiz de um repositório GitHub.
   Na raiz do repositório devem ficar app.py, requirements.txt, render.yaml
   e os arquivos HTML.
3. No Render, escolha New + > Blueprint e conecte esse repositório.
   O Render lerá o render.yaml automaticamente.
   Se preferir Web Service manual, selecione Python e use:
     Build Command: pip install -r requirements.txt
     Start Command: python -m gunicorn app:app --bind 0.0.0.0:$PORT
   Root Directory: deixe vazio.
4. Faça o deploy.

LOGIN INICIAL
  Usuário: gerente
  Senha: 1234

IMPORTANTE SOBRE O BANCO DE DADOS
O sistema usa SQLite. Em hospedagem Render sem disco persistente,
alterações no banco podem ser perdidas quando a instância reiniciar
ou for redeployada. Para manter os dados, configure um Persistent Disk
pago no Render montado em /var/data e defina DB_PATH=/var/data/controleplus.db
nas variáveis de ambiente. Antes de colocar em produção, troque a senha
inicial do gerente e mantenha SECRET_KEY privada.
