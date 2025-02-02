from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
import bcrypt
import mysql.connector

app = Flask(__name__, static_folder='static')
app.secret_key = 'supersecretkey'  # Chave secreta para a sessão

areas = {
    1: {"nome": "Oficina", "nivel_acesso": 1},
    2: {"nome": "Laboratório", "nivel_acesso": 2},
    3: {"nome": "Sala de Controle", "nivel_acesso": 3},
}

# Configuração do banco de dados
DATABASE_CONFIG = {
    'host': 'localhost',
    'user': 'root',
    'password': 'Guigui#1',
    'database': 'projeto'
}

def get_db_connection():
    try:
        conn = mysql.connector.connect(**DATABASE_CONFIG)
        return conn
    except mysql.connector.Error as err:
        print(f"Erro ao conectar ao banco de dados: {err}")
        return None

@app.route('/')
def index():
    if 'usuario_id' in session:
        return redirect(url_for('home'))
    return redirect(url_for('login'))

@app.route('/home')
def home():
    if 'usuario_id' not in session:
        return redirect(url_for('login'))
    return render_template('home.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        nome = request.form.get('username')
        senha = request.form.get('password')
        area_id = request.form.get('local')

        conn = get_db_connection()
        if conn is None:
            flash("Erro ao conectar ao banco de dados")
            return redirect(url_for('login'))

        cursor = conn.cursor(dictionary=True)
        cursor.execute('SELECT * FROM usuarios WHERE nome = %s', (nome,))
        usuario = cursor.fetchone()

        if usuario and bcrypt.checkpw(senha.encode('utf-8'), usuario['senha_hash'].encode('utf-8')):
            session['usuario_id'] = usuario['id']
            session['nivel_acesso'] = usuario['nivel_acesso']
            
            if area_id == 'sala_de_controle' and usuario['nivel_acesso'] != 3:
                cursor.execute('INSERT INTO logs (usuario, area, status) VALUES (%s, %s, %s)', (nome, 'Sala de Controle', 'Acesso negado'))
                conn.commit()
                conn.close()
                flash("Acesso negado. Você não tem permissão para acessar a Sala de Controle.")
                return redirect(url_for('login'))
            elif area_id == 'laboratorio' and usuario['nivel_acesso'] not in [2, 3]:
                cursor.execute('INSERT INTO logs (usuario, area, status) VALUES (%s, %s, %s)', (nome, 'Laboratório', 'Acesso negado'))
                conn.commit()
                conn.close()
                flash("Acesso negado. Você não tem permissão para acessar o Laboratório.")
                return redirect(url_for('login'))
            elif area_id == 'oficina' and usuario['nivel_acesso'] not in [1, 3]:
                cursor.execute('INSERT INTO logs (usuario, area, status) VALUES (%s, %s, %s)', (nome, 'Oficina', 'Acesso negado'))
                conn.commit()
                conn.close()
                flash("Acesso negado. Você não tem permissão para acessar a Oficina.")
                return redirect(url_for('login'))
            
            cursor.execute('INSERT INTO logs (usuario, area, status) VALUES (%s, %s, %s)', (nome, area_id, 'Acesso permitido'))
            conn.commit()
            conn.close()
            return redirect(url_for('menu'))
        else:
            cursor.execute('INSERT INTO logs (usuario, area, status) VALUES (%s, %s, %s)', (nome, area_id, 'Acesso negado'))
            conn.commit()
            conn.close()
            flash("Nome de usuário ou senha incorretos")
            return redirect(url_for('login'))
    return render_template('home.html', areas=areas)

@app.route('/menu')
def menu():
    if 'usuario_id' not in session:
        return redirect(url_for('login'))
    return render_template('menu.html')

@app.route('/dashboard')
def dashboard():
    if 'usuario_id' not in session:
        return redirect(url_for('login'))

    conn = get_db_connection()
    if conn is None:
        return "Erro ao conectar ao banco de dados"

    cursor = conn.cursor(dictionary=True)
    
    # Obter dados de equipamentos
    cursor.execute('SELECT nome, quantidade FROM equipamentos')
    equipamentos = cursor.fetchall()
    
    # Obter dados de veículos
    cursor.execute('''
        SELECT status, COUNT(*) as count 
        FROM veiculos 
        GROUP BY status
    ''')
    veiculos = cursor.fetchall()
    
    # Obter dados de dispositivos de segurança
    cursor.execute('''
        SELECT status, COUNT(*) as count 
        FROM dispositivos_seg 
        GROUP BY status
    ''')
    dispositivos_seg = cursor.fetchall()
    
    conn.close()

    # Processar dados de equipamentos
    equipamentos_labels = [item['nome'] for item in equipamentos]
    equipamentos_data = [item['quantidade'] for item in equipamentos]

    # Processar dados de veículos
    veiculos_labels = [v['status'] for v in veiculos]
    veiculos_data = [v['count'] for v in veiculos]

    # Processar dados de dispositivos
    dispositivos_labels = [d['status'] for d in dispositivos_seg]
    dispositivos_data = [d['count'] for d in dispositivos_seg]

    return render_template('dashboard.html', 
                         equipamentos_labels=equipamentos_labels,
                         equipamentos_data=equipamentos_data,
                         veiculos_labels=veiculos_labels,
                         veiculos_data=veiculos_data,
                         dispositivos_labels=dispositivos_labels,
                         dispositivos_data=dispositivos_data)

@app.route('/inventario')
def inventario():
    if 'usuario_id' not in session:
        return redirect(url_for('login'))

    conn = get_db_connection()
    if conn is None:
        flash("Erro ao conectar ao banco de dados")
        return redirect(url_for('menu'))

    cursor = conn.cursor(dictionary=True)
    
    cursor.execute('SELECT * FROM equipamentos')
    equipamentos = cursor.fetchall()
    
    cursor.execute('SELECT * FROM veiculos')
    veiculos = cursor.fetchall()
    
    cursor.execute('SELECT * FROM dispositivos_seg')
    dispositivos_seg = cursor.fetchall()
    
    cursor.close()
    conn.close()
    
    return render_template('inventario.html', equipamentos=equipamentos, veiculos=veiculos, dispositivos_seg=dispositivos_seg)

@app.route('/adicionar_item/<categoria>', methods=['GET', 'POST'])
def adicionar_item(categoria):
    if 'usuario_id' not in session:
        return redirect(url_for('login'))

    if session.get('nivel_acesso') not in [2, 3]:
        flash("Acesso negado. Você não tem permissão para adicionar itens.")
        return redirect(url_for('inventario'))

    if request.method == 'POST':
        conn = get_db_connection()
        if conn is None:
            flash("Erro ao conectar ao banco de dados")
            return redirect(url_for('inventario'))

        cursor = conn.cursor()
        
        if categoria == 'equipamentos':
            nome = request.form.get('nome')
            descricao = request.form.get('descricao')
            quantidade = request.form.get('quantidade')
            cursor.execute('INSERT INTO equipamentos (nome, descricao, quantidade) VALUES (%s, %s, %s)',
                           (nome, descricao, quantidade))
        
        elif categoria == 'veiculos':
            modelo = request.form.get('modelo')
            placa = request.form.get('placa')
            status = request.form.get('status')
            cursor.execute('INSERT INTO veiculos (modelo, placa, status) VALUES (%s, %s, %s)',
                           (modelo, placa, status))
        
        elif categoria == 'dispositivos_seg':
            nome = request.form.get('nome')
            localizacao = request.form.get('localizacao')
            status = request.form.get('status')
            cursor.execute('INSERT INTO dispositivos_seg (nome, localizacao, status) VALUES (%s, %s, %s)',
                           (nome, localizacao, status))
        
        conn.commit()
        cursor.close()
        conn.close()
        
        flash("Produto cadastrado com sucesso")
        return redirect(url_for('inventario'))
    
    return render_template('adicionar_item.html', categoria=categoria)

@app.route('/editar_item/<categoria>/<int:id_item>', methods=['GET', 'POST'])
def editar_item(categoria, id_item):
    if 'usuario_id' not in session:
        return redirect(url_for('login'))

    if session.get('nivel_acesso') not in [2, 3]:
        flash("Acesso negado. Você não tem permissão para editar itens.")
        return redirect(url_for('inventario'))

    if request.method == 'POST':
        conn = get_db_connection()
        if conn is None:
            flash("Erro ao conectar ao banco de dados")
            return redirect(url_for('inventario'))

        cursor = conn.cursor()
        
        if categoria == 'equipamentos':
            nome = request.form.get('nome')
            descricao = request.form.get('descricao')
            quantidade = request.form.get('quantidade')
            cursor.execute('UPDATE equipamentos SET nome = %s, descricao = %s, quantidade = %s WHERE id = %s',
                         (nome, descricao, quantidade, id_item))
            
        elif categoria == 'veiculos':
            modelo = request.form.get('modelo')
            placa = request.form.get('placa')
            status = request.form.get('status')
            cursor.execute('UPDATE veiculos SET modelo = %s, placa = %s, status = %s WHERE id = %s',
                         (modelo, placa, status, id_item))
            
        elif categoria == 'dispositivos_seg':
            nome = request.form.get('nome')
            localizacao = request.form.get('localizacao')
            status = request.form.get('status')
            cursor.execute('UPDATE dispositivos_seg SET nome = %s, localizacao = %s, status = %s WHERE id = %s',
                         (nome, localizacao, status, id_item))
        
        conn.commit()
        conn.close()
        flash("Item atualizado com sucesso")
        return redirect(url_for('inventario'))

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    try:
        if categoria == 'equipamentos':
            cursor.execute('SELECT * FROM equipamentos WHERE id = %s', (id_item,))
        elif categoria == 'veiculos':
            cursor.execute('SELECT * FROM veiculos WHERE id = %s', (id_item,))
        elif categoria == 'dispositivos_seg':
            cursor.execute('SELECT * FROM dispositivos_seg WHERE id = %s', (id_item,))
        
        item = cursor.fetchone()
        if item is None:
            flash("Item não encontrado")
            return redirect(url_for('inventario'))
    except mysql.connector.Error as err:
        flash(f"Erro ao buscar item: {err}")
        return redirect(url_for('inventario'))
    finally:
        cursor.close()
        conn.close()
    
    return render_template('editar_item.html', categoria=categoria, item=item)

@app.route('/excluir_item/<categoria>/<int:id_item>', methods=['POST'])
def excluir_item(categoria, id_item):
    if 'usuario_id' not in session:
        return redirect(url_for('login'))

    if session.get('nivel_acesso') not in [2, 3]:
        flash("Acesso negado. Você não tem permissão para excluir itens.")
        return redirect(url_for('inventario'))

    conn = get_db_connection()
    if conn is None:
        return jsonify({'error': 'Erro ao conectar ao banco de dados'}), 500

    try:
        cursor = conn.cursor()
        quantity = int(request.args.get('quantity', 1))
        
        if categoria == 'equipamentos':
            cursor.execute('SELECT quantidade FROM equipamentos WHERE id = %s', (id_item,))
            current_quantity = cursor.fetchone()[0]
            new_quantity = current_quantity - quantity
            if new_quantity <= 0:
                cursor.execute('DELETE FROM equipamentos WHERE id = %s', (id_item,))
            else:
                cursor.execute('UPDATE equipamentos SET quantidade = %s WHERE id = %s', (new_quantity, id_item))
        elif categoria == 'veiculos':
            cursor.execute('DELETE FROM veiculos WHERE id = %s', (id_item,))
        elif categoria == 'dispositivos_seg':
            cursor.execute('DELETE FROM dispositivos_seg WHERE id = %s', (id_item,))
        
        conn.commit()
        return jsonify({'success': True}), 200
        
    except mysql.connector.Error as err:
        return jsonify({'error': str(err)}), 500
        
    finally:
        cursor.close()
        conn.close()

@app.route('/usuarios', methods=['GET'])
def usuarios():
    if 'usuario_id' not in session:
        return redirect(url_for('login'))

    conn = get_db_connection()
    if conn is None:
        return "Erro ao conectar ao banco de dados"

    cursor = conn.cursor(dictionary=True)
    cursor.execute('SELECT * FROM usuarios')
    usuarios = cursor.fetchall()
    conn.close()

    return render_template('listar_usuarios.html', usuarios=usuarios)

@app.route('/adicionar_usuario', methods=['GET', 'POST'])
def adicionar_usuario():
    if 'usuario_id' not in session:
        return redirect(url_for('login'))

    if request.method == 'POST':
        nome = request.form['nome']
        senha = request.form['senha']
        nivel_acesso = request.form['nivel_acesso']
        senha_hash = bcrypt.hashpw(senha.encode('utf-8'), bcrypt.gensalt())

        conn = get_db_connection()
        if conn is None:
            flash("Erro ao conectar ao banco de dados")
            return redirect(url_for('usuarios'))

        cursor = conn.cursor()
        cursor.execute('INSERT INTO usuarios (nome, senha_hash, nivel_acesso) VALUES (%s, %s, %s)', (nome, senha_hash, nivel_acesso))
        conn.commit()
        conn.close()

        flash("Usuário adicionado com sucesso.")
        return redirect(url_for('usuarios'))
    return render_template('adicionar_usuario.html')

@app.route('/editar_usuario/<int:id_usuario>', methods=['GET', 'POST'])
def editar_usuario(id_usuario):
    if 'usuario_id' not in session:
        return redirect(url_for('login'))

    if request.method == 'POST':
        nome = request.form['nome']
        senha = request.form['senha']
        nivel_acesso = request.form['nivel_acesso']
        senha_hash = bcrypt.hashpw(senha.encode('utf-8'), bcrypt.gensalt())

        conn = get_db_connection()
        if conn is None:
            flash("Erro ao conectar ao banco de dados")
            return redirect(url_for('usuarios'))

        cursor = conn.cursor()
        cursor.execute('UPDATE usuarios SET nome = %s, senha_hash = %s, nivel_acesso = %s WHERE id = %s', (nome, senha_hash, nivel_acesso, id_usuario))
        conn.commit()
        conn.close()

        flash("Usuário editado com sucesso.")
        return redirect(url_for('usuarios'))
    
    conn = get_db_connection()
    if conn is None:
        return "Erro ao conectar ao banco de dados"
    
    cursor = conn.cursor(dictionary=True)
    cursor.execute('SELECT * FROM usuarios WHERE id = %s', (id_usuario,))
    usuario = cursor.fetchone()
    conn.close()
    
    return render_template('editar_usuario.html', usuario=usuario)

@app.route('/excluir_usuario/<int:id_usuario>', methods=['POST'])
def excluir_usuario(id_usuario):
    if 'usuario_id' not in session:
        return redirect(url_for('login'))

    conn = get_db_connection()
    if conn is None:
        flash("Erro ao conectar ao banco de dados")
        return redirect(url_for('usuarios'))

    cursor = conn.cursor()
    cursor.execute('DELETE FROM usuarios WHERE id = %s', (id_usuario,))
    conn.commit()
    conn.close()

    flash("Usuário excluído com sucesso.")
    return redirect(url_for('usuarios'))

@app.route('/logout')
def logout():
    session.pop('usuario_id', None)
    return redirect(url_for('login'))

@app.route('/logs')
def logs():
    if 'usuario_id' not in session:
        return redirect(url_for('login'))
    if session.get('nivel_acesso') != 3:
        flash("Acesso negado. Você não tem permissão para acessar esta área.")
        return redirect(url_for('menu'))

    conn = get_db_connection()
    if conn is None:
        flash("Erro ao conectar ao banco de dados")
        return redirect(url_for('menu'))

    cursor = conn.cursor(dictionary=True)
    cursor.execute('SELECT * FROM logs')
    logs = cursor.fetchall()
    conn.close()

    return render_template('logs.html', logs=logs)

if __name__ == '__main__':
    app.run(debug=True)