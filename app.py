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
    "Javier": {"password": "ADMINJCM", "rol": "admin"},
    "andrea": {"password": "ADMINJCM", "rol": "admin"},
    "Mauricio": {"password": "MAURICIOJCM", "rol": "jefeB"},
    "Mariela": {"password": "MARIELAJCM", "rol": "bodega"},
    "bodega": {"password": "bodega", "rol": "bodega"},
    "admin": {"password": "1234", "rol": "admin"},
    "Nicolas": {"password": "NICOLASJCM", "rol": "bodega"},
    "J.FUENTES": {"password": "J.FUENTESJCM", "rol": "jefeT"},
    "J.HENRIQUEZ": {"password": "J.HENRIQUEZJCM", "rol": "jefeT"},
    "O.DIAZ": {"password": "O.DIAZJCM", "rol": "jefeT"},
    "S.VILLAR": {"password": "S.VILLARJCM", "rol": "jefeT"},
    "jefe terreno": {"password": "JEFETERRENOJCM", "rol": "jefeT"}

}

@app.route('/', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        user = request.form['usuario']
        password = request.form['password']
        print("🔍 Usuario ingresado:", user)
        print("🔍 Contraseña ingresada:", password)


        conexion = obtener_conexion()

        # 🔐 Validación de conexión
        if conexion is None:
            flash('❌ No se pudo conectar a la base de datos. Revisa tu configuración.', 'danger')
            return redirect(url_for('login'))

        with conexion.cursor(cursor_factory=psycopg2.extras.DictCursor) as cursor:
            cursor.execute("""
                SELECT * FROM usuarios
                WHERE usuario = %s AND contraseña = %s
            """, (user, password))
            resultado = cursor.fetchone()
            print("📦 Resultado SQL:", resultado)

            if resultado:
                session['usuario'] = resultado['usuario']
                session['rol'] = resultado['rol']
                session['rut'] = resultado['rut']  # ✅ necesario para filtrar por RUT

                if session['rol'] == 'admin':
                    return redirect(url_for('asignar_personal'))
                elif session['rol'] == 'jefeT':
                    return redirect(url_for('control_gastos'))
                elif session['rol'] == 'bodega':
                    return redirect(url_for('solicitudes'))
                elif session['rol'] == 'jefeB':
                    return redirect(url_for('solicitudes'))                

        flash('Credenciales incorrectas', 'danger')
        return redirect(url_for('login'))

    return render_template('login.html')

######################################################################################################################

@app.route('/solicitudes', methods=['GET', 'POST'])
def solicitudes():
    if 'usuario' not in session or session.get('rol') not in ['admin', 'bodega','jefeB']:
        flash("No tienes acceso a esta página", "danger")
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
    return render_template(
        'solicitudes.html',
        inventario=inventario,
        datos=datos,
        proyectos=proyectos,
        alertas_stock=alertas_stock,
        mostrar_descarga=True,
        url_descarga="/descargar_excel/solicitudes"
    )

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
    if 'usuario' not in session or session.get('rol') not in ['admin', 'bodega','jefeB']:
        flash("No tienes acceso a esta página", "danger")
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

    return render_template(
        'devoluciones.html',
        devoluciones=devoluciones_filtradas,
        nombre=nombre,
        rut=rut,
        mostrar_descarga=True,
        url_descarga="/descargar_excel/devoluciones"
    )


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
                # Insertar en historial_devoluciones con centro_costo
                cursor.execute("""
                    INSERT INTO historial_devoluciones 
                    (nombre_devolutor, rut_devolutor, producto_id, producto_nombre, cantidad, fecha_devolucion, usuario, centro_costo)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                """, (
                    devolucion['nombre_solicitante'],
                    devolucion['rut_solicitante'],
                    devolucion['producto_id'],
                    devolucion['producto_nombre'],
                    devolucion['cantidad'],
                    devolucion['fecha'],
                    usuario_actual,
                    devolucion['centro_costo']
                ))

                # Actualizar stock_disponible en productos
                cursor.execute("""
                    UPDATE productos
                    SET stock_disponible = stock_disponible + %s
                    WHERE id = %s
                """, (
                    devolucion['cantidad'],
                    devolucion['producto_id']
                ))

                # Eliminar de devoluciones_pendientes
                cursor.execute("DELETE FROM devoluciones_pendientes WHERE id = %s", (id_,))

    conexion.commit()

    flash("✅ Devoluciones confirmadas y eliminadas de la base.")
    return redirect(url_for('devoluciones'))


####################################################################################################################
@app.route('/entradas', methods=['GET', 'POST'])
def entradas():
    if 'usuario' not in session or session.get('rol') not in ['admin', 'bodega','jefeB']:
        flash("No tienes acceso a esta página", "danger")
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
        datos=session['entrada_temporal'],
        mostrar_descarga=True,
        url_descarga="/descargar_excel/entradas"
    )

