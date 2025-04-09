import os
import re
import pdfplumber
import io
import psycopg2
import psycopg2.extras
from flask import Flask, render_template, request, redirect, url_for, flash, session, jsonify
from werkzeug.utils import secure_filename

from dotenv import load_dotenv
load_dotenv()



app = Flask(__name__)
app.secret_key = 'super_secret_key'
app.config['UPLOAD_FOLDER'] = 'uploads'

if not os.path.exists(app.config['UPLOAD_FOLDER']):
    os.makedirs(app.config['UPLOAD_FOLDER'])


# ======================== CONEXIÓN POSTGRESQL ========================
def obtener_conexion():
    return psycopg2.connect(
        host=os.getenv("DB_HOST"),
        database=os.getenv("DB_NAME"),
        user=os.getenv("DB_USER"),
        password=os.getenv("DB_PASSWORD"),  # 💡 Cambiar a variables de entorno para más seguridad
        port=5432,
        cursor_factory=psycopg2.extras.DictCursor,
        sslmode='require'
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

        cursor.execute("SELECT id_proyecto, nombre_proyecto FROM centros_costo ORDER BY id_proyecto")
        proyectos = cursor.fetchall()
            # 🚨 Consulta para productos con alerta de stock
        cursor.execute("""
            SELECT producto_nombre, stock_disponible, stock_critico
            FROM productos
            WHERE stock_disponible <= stock_critico
        """)
        alertas_stock = cursor.fetchall()



    if request.method == 'POST':
        nombre_solicitante = request.form['nombre_solicitante']
        rut_solicitante = request.form['rut_solicitante']
        producto_id = request.form['producto_id']
        cantidad = int(request.form['cantidad'])
        id_proyecto = request.form['id_proyecto']
        motivo = request.form['motivo']


        # Validación del formato del RUT
        if not re.match(r'^\d{7,8}-[\dkK]$', rut_solicitante):
            flash('RUT inválido. Debe tener el formato 12345678-9 o 1234567-K')
            return redirect(url_for('solicitudes'))

        with conexion.cursor(cursor_factory=psycopg2.extras.DictCursor) as cursor:
            cursor.execute("SELECT producto_nombre, estado, precio_unitario FROM productos WHERE id = %(id)s", {'id': producto_id})
            producto = cursor.fetchone()
            producto_nombre = producto['producto_nombre'] if producto else "Desconocido"
            estado_producto = producto['estado'] if producto else "Desconocido"
            precio_unitario = producto['precio_unitario'] if producto else "Desconocido"
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

        # Buscar el nombre del proyecto en la lista de proyectos
        nombre_proyecto = next((p['nombre_proyecto'] for p in proyectos if str(p['id_proyecto']) == id_proyecto), "Desconocido")
   
        total_precio = round(precio_unitario * cantidad)
        session['solicitud_temporal']['productos'].append({
            'producto_id': producto_id,
            'producto_nombre': producto_nombre,
            'cantidad': cantidad,
            'centro_costo': f"{id_proyecto} - {nombre_proyecto}",
            'motivo': motivo,
            'precio_unitario': precio_unitario,
            'precio': total_precio
        })

        flash(f'Producto {producto_nombre} agregado.')
        session.modified = True

        return redirect(url_for('solicitudes'))

    datos = session.get('solicitud_temporal', {})
    return render_template('solicitudes.html', inventario=inventario, datos=datos, proyectos=proyectos, alertas_stock=alertas_stock)


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
        flash("Acceso restringido", "danger")
        return redirect(url_for('login'))

    if 'solicitud_temporal' not in session:
        return redirect(url_for('solicitudes'))

    datos = session['solicitud_temporal']
    usuario = session['usuario']

    if request.method == 'POST':
        try:
            if not datos.get('productos'):
                flash('⚠️ No hay productos para confirmar.', 'error')
                return redirect(url_for('confirmar_solicitud'))

            alertas_stock_critico = []

            conexion = obtener_conexion()
            with conexion.cursor(cursor_factory=psycopg2.extras.DictCursor) as cursor:
                for item in datos['productos']:
                    cursor.execute("SELECT stock_disponible, stock_critico FROM productos WHERE id = %(id)s", {'id': item['producto_id']})
                    producto = cursor.fetchone()

                    if not producto or producto['stock_disponible'] < item['cantidad']:
                        flash(f'❌ No hay suficiente stock para {item["producto_nombre"]}. Solicitud cancelada.', 'error')
                        continue

                    nuevo_stock = producto['stock_disponible'] - item['cantidad']

                    # Actualizar stock
                    cursor.execute("""
                        UPDATE productos 
                        SET stock_disponible = %(stock_disponible)s 
                        WHERE id = %(id)s
                    """, {'stock_disponible': nuevo_stock, 'id': item['producto_id']})

                    # Registrar en historial de solicitudes
                    cursor.execute("""
                        INSERT INTO historial_solicitudes 
                        (nombre_solicitante, rut_solicitante, producto_id, producto_nombre, cantidad, centro_costo, motivo, usuario, precio)
                        VALUES (%(nombre_solicitante)s, %(rut_solicitante)s, %(producto_id)s, %(producto_nombre)s, %(cantidad)s, %(centro_costo)s, %(motivo)s, %(usuario)s, %(precio)s)
                    """, {
                        'nombre_solicitante': datos['nombre_solicitante'],
                        'rut_solicitante': datos['rut_solicitante'],
                        'producto_id': item['producto_id'],
                        'producto_nombre': item['producto_nombre'],
                        'cantidad': item['cantidad'],
                        'centro_costo': item['centro_costo'],
                        'motivo': item['motivo'],
                        'usuario': usuario,
                        'precio': item['precio'],

                    })
                    print("DEBUG MOTIVO:", item.get('motivo'))

                    if item['motivo'] == 'devolucion':
                        cursor.execute("""
                            INSERT INTO devoluciones_pendientes 
                            (nombre_solicitante, rut_solicitante, producto_id, producto_nombre, cantidad, centro_costo, motivo, usuario)
                            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                        """, (
                            datos['nombre_solicitante'],
                            datos['rut_solicitante'],
                            item['producto_id'],
                            item['producto_nombre'],
                            item['cantidad'],
                            item['centro_costo'],
                            item['motivo'],
                            usuario
                        ))
                        print("✅ INSERT ejecutado en devoluciones_pendientes")


                    # Stock crítico
                    if nuevo_stock <= producto['stock_critico']:
                        alertas_stock_critico.append(
                            f'⚠️ ¡ATENCIÓN! {item["producto_nombre"]} ha alcanzado el stock crítico ({nuevo_stock} unidades). Favor realizar pedido.'
                        )

                        # Registrar evento en tabla
                        cursor.execute("""
                            INSERT INTO registro_stock_critico 
                            (producto_id, nombre_producto, fecha, stock_disponible, stock_critico)
                            VALUES (%s, %s, NOW(), %s, %s)
                        """, (
                            item['producto_id'],
                            item['producto_nombre'],
                            nuevo_stock,
                            producto['stock_critico']
                        ))

                        # Flash solo si es crítico
                        flash(f'Solicitud confirmada por {usuario}: {item["producto_nombre"]} - Stock crítico alcanzado ({nuevo_stock})', 'warning')

            conexion.commit()
            flash('✅ Solicitud procesada exitosamente.', 'success')

            # Limpiar sesión temporal
            session.pop('solicitud_temporal', None)
            session.modified = True

            return redirect(url_for('solicitudes'))

        except Exception as e:
            flash(f"❌ Error al confirmar solicitud: {str(e)}", "error")
            return redirect(url_for('confirmar_solicitud'))

    # Render en GET
    return render_template(
        'confirmar_solicitud.html',
        solicitud=datos
    )

####################################################################################################################
@app.route('/devoluciones', methods=['GET', 'POST'])
def devoluciones():
    if 'usuario' not in session or session.get('rol') != 'admin':
        flash("Acceso restringido", "danger")
        return redirect(url_for('login'))

    nombre = ''
    rut = ''
    devoluciones_filtradas = []

    conexion = obtener_conexion()
    with conexion.cursor(cursor_factory=psycopg2.extras.DictCursor) as cursor:
        if request.method == 'POST':
            nombre = request.form['nombre_devolutor'].strip()
            rut = request.form['rut_devolutor'].strip()

            cursor.execute("""
                SELECT * FROM devoluciones_pendientes
                WHERE rut_solicitante = %s
                ORDER BY fecha DESC
            """, (rut,))
        else:
            cursor.execute("SELECT * FROM devoluciones_pendientes ORDER BY fecha DESC")

        devoluciones_filtradas = cursor.fetchall()

    return render_template('devoluciones.html', devoluciones=devoluciones_filtradas, nombre=nombre, rut=rut)

    return render_template('devoluciones.html', devoluciones=[], nombre='', rut='')

@app.route('/confirmar_devolucion', methods=['POST'])
def confirmar_devolucion():
    if 'usuario' not in session:
        flash("Acceso restringido", "danger")
        return redirect(url_for('login'))

    ids = request.form.getlist('devoluciones_ids')
    if not ids:
        flash("⚠️ Debes seleccionar al menos un producto para devolver.", "warning")
        return redirect(url_for('devoluciones'))
    usuario_actual = session.get('usuario')

    conexion = obtener_conexion()
    with conexion.cursor(cursor_factory=psycopg2.extras.DictCursor) as cursor:
        for id_ in ids:
            # Obtener los datos antes de eliminar
            cursor.execute("SELECT * FROM devoluciones_pendientes WHERE id = %s", (id_,))
            devolucion = cursor.fetchone()
            if devolucion:
                # Insertar en historial_devoluciones
                cursor.execute("""
                    INSERT INTO historial_devoluciones 
                    (nombre_devolutor, rut_devolutor, producto_id, producto_nombre, cantidad, fecha_devolucion, usuario)
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                """, (
                    devolucion['nombre_solicitante'],
                    devolucion['rut_solicitante'],
                    devolucion['producto_id'],
                    devolucion['producto_nombre'],
                    devolucion['cantidad'],
                    devolucion['fecha'],
                    usuario_actual
                ))
                # 2. Actualizar stock_disponible en la tabla productos
                cursor.execute("""
                    UPDATE productos
                    SET stock_disponible = stock_disponible + %s
                    WHERE id = %s
                """, (
                    devolucion['cantidad'],
                    devolucion['producto_id']
                ))


            cursor.execute("DELETE FROM devoluciones_pendientes WHERE id = %s", (id_,))
    conexion.commit()

    flash("✅ Devoluciones confirmadas y eliminadas de la base.")
    return redirect(url_for('devoluciones'))

####################################################################################################################
@app.route('/entradas', methods=['GET', 'POST'])
def entradas():
    if 'usuario' not in session or session.get('rol') != 'admin':
        flash("Acceso restringido", "danger")
        return redirect(url_for('login'))

    conexion = obtener_conexion()
    with conexion.cursor(cursor_factory=psycopg2.extras.DictCursor) as cursor:
        cursor.execute("SELECT id, producto_nombre, stock_disponible, unidad, categoria FROM productos")
        inventario = cursor.fetchall()

    if 'entrada_temporal' not in session:
        session['entrada_temporal'] = {
            'productos': [],
            'numero_orden': '',
            'numero_guia': '',
            'numero_factura': ''
        }

    if request.method == 'POST':

        if 'agregar_producto' in request.form:
            session['entrada_temporal']['numero_orden'] = request.form.get('numero_orden', '').strip()
            session['entrada_temporal']['numero_guia'] = request.form.get('numero_guia', '').strip()
            session['entrada_temporal']['numero_factura'] = request.form.get('numero_factura', '').strip()

            producto_id_form = request.form.get('producto_id')
            producto_nombre = request.form.get('producto_nombre', '').strip()
            unidad = request.form.get('unidad', '').strip()
            categoria = request.form.get('categoria', '').strip()
            try:
                cantidad = int(request.form.get('cantidad', 0))
                precio_unitario = float(request.form.get('precio_unitario', 0))
            except ValueError:
                flash("⚠️ La cantidad y el precio unitario deben ser números válidos.", "error")
                return redirect(url_for('entradas'))

            if not producto_nombre or cantidad <= 0 or precio_unitario <= 0:
                flash('⚠️ Error: Debes ingresar un nombre de producto, una cantidad y un precio unitario válidos.', 'error')
                return redirect(url_for('entradas'))

            conexion = obtener_conexion()
            with conexion.cursor(cursor_factory=psycopg2.extras.DictCursor) as cursor:
                if producto_id_form:
                    producto_id = int(producto_id_form)
                else:
                    # 🔽 Producto nuevo: lo insertamos
                    cursor.execute("""
                        INSERT INTO productos (producto_nombre, stock_disponible, unidad, categoria, precio_unitario)
                        VALUES (%s, %s, %s, %s, %s)
                        RETURNING id
                    """, (producto_nombre, cantidad, unidad, categoria, precio_unitario))
                    producto_id = cursor.fetchone()[0]
                    conexion.commit()
                    flash(f"🆕 Producto nuevo agregado: {producto_nombre}", "info")

            session['entrada_temporal']['productos'].append({
                'producto_id': producto_id,
                'producto_nombre': producto_nombre,
                'cantidad': cantidad,
                'unidad': unidad,
                'categoria': categoria,
                'precio_unitario': precio_unitario,
                'es_nuevo': not producto_id_form  # Agrega esta línea

            })

            session.modified = True
            flash(f'✅ Producto agregado: {producto_nombre} - Cantidad: {cantidad} - Precio Unitario: ${precio_unitario:.2f}', 'success')

            return redirect(url_for('entradas'))

        elif 'eliminar_producto' in request.form:
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

                if not any([numero_orden, numero_guia, numero_factura]):
                    flash("⚠️ Debes ingresar al menos número de orden, guía o factura.", "error")
                    return redirect(url_for('entradas')) 

                if not session['entrada_temporal'].get('productos'):
                    flash('⚠️ Error: No hay productos para registrar.', 'error')
                    return redirect(url_for('entradas'))

                conexion = obtener_conexion()
                with conexion.cursor(cursor_factory=psycopg2.extras.DictCursor) as cursor:
                    for producto in session['entrada_temporal']['productos']:
                        producto_id = producto['producto_id']
                        producto_nombre = producto['producto_nombre']
                        cantidad = producto['cantidad']
                        unidad = producto['unidad']
                        categoria = producto['categoria']
                        precio_unitario = producto['precio_unitario']


                        if not producto.get('es_nuevo'):
                        # Solo si el producto no es nuevo, sumamos stock
                            cursor.execute("""
                                UPDATE productos 
                                SET stock_disponible = stock_disponible + %s, precio_unitario = %s
                                WHERE id = %s
                            """, (cantidad, precio_unitario, producto_id))
                        else:
    # Si es nuevo, solo actualizamos el precio si hace falta
                            cursor.execute("""
                                UPDATE productos 
                                SET precio_unitario = %s
                                WHERE id = %s
                            """, (precio_unitario, producto_id))

                        cursor.execute("""
                            INSERT INTO historial_entradas 
                            (numero_orden, numero_guia, numero_factura, producto_id, producto_nombre, cantidad, unidad, categoria, precio_unitario, usuario) 
                            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                        """, (numero_orden, numero_guia, numero_factura, producto_id, producto_nombre, cantidad, unidad, categoria, precio_unitario, usuario))

                conexion.commit()
                flash('✅ Entrada confirmada y registrada exitosamente.', 'success')
                session.pop('entrada_temporal', None)
                session.modified = True
                return redirect(url_for('entradas'))

            except Exception as e:
                flash(f"❌ Error al confirmar entrada: {str(e)}", "error")
                return redirect(url_for('entradas'))

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
        cursor.execute("SELECT producto_nombre, stock_disponible, unidad, categoria, precio_unitario, estado FROM productos")
        inventario = cursor.fetchall()
        cursor.execute("SELECT id_proyecto, nombre_proyecto FROM centros_costo ORDER BY id_proyecto")
        proyectos = cursor.fetchall()


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
            id_proyecto = request.form.get("id_proyecto", "").strip()

            nombre_proyecto = next(
                (p['nombre_proyecto'] for p in proyectos if str(p['id_proyecto']) == id_proyecto),
                "Desconocido"
)

            if not producto_nombre or not cantidad.isdigit() or int(cantidad) <= 0:
                flash('⚠️ Error: Debes ingresar un nombre de producto y cantidad válida.', 'error')
                return redirect(url_for('distribucion'))

            cantidad = int(cantidad)

            with conexion.cursor(cursor_factory=psycopg2.extras.DictCursor) as cursor:
                cursor.execute("""
                    SELECT stock_disponible, estado, precio_unitario
                    FROM productos 
                    WHERE LOWER(TRIM(producto_nombre)) = LOWER(TRIM(%s))
                """, (producto_nombre,))
                producto_existente = cursor.fetchone()

                if not producto_existente:
                    flash(f'⚠️ Error: El producto "{producto_nombre}" no existe en el inventario.', 'error')
                    return redirect(url_for('distribucion'))

                # 🚫 Validar que el producto esté operativo
                if producto_existente['estado'].strip().upper() != 'OPERATIVO':
                    flash(f'❌ El producto "{producto_nombre}" no puede ser distribuido porque no está operativo.', 'error')
                    return redirect(url_for('distribucion'))

                if cantidad > producto_existente['stock_disponible']:
                    flash(f'⚠️ Error: Stock insuficiente para {producto_nombre}.', 'error')
                    return redirect(url_for('distribucion'))
                
                precio_unitario = float(producto_existente['precio_unitario'])


            session['distribucion_temporal']['productos'].append({
                'producto_nombre': producto_nombre,
                'cantidad': cantidad,
                'precio_unitario': precio_unitario,
                'centro_costo': f"{id_proyecto} - {nombre_proyecto}"
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
                    precio_unitario = producto['precio_unitario']
                    precio_total = precio_unitario * cantidad
                    

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
                        (numero_guia, producto_nombre, cantidad, destino, usuario, precio, centro_costo) 
                        VALUES (%s, %s, %s, %s, %s, %s, %s)
                    """, (numero_guia, producto_nombre, cantidad, destino, usuario, precio_total, producto['centro_costo']))
                
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
        datos=session['distribucion_temporal'],
        proyectos=proyectos
    )

@app.route('/admin/centros-costo', methods=['GET', 'POST'])
def gestionar_centros_costo():
    if 'usuario' not in session or session.get('rol') != 'admin':
        flash("Acceso restringido", "danger")
        return redirect(url_for('login'))

    conexion = obtener_conexion()
    with conexion.cursor(cursor_factory=psycopg2.extras.DictCursor) as cursor:
        if request.method == 'POST':
            id_proyecto = request.form['id_proyecto'].strip()
            nombre = request.form['nombre_proyecto'].strip()

            if not id_proyecto.isdigit() or not nombre:
                flash("⚠️ Debes ingresar un ID numérico y un nombre de proyecto válido.", "danger")
                return redirect(url_for('gestionar_centros_costo'))

            cursor.execute("INSERT INTO centros_costo (id_proyecto, nombre_proyecto) VALUES (%s, %s) ON CONFLICT (id_proyecto) DO NOTHING", 
                           (int(id_proyecto), nombre))
            conexion.commit()
            flash("✅ Centro de costo agregado con éxito", "success")

        cursor.execute("SELECT id_proyecto, nombre_proyecto FROM centros_costo ORDER BY id_proyecto")
        centros = cursor.fetchall()

    return render_template('admin_centros.html', centros=centros)


#######################################################################################################################
@app.route('/logout')
def logout():
    session.pop('usuario', None)
    return redirect(url_for('login'))


if __name__ == '__main__':
    port = int(os.environ.get("PORT", 10000))  # Toma el puerto de la variable de entorno
    app.run(host="0.0.0.0", port=port)