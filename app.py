import os
import re
import pdfplumber
import io
import psycopg2
import psycopg2.extras
from flask import Flask, render_template, request, redirect, url_for, flash, session, jsonify
from werkzeug.utils import secure_filename


app = Flask(__name__)
app.secret_key = 'super_secret_key'
app.config['UPLOAD_FOLDER'] = 'uploads'

if not os.path.exists(app.config['UPLOAD_FOLDER']):
    os.makedirs(app.config['UPLOAD_FOLDER'])


# ======================== CONEXIÓN POSTGRESQL ========================
def obtener_conexion():
    return psycopg2.connect(
        host=os.getenv("DB_HOST", "dpg-cv8rv652ng1s73bd3ee0-a.oregon-postgres.render.com"),
        database=os.getenv("DB_NAME", "inventario_db_gg37"),
        user=os.getenv("DB_USER", "inventario_db_gg37_user"),
        password=os.getenv("DB_PASSWORD"),  # 💡 Cambiar a variables de entorno para más seguridad
        port=5432,
        cursor_factory=psycopg2.extras.DictCursor
    )
# ======================== RUTAS ========================

@app.route('/', methods=['GET', 'POST'])
def login():
    usuarios = {
        "admin": "1234",
        "usuario1": "abcd",
        "usuario2": "efgh",
        "usuario3": "ijkl"
    }

    if request.method == 'POST':
        user = request.form['usuario']
        password = request.form['password']
        if user in usuarios and usuarios[user] == password:
            session['usuario'] = user
            return redirect(url_for('solicitudes'))
        else:
            flash('Credenciales incorrectas')
            return redirect(url_for('login'))
    return render_template('login.html')


######################################################################################################################

@app.route('/solicitudes', methods=['GET', 'POST'])
def solicitudes():
    if 'usuario' not in session:
        return redirect(url_for('login'))

    conexion = obtener_conexion()
    with conexion.cursor(cursor_factory=psycopg2.extras.DictCursor) as cursor:
        cursor.execute("SELECT * FROM productos")
        inventario = cursor.fetchall()

    if request.method == 'POST':
        nombre_solicitante = request.form['nombre_solicitante']
        rut_solicitante = request.form['rut_solicitante']
        producto_id = request.form['producto_id']
        cantidad = int(request.form['cantidad'])
        centro_costo = request.form['centro_costo']

        # Validación del formato del RUT
        if not re.match(r'^\d{7,8}-[\dkK]$', rut_solicitante):
            flash('RUT inválido. Debe tener el formato 12345678-9 o 1234567-K')
            return redirect(url_for('solicitudes'))

        with conexion.cursor(cursor_factory=psycopg2.extras.DictCursor) as cursor:
            cursor.execute("SELECT producto_nombre FROM productos WHERE id = %(id)s", {'id': producto_id})
            producto = cursor.fetchone()
            producto_nombre = producto['producto_nombre'] if producto else "Desconocido"

        if 'solicitud_temporal' not in session:
            session['solicitud_temporal'] = {
                'nombre_solicitante': nombre_solicitante,
                'rut_solicitante': rut_solicitante,
                'productos': []
            }

        session['solicitud_temporal']['productos'].append({
            'producto_id': producto_id,
            'producto_nombre': producto_nombre,
            'cantidad': cantidad,
            'centro_costo': centro_costo
        })
        flash(f'Producto {producto_nombre} agregado.')
        session.modified = True

        return redirect(url_for('solicitudes'))

    datos = session.get('solicitud_temporal', {})
    return render_template('solicitudes.html', inventario=inventario, datos=datos)

@app.route('/eliminar_producto/<int:index>')
def eliminar_producto(index):
    if 'solicitud_temporal' not in session:
        return redirect(url_for('solicitudes'))

    productos = session['solicitud_temporal'].get('productos', [])
    if 0 <= index < len(productos):
        producto_eliminado = productos.pop(index)
        flash(f'Producto {producto_eliminado["producto_nombre"]} eliminado.')
        session.modified = True

    return redirect(url_for('solicitudes'))