####################################################################################################################
@app.route('/inventario', methods=['GET', 'POST'])
def ver_inventario():
    if 'usuario' not in session or session.get('rol') not in ['admin', 'jefeT', 'bodega', 'jefeB']:
        flash("No tienes acceso a esta página", "danger")
        return redirect(url_for('login'))

    conexion = obtener_conexion()
    usuario = session.get('usuario')
    rol_usuario = session.get('rol')
    rut_usuario = session.get('rut')

    centros_costo = []
    centro_seleccionado = request.args.get('centro_costo')
    producto_buscado = request.args.get('producto_buscado')
    inventario = []
    inventario_centro = []
    inventario_filtrado = []
    categorias = []

    with conexion.cursor(cursor_factory=psycopg2.extras.DictCursor) as cursor:
        cursor.execute("SELECT * FROM productos")
        inventario = cursor.fetchall()

        cursor.execute("SELECT DISTINCT categoria FROM productos ORDER BY categoria")
        categorias = [row[0] for row in cursor.fetchall()]

        cursor.execute("SELECT DISTINCT centro_costo FROM historial_solicitudes")
        centros_costo = [row[0] for row in cursor.fetchall()]

        if centro_seleccionado:
            cursor.execute("""
                SELECT hs.producto_nombre,
                       COALESCE(SUM(hs.cantidad), 0) - COALESCE(SUM(hd.cantidad), 0) AS cantidad_actual,
                       MAX(hs.fecha_solicitud) AS ultima_solicitud
                FROM historial_solicitudes hs
                LEFT JOIN historial_devoluciones hd 
                    ON hs.producto_id = hd.producto_id AND hs.centro_costo = hd.centro_costo
                WHERE hs.centro_costo = %s
                GROUP BY hs.producto_nombre
            """, (centro_seleccionado,))
            inventario_centro = cursor.fetchall()

        if producto_buscado:
            cursor.execute("""
                SELECT hs.centro_costo,
                       hs.producto_nombre,
                       COALESCE(SUM(hs.cantidad), 0) - COALESCE(SUM(hd.cantidad), 0) AS cantidad_actual,
                       MAX(hs.fecha_solicitud) AS ultima_solicitud
                FROM historial_solicitudes hs
                LEFT JOIN historial_devoluciones hd 
                    ON hs.producto_id = hd.producto_id AND hs.centro_costo = hd.centro_costo
                WHERE hs.producto_nombre ILIKE %s
                GROUP BY hs.centro_costo, hs.producto_nombre
            """, (f"%{producto_buscado}%",))
            inventario_filtrado = cursor.fetchall()

    tab_activa = request.args.get('tab_activa', 'general')

    return render_template(
        'inventario.html',
        inventario=inventario,
        centros_costo=centros_costo,
        centro_seleccionado=centro_seleccionado,
        inventario_centro=inventario_centro,
        inventario_filtrado=inventario_filtrado,
        producto_buscado=producto_buscado,
        categorias=categorias,
        mostrar_descarga=True,
        url_descarga="/descargar_excel/inventario",
        tab_activa='centros' if centro_seleccionado or producto_buscado else 'general',
        rol_usuario=rol_usuario
    )


@app.route('/editar_estado_producto', methods=['POST'])
def editar_estado_producto():
    if 'usuario' not in session or session.get('rol') not in ['admin', 'jefeB', 'bodega']:
        flash("No tienes permisos para editar el estado de productos.", "danger")
        return redirect(url_for('ver_inventario'))

    producto_id = request.form.get('producto_id')
    nuevo_estado = request.form.get('nuevo_estado')
    cantidad_modificada = request.form.get('cantidad_modificada')

    if not producto_id or not nuevo_estado or not cantidad_modificada:
        flash("Faltan datos para actualizar el estado del producto.", "warning")
        return redirect(url_for('ver_inventario'))

    try:
        cantidad_modificada = int(cantidad_modificada)
    except ValueError:
        flash("La cantidad debe ser un número válido.", "warning")
        return redirect(url_for('ver_inventario'))

    conexion = obtener_conexion()
    with conexion.cursor(cursor_factory=psycopg2.extras.DictCursor) as cursor:
        # Obtener producto original
        cursor.execute("SELECT * FROM productos WHERE id = %s", (producto_id,))
        producto = cursor.fetchone()

        if not producto:
            flash("Producto no encontrado.", "danger")
            return redirect(url_for('ver_inventario'))

        stock_actual = producto['stock_disponible']
        if cantidad_modificada > stock_actual:
            flash("La cantidad modificada no puede ser mayor al stock disponible.", "warning")
            return redirect(url_for('ver_inventario'))

        # Descontar cantidad del producto original
        nuevo_stock = stock_actual - cantidad_modificada
        cursor.execute("""
            UPDATE productos
            SET stock_disponible = %s
            WHERE id = %s
        """, (nuevo_stock, producto_id))

        # Insertar nuevo registro con el nuevo estado y misma base
        cursor.execute("""
            INSERT INTO productos (
                producto_nombre, stock_disponible, stock_critico, categoria, estado, producto_base_id
            ) VALUES (%s, %s, %s, %s, %s, %s)
        """, (
            producto['producto_nombre'],
            cantidad_modificada,
            producto['stock_critico'],
            producto['categoria'],
            nuevo_estado,
            producto['producto_base_id'] or producto['id']
        ))

        conexion.commit()

    flash("✅ Estado y cantidad modificados correctamente. Se creó un nuevo registro con el nuevo estado.", "success")
    return redirect(url_for('ver_inventario'))

