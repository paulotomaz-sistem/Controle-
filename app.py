# ============================================================
# Controle+ — Backend Flask
# Sistema da Secretaria
# ============================================================
# Requisitos:
#   pip install flask werkzeug
#
# Executar:
#   python app.py
#
# Acessar:
#   http://127.0.0.1:5000
# ============================================================

import os
import sqlite3
from datetime import datetime, timedelta
from functools import wraps

from flask import (
    Flask, request, jsonify, session,
    send_from_directory, send_file, redirect, url_for
)
from werkzeug.security import generate_password_hash, check_password_hash


# ============================================================
# CONFIGURAÇÃO
# ============================================================
BASE_DIR = os.path.abspath(os.path.dirname(__file__))
# Render: configure DATABASE_PATH=/var/data/controleplus.db and attach a persistent disk.
DB_PATH = os.environ.get('DATABASE_PATH', os.path.join(BASE_DIR, 'controleplus.db'))
os.makedirs(os.path.dirname(os.path.abspath(DB_PATH)), exist_ok=True)

app = Flask(__name__, static_folder=None)
_secret_key = os.environ.get('SECRET_KEY')
if not _secret_key and os.environ.get('FLASK_ENV') == 'production':
    raise RuntimeError('Configure SECRET_KEY nas variáveis de ambiente antes de publicar.')
app.secret_key = _secret_key or 'controleplus-dev-troque-esta-chave-em-producao'

app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
app.config['SESSION_COOKIE_SECURE'] = os.environ.get('FLASK_ENV') == 'production'  # HTTPS no Render
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(hours=8)


# ============================================================
# BANCO DE DADOS
# ============================================================
def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute('PRAGMA foreign_keys = ON')
    return conn


def _coluna_existe(cursor, tabela, coluna):
    cursor.execute(f"PRAGMA table_info({tabela})")
    return any(row['name'] == coluna for row in cursor.fetchall())


def init_db():
    conn = get_db()
    c = conn.cursor()

    # ---------- usuários ----------
    c.execute('''
        CREATE TABLE IF NOT EXISTS usuarios (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nome TEXT NOT NULL,
            usuario TEXT NOT NULL UNIQUE,
            senha_hash TEXT NOT NULL,
            perfil TEXT NOT NULL CHECK (perfil IN ('gerente','auxiliar')),
            ativo INTEGER NOT NULL DEFAULT 1,
            criado_em TEXT NOT NULL,
            criado_por TEXT
        )
    ''')

    # ---------- histórico ----------
    c.execute('''
        CREATE TABLE IF NOT EXISTS historico (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            data TEXT NOT NULL,
            autor TEXT NOT NULL,
            autor_usuario TEXT NOT NULL,
            acao TEXT NOT NULL,
            detalhe TEXT,
            alvo TEXT
        )
    ''')

    # ---------- militares ----------
    c.execute('''
        CREATE TABLE IF NOT EXISTS militares (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nome TEXT NOT NULL,
            posto TEXT,
            identidade TEXT UNIQUE,
            email TEXT,
            contato TEXT,
            criado_em TEXT NOT NULL
        )
    ''')

    # ---------- pedidos ----------
    c.execute('''
        CREATE TABLE IF NOT EXISTS pedidos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            militar_id INTEGER NOT NULL,
            tipo TEXT NOT NULL,
            data_entrada TEXT,
            via TEXT,
            responsavel TEXT,
            situacao TEXT NOT NULL DEFAULT 'Em elaboração',
            data_entrega TEXT,
            docs_ok INTEGER NOT NULL DEFAULT 0,
            criado_em TEXT NOT NULL,
            FOREIGN KEY (militar_id) REFERENCES militares(id) ON DELETE CASCADE
        )
    ''')

    # ---------- baixa por companhia ----------
    c.execute('''
        CREATE TABLE IF NOT EXISTS baixa (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            companhia TEXT NOT NULL UNIQUE,
            militares INTEGER NOT NULL DEFAULT 0,
            b1 INTEGER NOT NULL DEFAULT 0,
            b2 INTEGER NOT NULL DEFAULT 0,
            ep INTEGER NOT NULL DEFAULT 0
        )
    ''')

    # migração: bases antigas sem a coluna "militares"
    if not _coluna_existe(c, 'baixa', 'militares'):
        try:
            c.execute('ALTER TABLE baixa ADD COLUMN militares INTEGER NOT NULL DEFAULT 0')
        except sqlite3.OperationalError:
            pass

    # ---------- gerente master ----------
    c.execute("SELECT COUNT(*) AS n FROM usuarios WHERE perfil='gerente'")
    if c.fetchone()['n'] == 0:
        initial_password = os.environ.get('INITIAL_ADMIN_PASSWORD')
        if not initial_password:
            if os.environ.get('FLASK_ENV') == 'production':
                conn.close()
                raise RuntimeError('Defina INITIAL_ADMIN_PASSWORD para criar o primeiro gerente no ambiente de produção.')
            initial_password = '1234'
        c.execute('''
            INSERT INTO usuarios (nome, usuario, senha_hash, perfil, ativo, criado_em, criado_por)
            VALUES (?, ?, ?, 'gerente', 1, ?, 'sistema')
        ''', (
            'Gerente Master',
            'gerente',
            generate_password_hash(initial_password),
            datetime.now().isoformat()
        ))

    # ---------- companhias padrão ----------
    c.execute("SELECT COUNT(*) AS n FROM baixa")
    if c.fetchone()['n'] == 0:
        for cia in ['1ª CIA', '2ª CIA', '3ª CIA', '4ª CIA', '5ª CIA',
                    'CCS', 'CRM', 'Banda', 'Divisão']:
            c.execute('INSERT INTO baixa (companhia) VALUES (?)', (cia,))

    conn.commit()
    conn.close()