@app.route('/confirmar_solicitud', methods=['GET', 'POST'])
def confirmar_solicitud():
    if 'usuario' not in session:
        return redirect(url_for('login'))

    datos = session.get('solicitud_temporal')
    if not datos:
        return redirect(url_for('solicitudes'))

    usuario = session['usuario']

    if request.method == 'POST':
        conexion = obtener_conexion()
        with conexion.cursor(cursor_factory=psycopg2.extras.DictCursor) as cursor:
            for item in datos['productos']:
                cursor.execute("SELECT stock_disponible FROM productos WHERE id = %(id)s", {'id': item['producto_id']})
                producto = cursor.fetchone()

                if producto and producto['stock_disponible'] >= item['cantidad']:  # Validación correcta
                    nuevo_stock = producto['stock_disponible'] - item['cantidad']

                    cursor.execute("""
                        UPDATE productos 
                        SET stock_disponible = %(stock_disponible)s 
                        WHERE id = %(id)s
                    """, {'stock_disponible': nuevo_stock, 'id': item['producto_id']})

                    cursor.execute("""
                        INSERT INTO historial_solicitudes 
                        (nombre_solicitante, rut_solicitante, producto_id, producto_nombre, cantidad, centro_costo, usuario)
                        VALUES (%(nombre_solicitante)s, %(rut_solicitante)s, %(producto_id)s, %(producto_nombre)s, %(cantidad)s, %(centro_costo)s, %(usuario)s)
                    """, {
                        'nombre_solicitante': datos['nombre_solicitante'],
                        'rut_solicitante': datos['rut_solicitante'],
                        'producto_id': item['producto_id'],
                        'producto_nombre': item['producto_nombre'],
                        'cantidad': item['cantidad'],
                        'centro_costo': item['centro_costo'],
                        'usuario': usuario
                    })

                    flash(f'Solicitud confirmada por {usuario}: {item["producto_nombre"]} - Nuevo stock: {nuevo_stock}')
                else:
                    flash(f'❌ No hay suficiente stock para {item["producto_nombre"]}. Solicitud cancelada.')

            conexion.commit()
            session.pop('solicitud_temporal', None)

        return redirect(url_for('solicitudes'))

    return render_template('confirmar_solicitud.html', solicitud=datos)

####################################################################################################################
@app.route('/devoluciones', methods=['GET', 'POST'])
def devoluciones():
    if 'usuario' not in session:
        return redirect(url_for('login'))

    conexion = obtener_conexion()
    with conexion.cursor(cursor_factory=psycopg2.extras.DictCursor) as cursor:
        cursor.execute("SELECT * FROM productos")
        inventario = cursor.fetchall()

    if request.method == 'POST':
        nombre_devolutor = request.form['nombre_devolutor']
        rut_devolutor = request.form['rut_devolutor']
        producto_id = request.form['producto_id']
        cantidad = int(request.form['cantidad'])

        if 'devolucion_temporal' not in session:
            session['devolucion_temporal'] = {
                'nombre_devolutor': nombre_devolutor,
                'rut_devolutor': rut_devolutor,
                'productos': []
            }

        producto = next((p for p in inventario if str(p['id']) == producto_id), None)

        if producto:
            session['devolucion_temporal']['productos'].append({
                'producto_id': producto_id,
                'producto_nombre': producto['producto_nombre'],
                'cantidad': cantidad
            })
            flash(f'Producto {producto["producto_nombre"]} agregado para devolución.')
            session.modified = True

        return redirect(url_for('devoluciones'))

    datos = session.get('devolucion_temporal', {})
    return render_template('devoluciones.html', inventario=inventario, datos=datos)

@app.route('/eliminar_producto_devolucion/<int:index>')
def eliminar_producto_devolucion(index):
    if 'devolucion_temporal' not in session:
        return redirect(url_for('devoluciones'))

    productos = session['devolucion_temporal'].get('productos', [])
    if 0 <= index < len(productos):
        producto_eliminado = productos.pop(index)
        flash(f'Producto {producto_eliminado["producto_nombre"]} eliminado.')
        session.modified = True

    return redirect(url_for('devoluciones'))