########################################################################################################################

@app.route('/admin/centros-costo', methods=['GET', 'POST'])
def gestionar_centros_costo():
    if 'usuario' not in session or session.get('rol') not in ['admin', 'bodega','jefeB']:
        flash("No tienes acceso a esta página", "danger")
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
# RUTA PARA CONTROL DE GASTOS
# RUTA PARA CONTROL DE GASTOS
@app.route('/control_gastos', methods=['GET', 'POST'])
def control_gastos():
    if 'usuario' not in session or session.get('rol') not in ['admin', 'jefeT']:
        flash("No tienes acceso a esta página", "danger")
        return redirect(url_for('login'))

    conexion = obtener_conexion()
    rol_usuario = session.get('rol')
    centros_costo = []

    with conexion.cursor() as cursor:
        if rol_usuario in ['jefeT', 'jefeB']:
            rut_usuario = session.get('rut')
            cursor.execute("""
                SELECT DISTINCT centro_costo
                FROM asignacion_personal
                WHERE rut = %s AND rol = %s
            """, (rut_usuario, rol_usuario))
            centros_costo = [row[0] for row in cursor.fetchall()]
        else:  # admin
            cursor.execute("""
                SELECT DISTINCT centro_costo
                FROM asignacion_personal
            """)
            centros_costo = [row[0] for row in cursor.fetchall()]

    # Registro de gastos (cuando se envía el formulario)
    if request.method == 'POST' and 'confirmar_adquisiciones' in request.form:
        centro_costo = request.form.get('centro_costo', '').strip()
        categoria = request.form.get('categoria', '').strip()
        fecha = request.form.get('fecha_factura', '').strip() or None
        tipo_documento = request.form.get('tipo_documento', '').strip()
        numero_documento = request.form.get('numero_factura', '').strip() or None
        registro_compra = request.form.get('registro_compra', '').strip() or None
        tipo_pago = request.form.get('tipo_pago', '').strip()
        usuario_actual = session.get('usuario')

        try:
            monto_raw = request.form.get('monto_registro', '').strip()
            monto_registro = int(monto_raw) if monto_raw else None
        except ValueError:
            flash("⚠️ El monto del registro debe ser un número entero válido.", "error")
            return redirect(url_for('control_gastos'))

        if not centro_costo or not categoria or not tipo_documento:
            flash("⚠️ Debes completar todos los campos obligatorios.", "error")
            return redirect(url_for('control_gastos'))

        with conexion.cursor() as cursor:
            cursor.execute("""
                SELECT 1 FROM registro_costos
                WHERE centro_costo = %s AND categoria = %s AND fecha = %s
                      AND tipo_documento = %s AND numero_documento = %s
            """, (centro_costo, categoria, fecha, tipo_documento, numero_documento))
            existe = cursor.fetchone()

            if existe:
                flash("⚠️ Ese registro ya fue ingresado previamente.", "warning")
                return redirect(url_for('control_gastos'))

            try:
                # Insertar en registro_costos
                cursor.execute("""
                    INSERT INTO registro_costos (
                        centro_costo, categoria, fecha, tipo_documento,
                        numero_documento, registro_compra, monto_registro, usuario, tipo_pago
                    )
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                """, (
                    centro_costo, categoria, fecha, tipo_documento,
                    numero_documento, registro_compra, monto_registro, usuario_actual, tipo_pago
                ))

                # Insertar en facturaOC si es factura
                if tipo_documento.lower() == 'factura' and numero_documento:
                    cursor.execute("""
                        INSERT INTO facturaOC (
                            numero_factura, fecha_factura, rut_proveedor,
                            nombre_proveedor, orden_compra, monto_factura, origen
                        )
                        VALUES (%s, %s, NULL, NULL, NULL, %s, %s)
                    """, (
                        numero_documento, fecha, monto_registro, 'control_gastos'
                    ))

                # Insertar en facturaOC si es orden de compra
                elif tipo_documento.lower() == 'orden de compra' and numero_documento:
                    cursor.execute("""
                        INSERT INTO facturaOC (
                            orden_compra, monto_factura, origen
                        )
                        VALUES (%s, %s, %s)
                        ON CONFLICT (orden_compra) DO NOTHING
                    """, (
                        numero_documento, monto_registro, 'control_gastos'
                    ))

                conexion.commit()
                flash("✅ Registro guardado correctamente.", "success")

            except psycopg2.IntegrityError as e:
                conexion.rollback()
                flash("⚠️ Error inesperado al guardar el registro.", "danger")
                print("ERROR DETALLE:", e)

        return redirect(url_for('control_gastos'))

    # Mostrar registros guardados y categorías
    with conexion.cursor(cursor_factory=psycopg2.extras.DictCursor) as cursor:
        cursor.execute("""
            SELECT centro_costo, categoria, fecha, tipo_documento, numero_documento, 
                   registro_compra, monto_registro, usuario, tipo_pago
            FROM registro_costos
            ORDER BY fecha DESC
        """)
        gastos_guardados = cursor.fetchall()

        cursor.execute("""
            SELECT DISTINCT categoria
            FROM clasificacion_costos
            ORDER BY categoria ASC
        """)
        categorias = cursor.fetchall()

    return render_template(
        'control_gastos.html',
        historial_adquisiciones=gastos_guardados,
        centros_costo=centros_costo,
        categorias=categorias,
        mostrar_descarga=True,
        url_descarga="/descargar_excel/gastos"
    )


