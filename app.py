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

# Definir usuarios y sus contraseñas
usuarios = {
    "Cesar": {"password": "ADMINJCM", "rol": "admin"},
    "Gonzalo": {"password": "ADMINJCM", "rol": "admin"},
    "Mauricio": {"password": "MAURICIOJCM", "rol": "admin"},
    "Mariela": {"password": "MARIELAJCM", "rol": "admin"},
    "admin": {"password": "1234", "rol": "admin"},
    "Nicolas": {"password": "NICOLASJCM", "rol": "admin"},
    "Jefe terreno": {"password": "JEFETERRENOJCM", "rol": "inventario"}  # Usuario restringido
}

@app.route('/', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        user = request.form['usuario']
        password = request.form['password']

        if user in usuarios and usuarios[user]["password"] == password:
            session['usuario'] = user
            session['rol'] = usuarios[user]["rol"]  # Guardar el rol en sesión

            if session['rol'] == 'inventario':
                return redirect(url_for('ver_inventario'))  # Redirigir al inventario
            else:
                return redirect(url_for('solicitudes'))  # Redirigir a la página principal

        flash('Credenciales incorrectas', 'danger')
        return redirect(url_for('login'))
    

    return render_template('login.html')
######################################################################################################################

@app.route('/solicitudes', methods=['GET', 'POST'])
def solicitudes():
    if 'usuario' not in session or session.get('rol') != 'admin':
        flash("Acceso restringido", "danger")
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
            cursor.execute("SELECT producto_nombre, estado FROM productos WHERE id = %(id)s", {'id': producto_id})
            producto = cursor.fetchone()
            producto_nombre = producto['producto_nombre'] if producto else "Desconocido"
            estado_producto = producto['estado'] if producto else "Desconocido"
                # ⛔ Validación para bloquear productos no operativos
            if estado_producto.lower().strip() != 'operativo':
               flash(f'❌ El producto "{producto_nombre}" no se puede agregar porque no está operativo.')
               return redirect(url_for('solicitudes'))

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
    alertas_stock_critico = []  # Para almacenar productos con stock crítico


    if request.method == 'POST':
        conexion = obtener_conexion()
        with conexion.cursor(cursor_factory=psycopg2.extras.DictCursor) as cursor:
            for item in datos['productos']:
                cursor.execute("SELECT stock_disponible, stock_critico FROM productos WHERE id = %(id)s", {'id': item['producto_id']})
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
                                        # Verificar si el stock es menor o igual al stock crítico
                    if nuevo_stock <= producto['stock_critico']:
                        alertas_stock_critico.append(f'⚠️ ¡ATENCIÓN! {item["producto_nombre"]} ha alcanzado el stock crítico ({nuevo_stock} unidades). Favor realizar pedido.')

                else:
                    flash(f'❌ No hay suficiente stock para {item["producto_nombre"]}. Solicitud cancelada.')

            conexion.commit()
            session.pop('solicitud_temporal', None)
            

        return render_template('confirmar_solicitud.html', solicitud=datos, alertas_stock_critico=alertas_stock_critico)
    return render_template('confirmar_solicitud.html', solicitud=datos)

####################################################################################################################
@app.route('/devoluciones', methods=['GET', 'POST'])
def devoluciones():
    if 'usuario' not in session or session.get('rol') != 'admin':
        flash("Acceso restringido", "danger")
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
    if 'usuario' not in session or session.get('rol') != 'admin':
        flash("Acceso restringido", "danger")
        return redirect(url_for('login'))

    # Obtener inventario
    conexion = obtener_conexion()
    with conexion.cursor(cursor_factory=psycopg2.extras.DictCursor) as cursor:
        cursor.execute("SELECT id, producto_nombre, stock_disponible, unidad, categoria FROM productos")
        inventario = cursor.fetchall()

    # Inicializar datos temporales en la sesión
    if 'entrada_temporal' not in session:
        session['entrada_temporal'] = {
            'productos': [],
            'numero_orden': '',
            'numero_guia': '',
            'numero_factura': ''
        }

    if request.method == 'POST':
        if 'agregar_producto' in request.form:
            # Guardar los datos de la orden en la sesión
            session['entrada_temporal']['numero_orden'] = request.form.get('numero_orden', '').strip()
            session['entrada_temporal']['numero_guia'] = request.form.get('numero_guia', '').strip()
            session['entrada_temporal']['numero_factura'] = request.form.get('numero_factura', '').strip()

            # Capturar datos del producto
            producto_nombre = request.form.get('producto_nombre', '').strip()
            cantidad = int(request.form.get('cantidad', 0))
            unidad = request.form.get('unidad', '').strip()
            categoria = request.form.get('categoria', 'General').strip()

            # Validación mínima
            if not producto_nombre or cantidad <= 0:
                flash('⚠️ Error: Debes ingresar un nombre de producto y cantidad válida.', 'error')
                return redirect(url_for('entradas'))

            # Buscar coincidencia por nombre exacto
            with conexion.cursor(cursor_factory=psycopg2.extras.DictCursor) as cursor:
                cursor.execute("""
                    SELECT id, stock_disponible FROM productos
                    WHERE LOWER(TRIM(producto_nombre)) = LOWER(TRIM(%s))
                """, (producto_nombre,))
                producto_existente = cursor.fetchone()

            if producto_existente:
                # Producto existente → solo sumar stock después
                session['entrada_temporal']['productos'].append({
                    'producto_id': producto_existente['id'],
                    'producto_nombre': producto_nombre,
                    'cantidad': cantidad,
                    'unidad': unidad,
                    'categoria': categoria,
                    'nuevo': False
                })
            else:
                # Producto nuevo → se agregará al inventario al confirmar
                session['entrada_temporal']['productos'].append({
                    'producto_id': None,
                    'producto_nombre': producto_nombre,
                    'cantidad': cantidad,
                    'unidad': unidad,
                    'categoria': categoria,
                    'nuevo': True
                })

            session.modified = True
            flash(f'✅ Producto agregado: {producto_nombre} - Cantidad: {cantidad}', 'success')
            return redirect(url_for('entradas'))

        elif 'eliminar_producto' in request.form:
            # Eliminar un producto de la lista temporal
            index = int(request.form.get('eliminar_producto'))
            if 0 <= index < len(session['entrada_temporal']['productos']):
                eliminado = session['entrada_temporal']['productos'].pop(index)
                session.modified = True
                flash(f'🗑 Producto eliminado: {eliminado["producto_nombre"]}', 'warning')
            return redirect(url_for('entradas'))

        elif 'confirmar_entrada' in request.form:
            try:
                usuario = session.get('usuario', 'Desconocido')
                numero_orden = session['entrada_temporal'].get('numero_orden') or None
                numero_guia = session['entrada_temporal'].get('numero_guia') or None
                numero_factura = session['entrada_temporal'].get('numero_factura') or None

                if not session['entrada_temporal'].get('productos'):
                    flash('⚠️ Error: No hay productos para registrar.', 'error')
                    return redirect(url_for('entradas'))

                conexion = obtener_conexion()
                with conexion.cursor(cursor_factory=psycopg2.extras.DictCursor) as cursor:
                    for producto in session['entrada_temporal']['productos']:
                        producto_nombre = producto['producto_nombre']
                        cantidad = producto['cantidad']
                        unidad = producto['unidad']
                        categoria = producto['categoria']
                        producto_id = producto.get('producto_id')

                        if producto['nuevo']:
                            # Insertar nuevo producto en la base de datos
                            cursor.execute("""
                                INSERT INTO productos (producto_nombre, unidad, stock_disponible, categoria) 
                                VALUES (%s, %s, %s, %s) RETURNING id
                            """, (producto_nombre, unidad, cantidad, categoria))
                            nuevo_producto = cursor.fetchone()
                            
                            if nuevo_producto:
                                producto_id = nuevo_producto['id']
                            else:
                                flash(f'❌ Error al insertar el producto "{producto_nombre}".', 'error')
                                return redirect(url_for('entradas'))
                        else:
                            # Actualizar stock del producto existente
                            cursor.execute("""
                                UPDATE productos 
                                SET stock_disponible = stock_disponible + %s 
                                WHERE id = %s
                            """, (cantidad, producto_id))

                        # Registrar en historial de entradas
                        cursor.execute("""
                            INSERT INTO historial_entradas 
                            (numero_orden, numero_guia, numero_factura, producto_id, producto_nombre, cantidad, unidad, categoria, usuario) 
                            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                        """, (numero_orden, numero_guia, numero_factura, producto_id, producto_nombre, cantidad, unidad, categoria, usuario))

                # Guardar cambios en la base de datos
                conexion.commit()
                flash('✅ Entrada confirmada y registrada exitosamente.', 'success')

                # Limpiar datos de la sesión después de registrar
                session.pop('entrada_temporal', None)
                session.modified = True

                return redirect(url_for('entradas'))

            except Exception as e:
                flash(f"❌ Error al confirmar entrada: {str(e)}", "error")
                return redirect(url_for('entradas'))

    # Renderizar la plantilla al final si es una solicitud GET
    return render_template(
        'entradas.html', 
        inventario=inventario, 
        productos_temporales=session['entrada_temporal']['productos'],
        datos=session['entrada_temporal']
    )


####################################################################################################################
@app.route('/inventario')
def ver_inventario():
    if 'usuario' not in session or session.get('rol') not in ['admin', 'inventario']:
        flash("No tienes acceso a esta página", "danger")
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
    if 'usuario' not in session or session.get('rol') != 'admin':
        flash("Acceso restringido", "danger")
        return redirect(url_for('login'))

    conexion = obtener_conexion()
    with conexion.cursor(cursor_factory=psycopg2.extras.DictCursor) as cursor:
        cursor.execute("SELECT producto_nombre, stock_disponible, unidad, categoria FROM productos")
        inventario = cursor.fetchall()

    if 'distribucion_temporal' not in session:
        session['distribucion_temporal'] = {
            'productos': [],
            'numero_guia': '',
            'destino': ''
        }

    if request.method == 'POST':
        if 'agregar_producto' in request.form:
            session['distribucion_temporal']['numero_guia'] = request.form.get("numero_guia", "").strip()
            session['distribucion_temporal']['destino'] = request.form.get("destino", "").strip()

            producto_nombre = request.form.get("producto_nombre", "").strip()
            cantidad = request.form.get("cantidad", "").strip()

            if not producto_nombre or not cantidad.isdigit() or int(cantidad) <= 0:
                flash('⚠️ Error: Debes ingresar un nombre de producto y cantidad válida.', 'error')
                return redirect(url_for('distribucion'))

            cantidad = int(cantidad)

            with conexion.cursor(cursor_factory=psycopg2.extras.DictCursor) as cursor:
                cursor.execute("SELECT stock_disponible FROM productos WHERE LOWER(TRIM(producto_nombre)) = LOWER(TRIM(%s))", (producto_nombre,))
                producto_existente = cursor.fetchone()

                if not producto_existente:
                    flash(f'⚠️ Error: El producto "{producto_nombre}" no existe en el inventario.', 'error')
                    return redirect(url_for('distribucion'))
                
                if cantidad > producto_existente['stock_disponible']:
                    flash(f'⚠️ Error: Stock insuficiente para {producto_nombre}.', 'error')
                    return redirect(url_for('distribucion'))

            session['distribucion_temporal']['productos'].append({
                'producto_nombre': producto_nombre,
                'cantidad': cantidad
            })
            session.modified = True
            flash(f'✅ Producto agregado a la distribución: {producto_nombre} - Cantidad: {cantidad}', 'success')
            return redirect(url_for('distribucion'))

        elif 'eliminar_producto' in request.form:
            index = int(request.form.get('eliminar_producto'))
            if 0 <= index < len(session['distribucion_temporal']['productos']):
                eliminado = session['distribucion_temporal']['productos'].pop(index)
                session.modified = True
                flash(f'🗑 Producto eliminado de la distribución: {eliminado["producto_nombre"]}', 'warning')
            return redirect(url_for('distribucion'))

        elif 'confirmar_distribucion' in request.form:
            usuario = session['usuario']
            numero_guia = session['distribucion_temporal']['numero_guia']
            destino = session['distribucion_temporal']['destino']

            if not session['distribucion_temporal']['productos']:
                flash('⚠️ Error: No hay productos para distribuir.', 'error')
                return redirect(url_for('distribucion'))
            

            conexion= obtener_conexion()
            with conexion.cursor(cursor_factory=psycopg2.extras.DictCursor) as cursor:
                for producto in session['distribucion_temporal']['productos']:
                    producto_nombre = producto['producto_nombre']
                    cantidad = producto['cantidad']
                    

                      # 🔹 Verificar el stock actual en la base de datos
                    cursor.execute("SELECT stock_disponible FROM productos WHERE LOWER(TRIM(producto_nombre)) = LOWER(TRIM(%s))", (producto_nombre,))
                    producto_existente = cursor.fetchone()

                    if not producto_existente:
                        flash(f'⚠️ Error: El producto "{producto_nombre}" no existe en el inventario.', 'error')
                        return redirect(url_for('distribucion'))

                    stock_actual = producto_existente['stock_disponible']

                    # 🔹 Si la cantidad a distribuir es mayor al stock disponible, no permitir la confirmación
                    if cantidad > stock_actual:
                        flash(f'⚠️ Error: Stock insuficiente para "{producto_nombre}". Solo hay {stock_actual} en inventario.', 'error')
                        return redirect(url_for('distribucion'))

                    # 🔹 Si hay stock suficiente, proceder con la actualización
                    cursor.execute("UPDATE productos SET stock_disponible = stock_disponible - %s WHERE LOWER(TRIM(producto_nombre)) = LOWER(TRIM(%s))", (cantidad, producto_nombre))
            
                    cursor.execute("""
                        INSERT INTO historial_distribucion 
                        (numero_guia, producto_nombre, cantidad, destino, usuario) 
                        VALUES (%s, %s, %s, %s, %s)
                    """, (numero_guia, producto_nombre, cantidad, destino, usuario))
                
                conexion.commit()
                flash('✅ Distribución confirmada y registrada exitosamente.', 'success')

            session['distribucion_temporal'] = {
                'productos': [],
                'numero_guia': '',
                'destino': ''
            }
            session.modified = True
            return redirect(url_for('distribucion'))

    return render_template(
        'distribucion.html', 
        inventario=inventario, 
        productos_temporales=session['distribucion_temporal']['productos'],
        datos=session['distribucion_temporal']
    )

#######################################################################################################################
@app.route('/logout')
def logout():
    session.pop('usuario', None)
    return redirect(url_for('login'))


if __name__ == '__main__':
    port = int(os.environ.get("PORT", 10000))  # Toma el puerto de la variable de entorno
    app.run(host="0.0.0.0", port=port)