@app.route('/confirmar_devolucion', methods=['GET', 'POST']) 
def confirmar_devolucion():
    if 'usuario' not in session:
        return redirect(url_for('login'))

    datos = session.get('devolucion_temporal')
    if not datos:
        return redirect(url_for('devoluciones'))

    usuario = session['usuario']  # Guardar quién hizo la devolución

    if request.method == 'POST':
        conexion = obtener_conexion()
        with conexion.cursor(cursor_factory=psycopg2.extras.DictCursor) as cursor:
            for item in datos['productos']:
                cursor.execute("SELECT * FROM productos WHERE id = %(id)s", {'id': item['producto_id']})
                producto = cursor.fetchone()

                if producto:
                    nuevo_stock = producto['stock_disponible'] + item['cantidad']
                    cursor.execute("""
                        UPDATE productos 
                        SET stock_disponible = %(stock_disponible)s 
                        WHERE id = %(id)s
                    """, {'stock_disponible': nuevo_stock, 'id': item['producto_id']})

                    # Guardar en historial_devoluciones con usuario
                    cursor.execute("""
                        INSERT INTO historial_devoluciones 
                        (nombre_devolutor, rut_devolutor, producto_id, producto_nombre, cantidad, usuario)
                        VALUES (%(nombre_devolutor)s, %(rut_devolutor)s, %(producto_id)s, %(producto_nombre)s, %(cantidad)s, %(usuario)s)
                    """, {
                        'nombre_devolutor': datos['nombre_devolutor'],
                        'rut_devolutor': datos['rut_devolutor'],
                        'producto_id': item['producto_id'],
                        'producto_nombre': item['producto_nombre'],
                        'cantidad': item['cantidad'],
                        'usuario': usuario
                    })

                    flash(f'Devolución confirmada por {usuario}: {producto["producto_nombre"]} - Nuevo stock: {nuevo_stock}')

            conexion.commit()
            session.pop('devolucion_temporal', None)

        return redirect(url_for('devoluciones'))

    return render_template('confirmar_devolucion.html', devolucion=datos)