#####################################################################################################
# RUTA PARA ASIGNAR PERSONAL
@app.route('/asignar_personal', methods=['GET', 'POST']) 
def asignar_personal():
    if 'usuario' not in session or session.get('rol') not in ['admin']:
        flash("No tienes acceso a esta página", "danger")
        return redirect(url_for('login'))

    conexion = obtener_conexion()

    if request.method == 'POST':
        usuario = session.get('usuario')

        # ➕ Agregar nuevo personal
        if 'agregar_personal' in request.form:
            nuevo_nombre = request.form.get('nuevo_nombre', '').strip()
            nuevo_apellido = request.form.get('nuevo_apellido', '').strip()
            nuevo_rut = request.form.get('nuevo_rut', '').strip()
            nuevo_especialidad = request.form.get('nuevo_especialidad', '').strip()
            nuevo_rol = request.form.get('nuevo_rol', '').strip()
            nuevo_genero = request.form.get('nuevo_genero', '').strip()
            pago_haberes_raw = request.form.get('pago_haberes', '').strip()

            if not nuevo_nombre or not nuevo_apellido or not nuevo_rut or not nuevo_rol or not nuevo_genero or not pago_haberes_raw:
                flash("⚠️ Todos los campos para agregar personal son obligatorios.", "warning")
            elif nuevo_genero not in ['Femenino', 'Masculino']:
                flash("⚠️ El género debe ser 'Femenino' o 'Masculino'.", "warning")
            else:
                with conexion.cursor() as cursor:
                    cursor.execute("SELECT 1 FROM personal WHERE rut = %s", (nuevo_rut,))
                    existe = cursor.fetchone()
                    if existe:
                        flash("⚠️ No se puede ingresar el RUT porque ya está registrado en el sistema.", "warning")
                        return redirect(url_for('asignar_personal'))

                    try:
                        pago_haberes = float(pago_haberes_raw)
                        pago_hora = round(pago_haberes / 176, 2)
                    except ValueError:
                        flash("⚠️ El campo Pago HABERES debe ser un número válido.", "warning")
                        return redirect(url_for('asignar_personal'))

                    cursor.execute("""
                        INSERT INTO personal (nombre, apellido, rut, especialidad, rol, genero, pago_hora)
                        VALUES (%s, %s, %s, %s, %s, %s, %s)
                    """, (nuevo_nombre, nuevo_apellido, nuevo_rut, nuevo_especialidad, nuevo_rol, nuevo_genero, pago_hora))
                    conexion.commit()
                    flash(f"✅ {nuevo_nombre} {nuevo_apellido} agregado a la base de datos con pago por hora ${pago_hora}.", "success")
            return redirect(url_for('asignar_personal'))

        # 📌 Asignar personal
        elif 'confirmar_asignacion' in request.form:
            centro_costo = request.form.get('centro_costo')
            seleccionados = request.form.getlist('seleccionados')

            if not centro_costo or not seleccionados:
                flash("⚠️ Debes seleccionar al menos una persona y un centro de costo.", "warning")
                return redirect(url_for('asignar_personal'))

            with conexion.cursor() as cursor:
                for dato in seleccionados:
                    rut, nombre, apellido, rol = dato.split('|')

                    cursor.execute("""
                        SELECT 1 FROM asignacion_personal
                        WHERE rut = %s AND centro_costo = %s
                    """, (rut, centro_costo))
                    existe = cursor.fetchone()

                    if not existe:
                        cursor.execute("""
                            INSERT INTO asignacion_personal (nombre, apellido, rut, rol, centro_costo, asignado_por)
                            VALUES (%s, %s, %s, %s, %s, %s)
                        """, (nombre, apellido, rut, rol, centro_costo, usuario))
            conexion.commit()
            flash("✅ Personal asignado correctamente.", "success")
            return redirect(url_for('asignar_personal'))

        # 🗑️ Eliminar asignación
        elif 'eliminar_asignacion' in request.form:
            rut = request.form.get('rut')
            centro_costo = request.form.get('centro_costo_eliminar')

            with conexion.cursor() as cursor:
                cursor.execute("""
                    DELETE FROM asignacion_personal
                    WHERE rut = %s AND centro_costo = %s
                """, (rut, centro_costo))
                conexion.commit()
            flash(f"✅ Asignación de {rut} eliminada del centro de costo {centro_costo}.", "success")
            return redirect(url_for('asignar_personal'))

        # ✏️ Modificar asignación
        elif 'modificar_asignacion' in request.form:
            rut = request.form.get('rut_modificar')
            nuevo_centro = request.form.get('nuevo_centro')
            antiguo_centro = request.form.get('centro_costo_actual')

            with conexion.cursor() as cursor:
                cursor.execute("""
                    UPDATE asignacion_personal
                    SET centro_costo = %s
                    WHERE rut = %s AND centro_costo = %s
                """, (nuevo_centro, rut, antiguo_centro))
                conexion.commit()
            flash(f"✏️ Asignación de {rut} actualizada a centro de costo {nuevo_centro}.", "success")
            return redirect(url_for('asignar_personal'))

    # Datos para mostrar
    with conexion.cursor(cursor_factory=psycopg2.extras.DictCursor) as cursor:
        cursor.execute("SELECT nombre, apellido, rut, rol FROM personal ORDER BY nombre ASC")
        lista_personal = cursor.fetchall()

        # ✅ Filtrar centros de costo según el rol
        rol_usuario = session.get('rol')
        rut_usuario = session.get('rut')

        if rol_usuario in ['jefeT', 'jefeB']:
            cursor.execute("""
                SELECT DISTINCT id_proyecto, nombre_proyecto
                FROM centros_costo
                WHERE (id_proyecto || ' - ' || nombre_proyecto) IN (
                    SELECT centro_costo
                    FROM asignacion_personal
                    WHERE rut = %s
                )
                ORDER BY id_proyecto
            """, (rut_usuario,))
        else:
            cursor.execute("SELECT id_proyecto, nombre_proyecto FROM centros_costo ORDER BY id_proyecto")
        centros_costo = cursor.fetchall()
        cursor.execute("""
            SELECT centro_costo, COUNT(*) as cantidad
            FROM asignacion_personal
            GROUP BY centro_costo
            ORDER BY centro_costo
        """)
        resumen_asignacion = cursor.fetchall()

        detalle_asignacion = {}
        for item in resumen_asignacion:
            cursor.execute("""
                SELECT nombre, apellido, rut
                FROM asignacion_personal
                WHERE centro_costo = %s
                ORDER BY nombre
            """, (item['centro_costo'],))
            detalle_asignacion[item['centro_costo']] = cursor.fetchall()

    return render_template('asignar_personal.html', 
                           lista_personal=lista_personal, 
                           centros_costo=centros_costo,
                           resumen_asignacion=resumen_asignacion,
                           detalle_asignacion=detalle_asignacion)