# ============================================================
# HELPERS
# ============================================================
def registrar_historico(acao, detalhe='', alvo=''):
    s = session.get('usuario')
    autor = s['nome'] if s else 'sistema'
    autor_usuario = s['usuario'] if s else 'sistema'
    conn = get_db()
    conn.execute('''
        INSERT INTO historico (data, autor, autor_usuario, acao, detalhe, alvo)
        VALUES (?, ?, ?, ?, ?, ?)
    ''', (datetime.now().isoformat(), autor, autor_usuario, acao, detalhe, alvo))
    conn.commit()
    conn.close()


def is_api():
    return request.path.startswith('/api/')


def login_required(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        if 'usuario' not in session:
            if is_api():
                return jsonify({'ok': False, 'erro': 'Não autenticado.'}), 401
            return redirect(url_for('index'))
        return f(*args, **kwargs)
    return wrapper


def gerente_required(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        if 'usuario' not in session:
            if is_api():
                return jsonify({'ok': False, 'erro': 'Não autenticado.'}), 401
            return redirect(url_for('index'))
        if session['usuario']['perfil'] != 'gerente':
            if is_api():
                return jsonify({'ok': False, 'erro': 'Acesso restrito ao gerente.'}), 403
            return redirect(url_for('sistema_page'))
        return f(*args, **kwargs)
    return wrapper


# ============================================================
# PÁGINAS
# ============================================================
@app.route('/')
def index():
    return send_from_directory(BASE_DIR, 'index.html')


@app.route('/sistema.html')
@login_required
def sistema_page():
    return send_from_directory(BASE_DIR, 'sistema.html')


@app.route('/usuarios.html')
@gerente_required
def usuarios_page():
    return send_from_directory(BASE_DIR, 'usuarios.html')


@app.route('/historico.html')
@login_required
def historico_page():
    return send_from_directory(BASE_DIR, 'historico.html')


@app.route('/cadastro.html')
@login_required
def cadastro_page():
    return send_from_directory(BASE_DIR, 'cadastro.html')


@app.route('/baixa.html')
@login_required
def baixa_page():
    return send_from_directory(BASE_DIR, 'baixa.html')


@app.route('/favicon.ico')
def favicon():
    icon = os.path.join(BASE_DIR, 'favicon.ico')
    if os.path.exists(icon):
        return send_from_directory(BASE_DIR, 'favicon.ico')
    return ('', 204)


# ============================================================
# API — AUTENTICAÇÃO
# ============================================================
@app.route('/api/login', methods=['POST'])
def api_login():
    dados = request.get_json(silent=True) or {}
    usuario = (dados.get('usuario') or '').strip()
    senha = (dados.get('senha') or '').strip()

    if not usuario or not senha:
        return jsonify({'ok': False, 'erro': 'Informe usuário e senha.'}), 400

    conn = get_db()
    u = conn.execute(
        'SELECT * FROM usuarios WHERE LOWER(usuario) = LOWER(?)',
        (usuario,)
    ).fetchone()
    conn.close()

    if not u or not check_password_hash(u['senha_hash'], senha):
        return jsonify({'ok': False, 'erro': 'Usuário ou senha inválidos.'}), 401

    if not u['ativo']:
        return jsonify({'ok': False, 'erro': 'Usuário inativo. Procure o gerente.'}), 403

    session.permanent = True
    session['usuario'] = {
        'id': u['id'],
        'nome': u['nome'],
        'usuario': u['usuario'],
        'perfil': u['perfil']
    }

    registrar_historico('LOGIN', f"Acesso como {u['perfil']}", u['usuario'])

    return jsonify({'ok': True, 'usuario': session['usuario']})


@app.route('/api/logout', methods=['POST'])
def api_logout():
    if 'usuario' in session:
        registrar_historico('LOGOUT', 'Saída do sistema', session['usuario']['usuario'])
    session.clear()
    return jsonify({'ok': True})


@app.route('/api/sessao', methods=['GET'])
def api_sessao():
    if 'usuario' not in session:
        return jsonify({'ok': False, 'erro': 'Não autenticado.'}), 401
    return jsonify({'ok': True, 'usuario': session['usuario']})


# ============================================================
# API — USUÁRIOS (somente gerente)
# ============================================================
@app.route('/api/usuarios', methods=['GET'])
@gerente_required
def api_listar_usuarios():
    conn = get_db()
    rows = conn.execute('''
        SELECT id, nome, usuario, perfil, ativo, criado_em, criado_por
        FROM usuarios ORDER BY criado_em DESC
    ''').fetchall()
    conn.close()
    return jsonify({'ok': True, 'usuarios': [dict(r) for r in rows]})


@app.route('/api/usuarios_responsaveis', methods=['GET'])
@login_required
def api_usuarios_responsaveis():
    """
    Lista leve para preencher o select 'Responsável' do cadastro.
    Acessível a gerente e auxiliar. Não expõe senha nem login.
    Retorna apenas usuários ATIVOS.
    """
    conn = get_db()
    rows = conn.execute('''
        SELECT nome FROM usuarios
        WHERE ativo = 1
        ORDER BY nome
    ''').fetchall()
    conn.close()
    return jsonify({
        'ok': True,
        'usuarios': [{'nome': r['nome'], 'ativo': True} for r in rows]
    })


@app.route('/api/usuarios', methods=['POST'])
@gerente_required
def api_criar_usuario():
    d = request.get_json(silent=True) or {}
    nome = (d.get('nome') or '').strip()
    usuario = (d.get('usuario') or '').strip()
    senha = (d.get('senha') or '').strip()
    perfil = (d.get('perfil') or '').strip()

    if not nome or not usuario or not senha or not perfil:
        return jsonify({'ok': False, 'erro': 'Preencha todos os campos.'}), 400
    if perfil not in ('gerente', 'auxiliar'):
        return jsonify({'ok': False, 'erro': 'Perfil inválido.'}), 400
    if len(senha) < 4:
        return jsonify({'ok': False, 'erro': 'Senha mínima de 4 caracteres.'}), 400

    conn = get_db()
    existe = conn.execute(
        'SELECT id FROM usuarios WHERE LOWER(usuario) = LOWER(?)',
        (usuario,)
    ).fetchone()
    if existe:
        conn.close()
        return jsonify({'ok': False, 'erro': 'Já existe um usuário com esse login.'}), 409

    autor = session['usuario']['usuario']
    conn.execute('''
        INSERT INTO usuarios (nome, usuario, senha_hash, perfil, ativo, criado_em, criado_por)
        VALUES (?, ?, ?, ?, 1, ?, ?)
    ''', (
        nome, usuario, generate_password_hash(senha), perfil,
        datetime.now().isoformat(), autor
    ))
    conn.commit()
    novo_id = conn.execute('SELECT last_insert_rowid() AS id').fetchone()['id']
    conn.close()

    registrar_historico('CRIAR_USUARIO', f'Criou usuário {usuario} ({perfil})', usuario)
    return jsonify({'ok': True, 'id': novo_id})


@app.route('/api/usuarios/<int:uid>', methods=['PUT'])
@gerente_required
def api_editar_usuario(uid):
    d = request.get_json(silent=True) or {}
    conn = get_db()
    u = conn.execute('SELECT * FROM usuarios WHERE id=?', (uid,)).fetchone()
    if not u:
        conn.close()
        return jsonify({'ok': False, 'erro': 'Usuário não encontrado.'}), 404

    nome = (d.get('nome') or u['nome']).strip()
    usuario = (d.get('usuario') or u['usuario']).strip()
    senha = (d.get('senha') or '').strip()
    perfil = (d.get('perfil') or u['perfil']).strip()

    if perfil not in ('gerente', 'auxiliar'):
        conn.close()
        return jsonify({'ok': False, 'erro': 'Perfil inválido.'}), 400

    if u['perfil'] == 'gerente' and perfil != 'gerente':
        qtd = conn.execute(
            "SELECT COUNT(*) AS n FROM usuarios WHERE perfil='gerente' AND ativo=1 AND id<>?",
            (uid,)
        ).fetchone()['n']
        if qtd == 0:
            conn.close()
            return jsonify({'ok': False, 'erro': 'É preciso manter pelo menos um gerente ativo.'}), 400

    dup = conn.execute(
        'SELECT id FROM usuarios WHERE LOWER(usuario)=LOWER(?) AND id<>?',
        (usuario, uid)
    ).fetchone()
    if dup:
        conn.close()
        return jsonify({'ok': False, 'erro': 'Já existe um usuário com esse login.'}), 409

    if senha:
        if len(senha) < 4:
            conn.close()
            return jsonify({'ok': False, 'erro': 'Senha mínima de 4 caracteres.'}), 400
        conn.execute('''
            UPDATE usuarios SET nome=?, usuario=?, senha_hash=?, perfil=? WHERE id=?
        ''', (nome, usuario, generate_password_hash(senha), perfil, uid))
    else:
        conn.execute('''
            UPDATE usuarios SET nome=?, usuario=?, perfil=? WHERE id=?
        ''', (nome, usuario, perfil, uid))

    conn.commit()
    conn.close()
    registrar_historico('EDITAR_USUARIO', f'Editou usuário {usuario}', usuario)
    return jsonify({'ok': True})


@app.route('/api/usuarios/<int:uid>/toggle', methods=['POST'])
@gerente_required
def api_toggle_usuario(uid):
    conn = get_db()
    u = conn.execute('SELECT * FROM usuarios WHERE id=?', (uid,)).fetchone()
    if not u:
        conn.close()
        return jsonify({'ok': False, 'erro': 'Usuário não encontrado.'}), 404

    novo = 0 if u['ativo'] else 1

    if u['perfil'] == 'gerente' and novo == 0:
        qtd = conn.execute(
            "SELECT COUNT(*) AS n FROM usuarios WHERE perfil='gerente' AND ativo=1 AND id<>?",
            (uid,)
        ).fetchone()['n']
        if qtd == 0:
            conn.close()
            return jsonify({'ok': False, 'erro': 'É preciso manter pelo menos um gerente ativo.'}), 400

    conn.execute('UPDATE usuarios SET ativo=? WHERE id=?', (novo, uid))
    conn.commit()
    conn.close()

    registrar_historico(
        'ATIVAR_USUARIO' if novo else 'DESATIVAR_USUARIO',
        f"{'Ativou' if novo else 'Desativou'} usuário {u['usuario']}",
        u['usuario']
    )
    return jsonify({'ok': True, 'ativo': bool(novo)})


@app.route('/api/usuarios/<int:uid>', methods=['DELETE'])
@gerente_required
def api_excluir_usuario(uid):
    conn = get_db()
    u = conn.execute('SELECT * FROM usuarios WHERE id=?', (uid,)).fetchone()
    if not u:
        conn.close()
        return jsonify({'ok': False, 'erro': 'Usuário não encontrado.'}), 404

    if session['usuario']['id'] == uid:
        conn.close()
        return jsonify({'ok': False, 'erro': 'Você não pode excluir a si mesmo.'}), 400

    if u['perfil'] == 'gerente':
        qtd = conn.execute(
            "SELECT COUNT(*) AS n FROM usuarios WHERE perfil='gerente' AND ativo=1 AND id<>?",
            (uid,)
        ).fetchone()['n']
        if qtd == 0:
            conn.close()
            return jsonify({'ok': False, 'erro': 'É preciso manter pelo menos um gerente.'}), 400

    conn.execute('DELETE FROM usuarios WHERE id=?', (uid,))
    conn.commit()
    conn.close()
    registrar_historico('EXCLUIR_USUARIO', f"Excluiu usuário {u['usuario']}", u['usuario'])
    return jsonify({'ok': True})


# ============================================================
# API — HISTÓRICO
# ============================================================
@app.route('/api/historico', methods=['GET'])
@login_required
def api_historico():
    try:
        limite = min(int(request.args.get('limite', 200)), 500)
    except ValueError:
        limite = 200
    conn = get_db()
    rows = conn.execute(
        'SELECT * FROM historico ORDER BY data DESC LIMIT ?', (limite,)
    ).fetchall()
    conn.close()
    return jsonify({'ok': True, 'historico': [dict(r) for r in rows]})


# ============================================================
# API — MILITARES
# ============================================================
@app.route('/api/militares', methods=['GET'])
@login_required
def api_listar_militares():
    conn = get_db()
    rows = conn.execute('SELECT * FROM militares ORDER BY nome').fetchall()
    conn.close()
    return jsonify({'ok': True, 'militares': [dict(r) for r in rows]})


@app.route('/api/militares', methods=['POST'])
@login_required
def api_criar_militar():
    d = request.get_json(silent=True) or {}
    nome = (d.get('nome') or '').strip()
    if not nome:
        return jsonify({'ok': False, 'erro': 'Nome é obrigatório.'}), 400

    conn = get_db()
    try:
        conn.execute('''
            INSERT INTO militares (nome, posto, identidade, email, contato, criado_em)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (
            nome,
            (d.get('posto') or '').strip(),
            (d.get('identidade') or '').strip() or None,
            (d.get('email') or '').strip(),
            (d.get('contato') or '').strip(),
            datetime.now().isoformat()
        ))
        conn.commit()
        novo_id = conn.execute('SELECT last_insert_rowid() AS id').fetchone()['id']
    except sqlite3.IntegrityError:
        conn.close()
        return jsonify({'ok': False, 'erro': 'Identidade militar já cadastrada.'}), 409
    conn.close()

    registrar_historico('CRIAR_MILITAR', f'Cadastrou militar {nome}', nome)
    return jsonify({'ok': True, 'id': novo_id})


@app.route('/api/militares/<int:mid>', methods=['PUT'])
@login_required
def api_editar_militar(mid):
    d = request.get_json(silent=True) or {}
    conn = get_db()
    m = conn.execute('SELECT * FROM militares WHERE id=?', (mid,)).fetchone()
    if not m:
        conn.close()
        return jsonify({'ok': False, 'erro': 'Militar não encontrado.'}), 404

    try:
        conn.execute('''
            UPDATE militares
            SET nome=?, posto=?, identidade=?, email=?, contato=?
            WHERE id=?
        ''', (
            (d.get('nome') or m['nome']).strip(),
            (d.get('posto') or '').strip(),
            (d.get('identidade') or '').strip() or None,
            (d.get('email') or '').strip(),
            (d.get('contato') or '').strip(),
            mid
        ))
        conn.commit()
    except sqlite3.IntegrityError:
        conn.close()
        return jsonify({'ok': False, 'erro': 'Identidade militar já cadastrada.'}), 409
    conn.close()

    registrar_historico('EDITAR_MILITAR', f"Editou militar {m['nome']}", m['nome'])
    return jsonify({'ok': True})


@app.route('/api/militares/<int:mid>', methods=['DELETE'])
@login_required
def api_excluir_militar(mid):
    conn = get_db()
    m = conn.execute('SELECT * FROM militares WHERE id=?', (mid,)).fetchone()
    if not m:
        conn.close()
        return jsonify({'ok': False, 'erro': 'Militar não encontrado.'}), 404
    conn.execute('DELETE FROM militares WHERE id=?', (mid,))
    conn.commit()
    conn.close()
    registrar_historico('EXCLUIR_MILITAR', f"Excluiu militar {m['nome']}", m['nome'])
    return jsonify({'ok': True})


# ============================================================
# API — PEDIDOS
# ============================================================
@app.route('/api/pedidos', methods=['GET'])
@login_required
def api_listar_pedidos():
    militar_id = request.args.get('militar_id')
    conn = get_db()
    if militar_id:
        rows = conn.execute(
            'SELECT * FROM pedidos WHERE militar_id=? ORDER BY criado_em DESC',
            (militar_id,)
        ).fetchall()
    else:
        rows = conn.execute(
            'SELECT * FROM pedidos ORDER BY criado_em DESC'
        ).fetchall()
    conn.close()
    return jsonify({'ok': True, 'pedidos': [dict(r) for r in rows]})


@app.route('/api/pedidos', methods=['POST'])
@login_required
def api_criar_pedido():
    d = request.get_json(silent=True) or {}
    militar_id = d.get('militar_id')
    tipo = (d.get('tipo') or '').strip()
    if not militar_id or not tipo:
        return jsonify({'ok': False, 'erro': 'Militar e tipo são obrigatórios.'}), 400

    conn = get_db()
    existe = conn.execute('SELECT id FROM militares WHERE id=?', (militar_id,)).fetchone()
    if not existe:
        conn.close()
        return jsonify({'ok': False, 'erro': 'Militar não encontrado.'}), 404

    conn.execute('''
        INSERT INTO pedidos
        (militar_id, tipo, data_entrada, via, responsavel, situacao, data_entrega, docs_ok, criado_em)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (
        militar_id, tipo,
        d.get('data_entrada') or None,
        (d.get('via') or '').strip(),
        (d.get('responsavel') or '').strip(),
        d.get('situacao') or 'Em elaboração',
        d.get('data_entrega') or None,
        int(d.get('docs_ok') or 0),
        datetime.now().isoformat()
    ))
    conn.commit()
    novo_id = conn.execute('SELECT last_insert_rowid() AS id').fetchone()['id']
    conn.close()

    registrar_historico('CRIAR_PEDIDO', f'Criou pedido {tipo}', str(militar_id))
    return jsonify({'ok': True, 'id': novo_id})


@app.route('/api/pedidos/<int:pid>', methods=['PUT'])
@login_required
def api_editar_pedido(pid):
    d = request.get_json(silent=True) or {}
    conn = get_db()
    p = conn.execute('SELECT * FROM pedidos WHERE id=?', (pid,)).fetchone()
    if not p:
        conn.close()
        return jsonify({'ok': False, 'erro': 'Pedido não encontrado.'}), 404

    conn.execute('''
        UPDATE pedidos SET
            tipo=?, data_entrada=?, via=?, responsavel=?,
            situacao=?, data_entrega=?, docs_ok=?
        WHERE id=?
    ''', (
        d.get('tipo') or p['tipo'],
        d.get('data_entrada') or p['data_entrada'],
        d.get('via') or p['via'],
        d.get('responsavel') or p['responsavel'],
        d.get('situacao') or p['situacao'],
        d.get('data_entrega') or p['data_entrega'],
        int(d.get('docs_ok', p['docs_ok'])),
        pid
    ))
    conn.commit()
    conn.close()
    registrar_historico('EDITAR_PEDIDO', f"Editou pedido {p['tipo']}", str(pid))
    return jsonify({'ok': True})


@app.route('/api/pedidos/<int:pid>', methods=['DELETE'])
@login_required
def api_excluir_pedido(pid):
    conn = get_db()
    p = conn.execute('SELECT * FROM pedidos WHERE id=?', (pid,)).fetchone()
    if not p:
        conn.close()
        return jsonify({'ok': False, 'erro': 'Pedido não encontrado.'}), 404
    conn.execute('DELETE FROM pedidos WHERE id=?', (pid,))
    conn.commit()
    conn.close()
    registrar_historico('EXCLUIR_PEDIDO', f"Excluiu pedido {p['tipo']}", str(pid))
    return jsonify({'ok': True})


# ============================================================
# API — BAIXA POR COMPANHIA
# ============================================================
@app.route('/api/baixa', methods=['GET'])
@login_required
def api_listar_baixa():
    conn = get_db()
    rows = conn.execute(
        'SELECT id, companhia, militares, b1, b2, ep FROM baixa ORDER BY id'
    ).fetchall()
    conn.close()
    return jsonify({'ok': True, 'baixa': [dict(r) for r in rows]})


@app.route('/api/baixa/<int:bid>', methods=['PUT'])
@login_required
def api_editar_baixa(bid):
    d = request.get_json(silent=True) or {}
    conn = get_db()
    b = conn.execute('SELECT * FROM baixa WHERE id=?', (bid,)).fetchone()
    if not b:
        conn.close()
        return jsonify({'ok': False, 'erro': 'Companhia não encontrada.'}), 404

    conn.execute('''
        UPDATE baixa
        SET militares=?, b1=?, b2=?, ep=?
        WHERE id=?
    ''', (
        int(d.get('militares', b['militares'])),
        int(d.get('b1', b['b1'])),
        int(d.get('b2', b['b2'])),
        int(d.get('ep', b['ep'])),
        bid
    ))
    conn.commit()
    conn.close()
    registrar_historico('EDITAR_BAIXA', f"Atualizou baixa de {b['companhia']}", b['companhia'])
    return jsonify({'ok': True})


# ============================================================
# API — BACKUP (somente gerente)
# ============================================================
@app.route('/api/backup', methods=['GET'])
@gerente_required
def api_backup():
    """
    Devolve o banco SQLite completo como download.
    Somente gerente pode baixar.
    """
    if not os.path.exists(DB_PATH):
        return jsonify({'ok': False, 'erro': 'Banco de dados não encontrado.'}), 404

    registrar_historico('BACKUP', 'Baixou backup do banco de dados', 'controleplus.db')

    try:
        conn = get_db()
        conn.execute('PRAGMA wal_checkpoint(FULL)')
        conn.close()
    except Exception:
        pass

    nome_arquivo = f"controleplus_backup_{datetime.now().strftime('%Y-%m-%d')}.db"

    return send_file(
        DB_PATH,
        as_attachment=True,
        download_name=nome_arquivo,
        mimetype='application/x-sqlite3'
    )


# ============================================================
# INICIALIZAÇÃO
# ============================================================
# Initialize schema on application startup (works with Gunicorn/Render too).
init_db()

if __name__ == '__main__':
    print('=' * 60)
    print('  Controle+ — Sistema da Secretaria')
    print('=' * 60)
    print(f'  Banco:  {DB_PATH}')
    print(f'  Acesse: http://127.0.0.1:5000')
    print('  Login inicial: gerente (senha definida em INITIAL_ADMIN_PASSWORD)')
    print('=' * 60)
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)), debug=False)