####################################################################################################################
@app.route('/entradas', methods=['GET', 'POST'])
def entradas():
    if 'usuario' not in session:
        return redirect(url_for('login'))

    conexion = obtener_conexion()
    with conexion.cursor(cursor_factory=psycopg2.extras.DictCursor) as cursor:
        cursor.execute("SELECT id, producto_nombre, stock_disponible, unidad, categoria FROM productos")
        inventario = cursor.fetchall()

    if request.method == 'POST':
        usuario = session['usuario']  # Guardar quién hizo la entrada
        producto_nombre = request.form.get('producto_nombre', '').strip()
        cantidad = int(request.form.get('cantidad', 0))
        categoria = request.form.get('categoria', 'General').strip()  # Nueva categoría agregada
        unidad = request.form.get('unidad', '')
        stock_critico = int(request.form.get('stock_critico', 0))
        numero_orden = request.form.get('numero_orden', '')
        numero_guia = request.form.get('numero_guia', '')
        numero_factura = request.form.get('numero_factura', '')

        with conexion.cursor(cursor_factory=psycopg2.extras.DictCursor) as cursor:
            # Buscar si el producto ya existe en la base de datos
            cursor.execute("SELECT id, stock_disponible, categoria FROM productos WHERE producto_nombre = %(nombre)s", {'nombre': producto_nombre})
            producto = cursor.fetchone()

            if producto:
                # Si el producto ya existe, actualizar su stock pero NO cambiar su categoría
                nuevo_stock = producto['stock_disponible'] + cantidad
                cursor.execute("""
                    UPDATE productos 
                    SET stock_disponible = %(stock_disponible)s 
                    WHERE id = %(id)s
                """, {'stock_disponible': nuevo_stock, 'id': producto['id']})
                producto_id = producto['id']
                categoria = producto['categoria']  # Mantener la categoría del producto existente
            else:
                # Si el producto no existe, insertarlo en la base de datos con la categoría seleccionada
                cursor.execute("""
                    INSERT INTO productos (producto_nombre, unidad, stock_disponible, stock_critico, categoria) 
                    VALUES (%(nombre)s, %(unidad)s, %(stock_disponible)s, %(stock_critico)s, %(categoria)s) 
                    RETURNING id
                """, {
                    'nombre': producto_nombre,
                    'unidad': unidad,
                    'stock_disponible': cantidad,
                    'stock_critico': stock_critico,
                    'categoria': categoria
                })
                producto_id = cursor.fetchone()['id']  # Obtener el ID del producto insertado

            # Registrar la entrada en el historial de entradas
            cursor.execute("""
                INSERT INTO historial_entradas 
                (numero_orden, numero_guia, numero_factura, producto_id, producto_nombre, cantidad, unidad, categoria, usuario) 
                VALUES (%(numero_orden)s, %(numero_guia)s, %(numero_factura)s, %(producto_id)s, %(producto_nombre)s, %(cantidad)s, %(unidad)s, %(categoria)s, %(usuario)s)
            """, {
                'numero_orden': numero_orden,
                'numero_guia': numero_guia,
                'numero_factura': numero_factura,
                'producto_id': producto_id,
                'producto_nombre': producto_nombre,
                'cantidad': cantidad,
                'unidad': unidad,
                'categoria': categoria,
                'usuario': usuario
            })

            flash(f'✅ Entrada registrada por {usuario}: {producto_nombre} - Cantidad: {cantidad} - Categoría: {categoria}')
            conexion.commit()

        return redirect(url_for('entradas'))

    return render_template('entradas.html', inventario=inventario)

####################################################################################################################
@app.route('/inventario')
def ver_inventario():
    if 'usuario' not in session:
        return redirect(url_for('login'))

    conexion = obtener_conexion()
    with conexion.cursor(cursor_factory=psycopg2.extras.DictCursor) as cursor:
        cursor.execute("SELECT * FROM productos")
        inventario = cursor.fetchall()

    return render_template('inventario.html', inventario=inventario)
########################################################################################################################
# ======================== RUTA DISTRIBUCIÓN ========================
@app.route('/distribucion', methods=['GET', 'POST'])
def distribucion():
    if 'usuario' not in session:
        return redirect(url_for('login'))

    conexion = obtener_conexion()
    with conexion.cursor(cursor_factory=psycopg2.extras.DictCursor) as cursor:
        cursor.execute("SELECT id, producto_nombre, stock_disponible, unidad, categoria FROM productos")
        inventario = cursor.fetchall()

    if request.method == 'POST':
        usuario = session['usuario']  # Guardar quién está registrando la distribución
        numero_guia = request.form.get("numero_guia", "").strip()
        destino = request.form.get("destino", "").strip()
        producto_id = request.form.get("producto_id", "").strip()
        cantidad = int(request.form.get("cantidad", 0))

        # Validación de datos
        if not numero_guia or not destino or not producto_id or cantidad <= 0:
            flash("❌ Todos los campos son obligatorios y la cantidad debe ser mayor a 0.", "error")
            return redirect(url_for('distribucion'))

        with conexion.cursor(cursor_factory=psycopg2.extras.DictCursor) as cursor:
            # Verificar si el producto existe y tiene stock suficiente
            cursor.execute("SELECT stock_disponible FROM productos WHERE id = %(id)s", {'id': producto_id})
            producto = cursor.fetchone()

            if producto and producto['stock_disponible'] >= cantidad:
                nuevo_stock = producto['stock_disponible'] - cantidad

                # Actualizar el stock en la base de datos
                cursor.execute("""
                    UPDATE productos 
                    SET stock_disponible = %(stock_disponible)s 
                    WHERE id = %(id)s
                """, {'stock_disponible': nuevo_stock, 'id': producto_id})

                # Insertar en historial de distribución
                cursor.execute("""
                    INSERT INTO historial_distribucion (usuario, producto_id, cantidad, destino, numero_guia) 
                    VALUES (%(usuario)s, %(producto_id)s, %(cantidad)s, %(destino)s, %(numero_guia)s)
                """, {
                    'usuario': usuario,
                    'producto_id': producto_id,
                    'cantidad': cantidad,
                    'destino': destino,
                    'numero_guia': numero_guia
                })

                conexion.commit()
                flash(f"✅ Distribución registrada: Producto {producto_id}, Cantidad: {cantidad}", "success")
            else:
                flash("❌ No hay suficiente stock para realizar la distribución.", "error")

        return redirect(url_for('distribucion'))

    return render_template('distribucion.html', inventario=inventario)