##################################################################################################################
from datetime import datetime, timedelta

@app.route('/registro_horas', methods=['GET', 'POST'])
def registro_horas():
    if 'usuario' not in session or session.get('rol') not in ['admin', 'jefeT', 'jefeB']:
        flash("No tienes acceso a esta página", "danger")
        return redirect(url_for('login'))

    conexion = obtener_conexion()
    if conexion is None:
        flash("❌ No se pudo conectar a la base de datos", "danger")
        return redirect(url_for('login'))

    trabajadores = []
    semana_actual = ''
    centro_costo_actual = ''
    fechas_por_dia = {}
    dias_bloqueados = {}
    resumen = {}

    rol_usuario = session.get('rol')
    centros_costo = []

    with conexion.cursor() as cursor:
        if rol_usuario in ['jefeT', 'jefeB']:
            rut_usuario = session.get('rut')
            cursor.execute("""
                SELECT DISTINCT centro_costo
                FROM asignacion_personal
                WHERE rut = %s
            """, (rut_usuario,))
            centros_costo = [row[0] for row in cursor.fetchall()]
        else:
            cursor.execute("SELECT DISTINCT centro_costo FROM asignacion_personal")
            centros_costo = [row[0] for row in cursor.fetchall()]

    if request.method == 'POST':
        if 'guardar_semana' in request.form:
            semana = request.form.get('semana')
            centro_costo = request.form.get('centro_costo')
            usuario = session.get('usuario')

            if semana:
                year, week = semana.split('-W')
                primer_dia = datetime.fromisocalendar(int(year), int(week), 1)
                dias = ['lun', 'mar', 'mie', 'jue', 'vie']
                for i, d in enumerate(dias):
                    fechas_por_dia[d] = (primer_dia + timedelta(days=i)).strftime('%Y-%m-%d')

            domingo = primer_dia + timedelta(days=6)

            with conexion.cursor() as cursor:
                cursor.execute("""
                    SELECT DISTINCT horas_fecha FROM registro_horas
                    WHERE centro_costo = %s AND horas_fecha BETWEEN %s AND %s
                """, (centro_costo, primer_dia.date(), domingo))
                fechas_guardadas = cursor.fetchall()
                for fila in fechas_guardadas:
                    fecha_str = fila[0].strftime('%Y-%m-%d')
                    dias_bloqueados[fecha_str] = True

            with conexion.cursor() as cursor:
                cursor.execute("""
                    SELECT rut, nombre, apellido FROM personal
                    WHERE rut IN (
                        SELECT rut FROM asignacion_personal WHERE centro_costo = %s
                    )
                """, (centro_costo,))
                personas = cursor.fetchall()

            dia_a_guardar = request.form.get('dia_a_guardar', '').strip().lower()
            fecha_real = fechas_por_dia.get(dia_a_guardar)

            if not fecha_real:
                flash("⚠️ Día no válido", "warning")
                return redirect(url_for('registro_horas'))

            if fecha_real in dias_bloqueados:
                flash("⚠️ Ese día ya fue registrado", "info")
                return redirect(url_for('registro_horas'))

            with conexion.cursor() as cursor:
                for persona in personas:
                    rut = persona[0]
                    nombre = persona[1]
                    apellido = persona[2]

                    hn_key = f'hn_{rut}_{dia_a_guardar}'
                    he_key = f'he_{rut}_{dia_a_guardar}'

                    if hn_key not in request.form:
                        continue

                    hn_val = request.form.get(hn_key, '').strip().upper()
                    he_val = request.form.get(he_key, '').strip()
                    observacion = None
                    observacionP = None

                    try:
                        if hn_val in ['L', 'V', 'F', 'P']:
                            horas_normales = 0
                            observacion = hn_val

                            if hn_val == 'P':
                                tipo_permiso = request.form.get(f'tipo_permiso_{rut}_{dia_a_guardar}', '')
                                razon_permiso = request.form.get(f'razon_permiso_{rut}_{dia_a_guardar}', '')
                                if tipo_permiso and razon_permiso:
                                    observacionP = f"{tipo_permiso} - {razon_permiso}"
                                else:
                                    observacionP = tipo_permiso or razon_permiso or None
                        elif hn_val == '':
                            horas_normales = 0
                        else:
                            horas_normales = int(hn_val)

                        horas_extras = int(he_val) if he_val != '' else 0

                        if horas_normales < 0 or horas_normales > 24 or horas_extras < 0 or horas_extras > 24:
                            flash(f"⚠️ Error en las horas para {rut}", "warning")
                            continue

                        cursor.execute("""
                            SELECT 1 FROM registro_horas
                            WHERE horas_fecha = %s AND centro_costo = %s AND rut = %s
                        """, (fecha_real, centro_costo, rut))
                        if cursor.fetchone():
                            continue

                        if observacion == 'V':
                            dias_trabajados = 1
                        else:
                            dias_trabajados = round(horas_normales / 9, 1) if horas_normales else 0

                        cursor.execute("""
                            INSERT INTO registro_horas (
                                rut, nombre, apellido, centro_costo,
                                horas_normales, horas_extras, horas_fecha,
                                fecha_registro, usuario, observacion, dias_trabajados, observacionP
                            )
                            VALUES (%s, %s, %s, %s, %s, %s, %s, CURRENT_DATE, %s, %s, %s, %s)
                        """, (rut, nombre, apellido, centro_costo,
                              horas_normales, horas_extras, fecha_real,
                              usuario, observacion, dias_trabajados, observacionP))

                    except ValueError:
                        flash(f"⚠️ Error en las horas para {rut}", "warning")

            conexion.commit()
            flash("✅ Día registrado exitosamente. Ese día queda bloqueado.", "success")
            return redirect(url_for('registro_horas'))

        else:
            centro_costo_actual = request.form.get('centro_costo', '').strip()
            semana_actual = request.form.get('semana', '').strip()

            if semana_actual and centro_costo_actual:
                try:
                    year, week = semana_actual.split('-W')
                    primer_dia = datetime.fromisocalendar(int(year), int(week), 1).date()
                    domingo = primer_dia + timedelta(days=6)

                    dias = ['lun', 'mar', 'mie', 'jue', 'vie']
                    for i, d in enumerate(dias):
                        fecha_dia = primer_dia + timedelta(days=i)
                        fechas_por_dia[d] = fecha_dia.strftime('%Y-%m-%d')

                    with conexion.cursor() as cursor:
                        cursor.execute("""
                            SELECT DISTINCT horas_fecha FROM registro_horas
                            WHERE centro_costo = %s AND horas_fecha BETWEEN %s AND %s
                        """, (centro_costo_actual, primer_dia, domingo))
                        fechas_guardadas = cursor.fetchall()
                        for fila in fechas_guardadas:
                            fecha_str = fila[0].strftime('%Y-%m-%d')
                            dias_bloqueados[fecha_str] = True

                    with conexion.cursor() as cursor:
                        cursor.execute("""
                            SELECT nombre, apellido, rut FROM personal
                            WHERE rut IN (
                                SELECT rut FROM asignacion_personal WHERE centro_costo = %s
                            )
                        """, (centro_costo_actual,))
                        trabajadores = cursor.fetchall()

                except Exception as e:
                    flash(f"⚠️ Error al procesar la semana: {e}", "danger")

    if not centro_costo_actual and centros_costo:
        centro_costo_actual = centros_costo[0]

    if centro_costo_actual:
        with conexion.cursor() as cursor:
            cursor.execute("""
                SELECT 
                    MAX(horas_fecha) AS ultima_fecha,
                    SUM(COALESCE(horas_normales, 0) + COALESCE(horas_extras, 0)) AS total_horas
                FROM registro_horas
                WHERE centro_costo = %s AND horas_fecha <= CURRENT_DATE
            """, (centro_costo_actual,))
            fila = cursor.fetchone()
            resumen = {
                'ultima_fecha': fila[0],
                'total_horas': fila[1] if fila[1] else 0
            }

    return render_template("registro_horas.html",
                           trabajadores=trabajadores,
                           semana=semana_actual,
                           centro_costo=centro_costo_actual,
                           centros_costo=centros_costo,
                           fechas_por_dia=fechas_por_dia,
                           dias_bloqueados=dias_bloqueados,
                           resumen=resumen)

########################################################################################################
@app.route('/adquisiciones', methods=['GET', 'POST'])
def adquisiciones():
    if 'usuario' not in session or session.get('rol') not in ['admin', 'bodega', 'jefeB']:
        flash("⚠️ Acceso restringido", "danger")
        return redirect(url_for('login'))

    conexion = obtener_conexion()
    usuario = session.get('usuario')

    if request.method == 'POST':
        # ✅ Completar datos de factura pendiente (OC, RUT, proveedor)
        if 'asignar_oc' in request.form:
            numero_factura = request.form.get('factura_a_actualizar', '').strip()
            nueva_oc = request.form.get('nueva_oc', '').strip()
            rut_proveedor = request.form.get('rut_proveedor', '').strip()
            nombre_proveedor = request.form.get('nombre_proveedor', '').strip()

            if not numero_factura or not nueva_oc or not rut_proveedor or not nombre_proveedor:
                flash("⚠️ Todos los campos deben completarse", "warning")
                return redirect(url_for('adquisiciones'))

            try:
                nueva_oc = int(nueva_oc)
            except ValueError:
                flash("⚠️ La orden de compra debe ser un número", "warning")
                return redirect(url_for('adquisiciones'))

            with conexion.cursor() as cursor:
                cursor.execute("""
                    UPDATE facturaOC
                    SET orden_compra = %s,
                        rut_proveedor = %s,
                        nombre_proveedor = %s
                    WHERE numero_factura = %s
                """, (nueva_oc, rut_proveedor, nombre_proveedor, numero_factura))

            conexion.commit()
            flash(f"✅ Datos actualizados para la factura {numero_factura}", "success")
            return redirect(url_for('adquisiciones'))

        # ✅ Completar orden de compra que ya está registrada sin factura
        elif 'registrar_factura' in request.form:
            orden_compra = request.form.get('orden_compra', '').strip()
            numero_factura = request.form.get('numero_factura', '').strip()
            fecha_factura = request.form.get('fecha_factura', '').strip()
            rut_proveedor = request.form.get('rut_proveedor', '').strip()
            nombre_proveedor = request.form.get('nombre_proveedor', '').strip()
            monto_factura = request.form.get('monto_factura', '').strip()

            if not orden_compra or not numero_factura or not fecha_factura or not rut_proveedor or not nombre_proveedor or not monto_factura:
                flash("⚠️ Todos los campos deben completarse", "warning")
                return redirect(url_for('adquisiciones'))

            try:
                orden_compra = int(orden_compra)
                monto_factura = float(monto_factura)
            except ValueError:
                flash("⚠️ OC debe ser numérica y el monto válido", "warning")
                return redirect(url_for('adquisiciones'))

            with conexion.cursor() as cursor:
                # Verifica si ya existe la orden
                cursor.execute("SELECT id FROM facturaOC WHERE orden_compra = %s", (orden_compra,))
                existe_oc = cursor.fetchone()

                if existe_oc:
                    # Actualiza datos
                    cursor.execute("""
                        UPDATE facturaOC
                        SET numero_factura = %s,
                            fecha_factura = %s,
                            rut_proveedor = %s,
                            nombre_proveedor = %s,
                            monto_factura = %s
                        WHERE orden_compra = %s
                    """, (numero_factura, fecha_factura, rut_proveedor, nombre_proveedor, monto_factura, orden_compra))
                else:
                    # Inserta si no existe (por seguridad)
                    cursor.execute("""
                        INSERT INTO facturaOC (
                            orden_compra, numero_factura, fecha_factura,
                            rut_proveedor, nombre_proveedor, monto_factura, usuario_registro
                        )
                        VALUES (%s, %s, %s, %s, %s, %s, %s)
                    """, (orden_compra, numero_factura, fecha_factura, rut_proveedor, nombre_proveedor, monto_factura, usuario))

            conexion.commit()
            flash("✅ Factura completada correctamente", "success")
            return redirect(url_for('adquisiciones'))

    # 🔽 Cargar facturas que no tienen OC asignada
    with conexion.cursor(cursor_factory=psycopg2.extras.DictCursor) as cursor:
        cursor.execute("""
            SELECT numero_factura, fecha_factura, rut_proveedor, nombre_proveedor
            FROM facturaOC
            WHERE orden_compra IS NULL
            ORDER BY fecha_factura DESC
        """)
        facturas_sin_oc = cursor.fetchall()

    # 🔽 Cargar órdenes de compra sin factura asociada
    with conexion.cursor(cursor_factory=psycopg2.extras.DictCursor) as cursor:
        cursor.execute("""
            SELECT orden_compra, monto_factura
            FROM facturaOC
            WHERE numero_factura IS NULL AND orden_compra IS NOT NULL
            ORDER BY orden_compra
        """)
        ordenes_sin_factura = cursor.fetchall()

    return render_template("adquisiciones.html",
                           facturas_sin_oc=facturas_sin_oc,
                           ordenes_sin_factura=ordenes_sin_factura)