# ======================== GUARDAR DISTRIBUCIÓN EN POSTGRESQL ========================
@app.route('/guardar_distribucion', methods=['POST'])
def guardar_distribucion():
    datos = request.get_json()
    usuario = session.get("usuario", "Desconocido")
    productos = datos.get("productos", [])
    numero_guia = datos.get("numero_guia", "").strip()
    destino = datos.get("destino", "").strip()

    if not productos:
        return jsonify({"success": False, "error": "❌ No hay productos para guardar."})

    if not numero_guia or not destino:
        return jsonify({"success": False, "error": "❌ Debes completar todos los campos obligatorios."})

    conexion = obtener_conexion()
    with conexion.cursor(cursor_factory=psycopg2.extras.DictCursor) as cursor:
        for producto in productos:
            cursor.execute("SELECT id, stock_disponible FROM productos WHERE producto_nombre = %(nombre)s", {'nombre': producto["nombre"]})
            producto_en_inventario = cursor.fetchone()

            if producto_en_inventario and producto_en_inventario["stock_disponible"] >= producto["cantidad"]:
                nuevo_stock = producto_en_inventario["stock_disponible"] - producto["cantidad"]

                # Actualizar el stock disponible en la tabla productos
                cursor.execute("""
                    UPDATE productos 
                    SET stock_disponible = %(stock_disponible)s 
                    WHERE id = %(id)s
                """, {'stock_disponible': nuevo_stock, 'id': producto_en_inventario["id"]})

                # Insertar la distribución en el historial
                cursor.execute("""
                    INSERT INTO historial_distribucion (usuario, producto_id, cantidad, destino, numero_guia) 
                    VALUES (%(usuario)s, %(producto_id)s, %(cantidad)s, %(destino)s, %(numero_guia)s)
                """, {
                    'usuario': usuario,
                    'producto_id': producto_en_inventario["id"],
                    'cantidad': producto["cantidad"],
                    'destino': destino,
                    'numero_guia': numero_guia
                })

            else:
                return jsonify({"success": False, "error": f"❌ No hay suficiente stock de {producto['nombre']}."})

        conexion.commit()

    return jsonify({"success": True, "message": "✅ Distribución guardada exitosamente en PostgreSQL y stock actualizado."})


# ======================== VERIFICAR INVENTARIO ========================
@app.route('/verificar_inventario', methods=['POST'])
def verificar_inventario():
    datos = request.get_json()
    nombre_producto = datos.get("nombre", "").strip()

    conexion = obtener_conexion()
    with conexion.cursor(cursor_factory=psycopg2.extras.DictCursor) as cursor:
        cursor.execute("SELECT stock_disponible FROM productos WHERE producto_nombre = %(nombre)s", {'nombre': nombre_producto})
        producto = cursor.fetchone()

    if producto:
        return jsonify({"existe": True, "stock": producto["stock_disponible"]})
    else:
        return jsonify({"existe": False, "stock": 0})

#######################################################################################################################
@app.route('/logout')
def logout():
    session.pop('usuario', None)
    return redirect(url_for('login'))


if __name__ == '__main__':
    port = int(os.environ.get("PORT", 10000))  # Toma el puerto de la variable de entorno
    app.run(host="0.0.0.0", port=port)