####################################################################################################################
@app.route('/descargar_excel/<tabla>')
def descargar_excel(tabla):
    import pandas as pd
    from io import BytesIO
    from flask import send_file, request

    tabla_map = {
        "solicitudes": "historial_solicitudes",
        "devoluciones": "historial_devoluciones",
        "gastos": "registro_costos",
        "entradas": "historial_entradas",
        "inventario": "productos",
        "registro_horas": "registro_horas",
        "asignacion_personal": "asignacion_personal",
        "inventario_proyectos": None  # caso especial
    }

    if tabla not in tabla_map:
        return "Tabla no válida", 400

    centro_costo = request.args.get("centro_costo")
    conexion = obtener_conexion()

    # 🎯 CASO ESPECIAL INVENTARIO PROYECTOS
    if tabla == "inventario_proyectos":
        if not centro_costo or centro_costo.strip() == "":
            return "Debes seleccionar un centro de costo antes de descargar.", 400

        nombre_centro = centro_costo


        with conexion.cursor() as cursor:
            cursor.execute("""
                SELECT hs.producto_nombre,
                       COALESCE(SUM(hs.cantidad), 0) - COALESCE(SUM(hd.cantidad), 0) AS cantidad_actual,
                       MAX(hs.fecha_solicitud) AS ultima_solicitud
                FROM historial_solicitudes hs
                LEFT JOIN historial_devoluciones hd 
                    ON hs.producto_id = hd.producto_id AND hs.centro_costo = hd.centro_costo
                WHERE hs.centro_costo = %s
                GROUP BY hs.producto_nombre
            """, (nombre_centro,))
            datos = cursor.fetchall()

        conexion.close()

        df = pd.DataFrame(datos, columns=["producto_nombre", "cantidad_actual", "ultima_solicitud"])
        output = BytesIO()
        df.to_excel(output, index=False)
        output.seek(0)
        return send_file(output, download_name=f"inventario_{nombre_centro}.xlsx", as_attachment=True)

    # 📦 OTROS CASOS ESTÁNDAR
    base_query = f"SELECT * FROM {tabla_map[tabla]}"
    if tabla_map[tabla] in ["registro_horas", "registro_costos", "historial_solicitudes", "asignacion_personal"]:
        if not centro_costo or centro_costo.strip() == "":
            return "Debes seleccionar un centro de costo antes de descargar.", 400
        base_query += " WHERE centro_costo = %s"
        df = pd.read_sql(base_query, conexion, params=(centro_costo,))
        nombre = f"{tabla_map[tabla]}_{centro_costo}.xlsx"
    else:
        df = pd.read_sql(base_query, conexion)
        nombre = f"{tabla_map[tabla]}.xlsx"

    conexion.close()

    output = BytesIO()
    df.to_excel(output, index=False)
    output.seek(0)
    return send_file(output, download_name=nombre, as_attachment=True)

#####################################################################################################################################
@app.route('/logout')
def logout():
    session.pop('usuario', None)
    return redirect(url_for('login'))


if __name__ == '__main__':
    port = int(os.environ.get("PORT", 10000))  # Toma el puerto de la variable de entorno
    app.run(host="0.0.0.0", port=port)