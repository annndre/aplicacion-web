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
    "Cesar": {"password": "ADMINJCM", "rol": "admin", "rut": "16831221-0", "nombre": "Cesar", "apellido": "Hidalgo"},
    "Gonzalo": {"password": "ADMINJCM", "rol": "admin", "rut": "10383484-8", "nombre": "Gonzalo", "apellido": "Solis"},
    "Javier": {"password": "ADMINJCM", "rol": "admin", "rut": "15922965-3", "nombre": "Javier", "apellido": "Mundaca"},
    "andrea": {"password": "ADMINJCM", "rol": "admin", "rut": "20488630-k", "nombre": "Andrea", "apellido": "Cid"},
    "Mauricio": {"password": "MAURICIOJCM", "rol": "jefeB", "rut": "16156850-3", "nombre": "Mauricio", "apellido": "Matamala"},
    "Mariela": {"password": "MARIELAJCM", "rol": "bodega", "rut": "19745977-8", "nombre": "Mariela", "apellido": "MCManus"},
    "bodega": {"password": "bodega", "rol": "bodega"},
    "admin": {"password": "1234", "rol": "admin"},
    "Nicolas": {"password": "NICOLASJCM", "rol": "bodega", "rut": "19009768-4", "nombre": "Nicolas", "apellido": "Diaz"},
    "J.FUENTES": {"password": "J.FUENTESJCM", "rol": "jefeT", "rut": "15567862-3", "nombre": "Jonathan", "apellido": "Fuentes"},
    "J.HENRIQUEZ": {"password": "J.HENRIQUEZJCM", "rol": "jefeT", "rut": "16836181-5", "nombre": "Jorge", "apellido": "Henriquez"},
    "O.DIAZ": {"password": "O.DIAZJCM", "rol": "jefeT", "rut": "16455428-7", "nombre": "Oscar", "apellido": "Diaz"},
    "S.VILLAR": {"password": "S.VILLARJCM", "rol": "jefeT", "rut": "11745422-3", "nombre": "Sergio", "apellido": "Villar"},
    "jefe terreno": {"password": "JEFETERRENOJCM", "rol": "jefeT"},
    "S.VILLAR2": {"password": "S.VILLAR2", "rol": "jefeT", "rut": "20885308-2", "nombre": "Sergio", "apellido": "Villar"},
    "Juan": {"password": "ADMINJCM", "rol": "admin", "rut": "21018054-0", "nombre": "Juan", "apellido": "Anticoi"},
    "R.VILLAGRA": {"password": "R.VILLAGRAJCM", "rol": "supervisor", "rut": "11955538-8", "nombre": "Rafael", "apellido": "Villagra"},
    "R.VERGARA": {"password": "R.VERGARAJCM", "rol": "supervisor", "rut": "11457999-8", "nombre": "Reynaldo", "apellido": "Vergara"},
    "J.NORAMBUENA": {"password": "J.NORAMBUENAJCM", "rol": "supervisor", "rut": "19575396-2", "nombre": "Jaime", "apellido": "Norambuena"},
    "M.PENA": {"password": "M.PENAJCM", "rol": "conductor", "rut": "19386784-7", "nombre": "Matias", "apellido": "Peña"},
    "F.CANCINO": {"password": "F.CANCINOJCM", "rol": "conductor", "rut": "17147358-6", "nombre": "Francisco", "apellido": "Cancino"},
    "F.OLIVOS": {"password": "F.OLIVOSJCM", "rol": "conductor", "rut": "7373331-6", "nombre": "Fernando", "apellido": "Olivos"},

}

# Funciones Auxiliares
def obtener_datos_por_rut(rut_buscado):
    """
    Busca en el diccionario global el nombre amigable asociado al RUT.
    Devuelve un nombre y un apellido distintivo.
    """
    for login_user, datos in usuarios.items():
        if datos.get('rut') == rut_buscado:
            return datos.get('nombre', login_user), datos.get('apellido', '')
    
    return "Usuario", "No Mapeado"

@app.route('/', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        user = request.form['usuario']
        password = request.form['password']
        conexion = obtener_conexion()
        if conexion is None:
            flash('❌ Error de conexión con la base de datos.', 'danger')
            return redirect(url_for('login'))

        try:
            with conexion.cursor(cursor_factory=psycopg2.extras.DictCursor) as cursor:
                cursor.execute("SELECT * FROM usuarios WHERE usuario = %s AND contraseña = %s", (user, password))
                resultado = cursor.fetchone()

                if resultado:
                    session['usuario'] = resultado['usuario']
                    session['rol'] = resultado['rol']
                    session['rut'] = resultado['rut']

                    # --- NUEVO: CARGAR ESPECIALIDAD DESDE PGADMIN ---
                    cursor.execute("SELECT especialidad FROM jefe_especialidad WHERE usuario_jefe = %s", (user,))
                    esp_res = cursor.fetchone()
                    session['especialidad_a_cargo'] = esp_res['especialidad'] if esp_res else None

                    # Redirecciones
                    if session['rol'] == 'admin': return redirect(url_for('dashboard'))
                    if session['rol'] in ['jefeT', 'jefeB', 'supervisor']: return redirect(url_for('gestion_flota'))
                    if session['rol'] == 'conductor': return redirect(url_for('inspeccion_vehiculo'))
                    if session['rol'] == 'bodega': return redirect(url_for('solicitudes'))
                    return redirect(url_for('resultado_hh'))
        except Exception as e:
            flash(f'Error crítico: {e}', 'danger')
        finally:
            if conexion: conexion.close()
        
        flash('Credenciales incorrectas', 'danger')
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
            cursor.execute("""
                SELECT producto_nombre, estado, precio_unitario, marca, n_serie, categoria
                FROM productos
                WHERE id = %(id)s
            """, {'id': producto_id})
            producto = cursor.fetchone()

            if not producto:
                flash('Producto no encontrado.', 'error')
                return redirect(url_for('solicitudes'))

            producto_nombre = producto['producto_nombre']
            estado_producto = producto['estado']
            precio_unitario = producto['precio_unitario']
            marca = producto['marca']
            n_serie = producto['n_serie']
            categoria = producto['categoria']

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
            'precio': total_precio,
            'marca': marca,
            'n_serie': n_serie,
            'categoria': categoria
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

@app.route('/obtener_rut_solicitante')
def obtener_rut_solicitante():
    # Obtenemos el texto ingresado y lo limpiamos
    busqueda = request.args.get('nombre', '').strip()
    if not busqueda:
        return jsonify({'rut': ''})

    # Dividimos lo ingresado en palabras para buscar cada una
    partes = busqueda.split()
    
    conexion = obtener_conexion()
    try:
        with conexion.cursor(cursor_factory=psycopg2.extras.DictCursor) as cursor:
            # Creamos una búsqueda flexible: cada palabra debe estar presente
            # en la unión de nombre + apellido
            query = """
                SELECT rut 
                FROM personal 
                WHERE (COALESCE(nombre, '') || ' ' || COALESCE(apellido, '')) ILIKE %s
                ORDER BY (nombre || ' ' || apellido) ASC
                LIMIT 1
            """
            
            # Formateamos la búsqueda para que busque "MIGUEL%ROJAS%" 
            # Esto permite saltarse segundos nombres intermedios
            termino_busqueda = "%" + "%".join(partes) + "%"
            
            cursor.execute(query, (termino_busqueda,))
            resultado = cursor.fetchone()
            
            if resultado:
                return jsonify({'rut': resultado['rut']})
    except Exception as e:
        print(f"Error en autocompletado: {e}")
    finally:
        conexion.close()
    
    return jsonify({'rut': ''})

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
                    cursor.execute(
                        "SELECT stock_disponible, stock_critico FROM productos WHERE id = %(id)s",
                        {'id': item['producto_id']}
                    )
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
                        (nombre_solicitante, rut_solicitante, producto_id, producto_nombre, marca, n_serie, categoria, cantidad, centro_costo, motivo, usuario, precio)
                        VALUES (%(nombre_solicitante)s, %(rut_solicitante)s, %(producto_id)s, %(producto_nombre)s, %(marca)s, %(n_serie)s, %(categoria)s, %(cantidad)s, %(centro_costo)s, %(motivo)s, %(usuario)s, %(precio)s)
                    """, {
                        'nombre_solicitante': datos['nombre_solicitante'],
                        'rut_solicitante': datos['rut_solicitante'],
                        'producto_id': item['producto_id'],
                        'producto_nombre': item['producto_nombre'],
                        'marca': item.get('marca'),
                        'n_serie': item.get('n_serie'),
                        'categoria': item.get('categoria'),
                        'cantidad': item['cantidad'],
                        'centro_costo': item['centro_costo'],
                        'motivo': item['motivo'],
                        'usuario': usuario,
                        'precio': item['precio'],
                    })

                    print("DEBUG MOTIVO:", item.get('motivo'))

                    if item['motivo'] == 'devolucion':
                        print("Insertando en devoluciones_pendientes:", item)
                        cursor.execute("""
                            INSERT INTO devoluciones_pendientes 
                            (nombre_solicitante, rut_solicitante, producto_id, producto_nombre, cantidad, centro_costo, motivo, usuario, marca, n_serie, categoria)
                            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                        """, (
                            datos['nombre_solicitante'],
                            datos['rut_solicitante'],
                            item['producto_id'],
                            item['producto_nombre'],
                            item['cantidad'],
                            item['centro_costo'],
                            item['motivo'],
                            usuario,
                            item.get('marca'),
                            item.get('n_serie'),
                            item.get('categoria')
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
        solicitud=datos,
        alertas_stock_critico=alertas_stock_critico if 'alertas_stock_critico' in locals() else []
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
                SELECT id, nombre_solicitante, rut_solicitante, producto_id, producto_nombre, cantidad, fecha, centro_costo, marca, n_serie
                FROM devoluciones_pendientes
                WHERE rut_solicitante = %s
                ORDER BY fecha DESC
            """, (rut,))
        else:
            cursor.execute("""
                SELECT id, nombre_solicitante, rut_solicitante, producto_id, producto_nombre, cantidad, fecha, centro_costo, marca, n_serie
                FROM devoluciones_pendientes
                ORDER BY fecha DESC
            """)

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
                # Insertar en historial_devoluciones con centro_costo, marca y n_serie
                cursor.execute("""
                    INSERT INTO historial_devoluciones 
                    (nombre_devolutor, rut_devolutor, producto_id, producto_nombre, cantidad, fecha_devolucion, usuario, centro_costo, marca, n_serie)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """, (
                    devolucion['nombre_solicitante'],
                    devolucion['rut_solicitante'],
                    devolucion['producto_id'],
                    devolucion['producto_nombre'],
                    devolucion['cantidad'],
                    devolucion['fecha'],
                    usuario_actual,
                    devolucion['centro_costo'],
                    devolucion.get('marca'),
                    devolucion.get('n_serie')
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
    if 'usuario' not in session or session.get('rol') not in ['admin', 'bodega', 'jefeB']:
        flash("No tienes acceso a esta página", "danger")
        return redirect(url_for('login'))

    conexion = obtener_conexion()
    with conexion.cursor(cursor_factory=psycopg2.extras.DictCursor) as cursor:
        cursor.execute("SELECT id, producto_nombre, stock_disponible, unidad, categoria FROM productos")
        inventario = cursor.fetchall()
        cursor.execute("SELECT id_proyecto, nombre_proyecto FROM centros_costo ORDER BY id_proyecto")
        proyectos = cursor.fetchall()

    if 'entrada_temporal' not in session:
        session['entrada_temporal'] = {
            'productos': [],
            'numero_orden': '',
            'numero_guia': '',
            'numero_factura': '',
            'id_proyecto': 'BOD'
        }

    if request.method == 'POST':
        if 'agregar_producto' in request.form:
            # --- 1. CAPTURA DE DATOS (Solución al NameError) ---
            session['entrada_temporal']['numero_orden'] = request.form.get('numero_orden', '').strip()
            session['entrada_temporal']['numero_guia'] = request.form.get('numero_guia', '').strip()
            session['entrada_temporal']['numero_factura'] = request.form.get('numero_factura', '').strip()
            session['entrada_temporal']['id_proyecto'] = request.form.get('id_proyecto', 'BOD')

            producto_id_form = request.form.get('producto_id')
            producto_nombre = request.form.get('producto_nombre', '').strip()
            unidad = request.form.get('unidad', '').strip()
            categoria = request.form.get('categoria', '').strip()
            marca = request.form.get('marca', '').strip()
            n_serie = request.form.get('n_serie', '').strip()

            try:
                cantidad = int(request.form.get('cantidad', 0))
                precio_unitario = int(request.form.get('precio_unitario', 0))
            except ValueError:
                flash("⚠️ La cantidad y el precio unitario deben ser números válidos.", "error")
                return redirect(url_for('entradas'))

            if not producto_nombre or cantidad <= 0:
                flash('⚠️ Error: Debes ingresar un nombre de producto y una cantidad válida.', 'error')
                return redirect(url_for('entradas'))

            # --- 2. LÓGICA DE CENTRO DE COSTO ---
            id_p = session['entrada_temporal']['id_proyecto']
            nombre_p = next((p['nombre_proyecto'] for p in proyectos if str(p['id_proyecto']) == id_p), "BODEGA")
            centro_final = f"{id_p} - {nombre_p}" if id_p != "BOD" else "EN BODEGA"

            # --- 3. PROCESAMIENTO EN BASE DE DATOS ---
            with conexion.cursor(cursor_factory=psycopg2.extras.DictCursor) as cursor:
                if n_serie or not producto_id_form:
                    cursor.execute("""
                        INSERT INTO productos (producto_nombre, stock_disponible, unidad, categoria, precio_unitario, marca, n_serie, centro_costo)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s) RETURNING id
                    """, (producto_nombre, cantidad, unidad, categoria, precio_unitario, marca, n_serie, centro_final))
                    producto_id = cursor.fetchone()[0]
                    conexion.commit()
                    es_nuevo = True
                else:
                    producto_id = int(producto_id_form)
                    es_nuevo = False

            # --- 4. AGREGAR A LA LISTA TEMPORAL ---
            session['entrada_temporal']['productos'].append({
                'producto_id': producto_id, 
                'producto_nombre': producto_nombre,
                'cantidad': cantidad, 
                'precio_unitario': precio_unitario,
                'centro_costo': centro_final, 
                'es_nuevo': es_nuevo,
                'unidad': unidad, 
                'categoria': categoria, 
                'marca': marca, 
                'n_serie': n_serie
            })
            session.modified = True
            flash(f'✅ {producto_nombre} agregado correctamente.', 'success')
            return redirect(url_for('entradas'))

        elif 'confirmar_entrada' in request.form:
            # --- MEJORA: BLOQUE DE CONFIRMACIÓN CORREGIDO ---
            try:
                usuario = session.get('usuario', 'Desconocido')
                n_orden = session['entrada_temporal'].get('numero_orden')
                n_guia = session['entrada_temporal'].get('numero_guia')
                n_factura = session['entrada_temporal'].get('numero_factura')

                with conexion.cursor(cursor_factory=psycopg2.extras.DictCursor) as cursor:
                    for producto in session['entrada_temporal']['productos']:
                        # 1. Actualizar stock y centro_costo en productos existentes
                        if not producto.get('es_nuevo'):
                            cursor.execute("""
                                UPDATE productos 
                                SET stock_disponible = stock_disponible + %s, 
                                    precio_unitario = %s, 
                                    centro_costo = %s 
                                WHERE id = %s
                            """, (producto['cantidad'], producto['precio_unitario'], 
                                  producto['centro_costo'], producto['producto_id']))

                        # 2. Registrar en historial permanente con el Centro de Costo
                        cursor.execute("""
                            INSERT INTO historial_entradas (
                                numero_orden, numero_guia, numero_factura, producto_id, 
                                producto_nombre, cantidad, unidad, categoria, precio_unitario, 
                                marca, n_serie, usuario, fecha_entrada, centro_costo
                            ) 
                            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, CURRENT_DATE, %s)
                        """, (
                            n_orden, n_guia, n_factura, producto['producto_id'], 
                            producto['producto_nombre'], producto['cantidad'], 
                            producto['unidad'], producto['categoria'], 
                            producto['precio_unitario'], producto['marca'], 
                            producto['n_serie'], usuario, producto['centro_costo']
                        ))

                conexion.commit()
                session.pop('entrada_temporal', None)
                session.modified = True
                flash('✅ Entrada registrada y historial actualizado correctamente.', 'success')
                return redirect(url_for('entradas'))

            except Exception as e:
                flash(f"❌ Error al confirmar la entrada: {str(e)}", "error")
                return redirect(url_for('entradas'))

    # Historial ordenado para la vista web
    with conexion.cursor(cursor_factory=psycopg2.extras.DictCursor) as cursor:
        cursor.execute("SELECT * FROM historial_entradas ORDER BY fecha_entrada ASC, id ASC")
        historial_completo = cursor.fetchall()

    return render_template('entradas.html', inventario=inventario, proyectos=proyectos, 
                           historial_entradas=historial_completo, datos=session['entrada_temporal'], 
                           productos_temporales=session['entrada_temporal']['productos'],
                           mostrar_descarga=True, url_descarga="/descargar_excel/entradas")
                
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
        cursor.execute("""
            SELECT p.id,
                   p.producto_nombre,
                   p.n_serie,
                   p.marca,
                   p.stock_disponible,
                   p.unidad,
                   p.stock_critico,
                   p.categoria,
                   p.estado,
                   p.precio_unitario,
                   COALESCE(hs.ultimo_centro_costo, 'EN BODEGA') AS centro_costo
            FROM productos p
            LEFT JOIN (
                SELECT DISTINCT ON (producto_id) producto_id,
                        centro_costo AS ultimo_centro_costo
                FROM historial_solicitudes
                ORDER BY producto_id, fecha_solicitud DESC
            ) hs ON p.id = hs.producto_id
            ORDER BY p.id ASC
        """)

        inventario = cursor.fetchall()

        cursor.execute("SELECT DISTINCT categoria FROM productos ORDER BY categoria")
        categorias = [row[0] for row in cursor.fetchall()]

        cursor.execute("SELECT DISTINCT centro_costo FROM historial_solicitudes")
        centros_costo = [row[0] for row in cursor.fetchall()]

        if centro_seleccionado:
            # 🎯 BLOQUE ACTUALIZADO: Carga el detalle de 'devoluciones_pendientes'
            # Esto se alinea con el cambio realizado en inventario.html para mostrar los detalles
            cursor.execute("""
                SELECT producto_nombre, n_serie, marca, cantidad, fecha, motivo, nombre_solicitante
                FROM devoluciones_pendientes
                WHERE centro_costo = %s
                ORDER BY fecha DESC
            """, (centro_seleccionado,))
            inventario_centro = cursor.fetchall()
            #  fin del bloque actualizado

        # ✅ BLOQUE MODIFICADO: Búsqueda por Nombre O N° de Serie en Centros de Costo (TAB 2)
        if producto_buscado:
            busqueda_patron = f"%{producto_buscado}%" # Define el patrón para usarlo dos veces

            cursor.execute("""
                SELECT hs.centro_costo,
                       hs.producto_nombre,
                       p.n_serie, -- Añadido N° de Serie
                       COALESCE(SUM(hs.cantidad), 0) - COALESCE(SUM(hd.cantidad), 0) AS cantidad_actual,
                       MAX(hs.fecha_solicitud) AS ultima_solicitud
                FROM historial_solicitudes hs
                
                JOIN productos p ON hs.producto_id = p.id -- Necesario para acceder a p.n_serie
                
                LEFT JOIN historial_devoluciones hd 
                    ON hs.producto_id = hd.producto_id AND hs.centro_costo = hd.centro_costo
                    
                -- Lógica de búsqueda flexible: busca en Nombre O N° de Serie
                WHERE hs.producto_nombre ILIKE %s OR p.n_serie::text ILIKE %s
                
                -- Se añade p.n_serie al GROUP BY
                GROUP BY hs.centro_costo, hs.producto_nombre, p.n_serie
            """, (busqueda_patron, busqueda_patron,)) # Se pasa el patrón dos veces
            
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
@app.route('/editar_precio_producto', methods=['POST'])
def editar_precio_producto():
    if 'usuario' not in session or session.get('rol') not in ['admin', 'jefeB', 'bodega']:
        flash("No tienes permiso para editar precios", "danger")
        return redirect(url_for('ver_inventario'))

    producto_id = request.form.get('producto_id')
    nuevo_precio = request.form.get('nuevo_precio')

    try:
        nuevo_precio = float(nuevo_precio)
    except ValueError:
        flash("El precio debe ser un número válido", "warning")
        return redirect(url_for('ver_inventario'))

    conexion = obtener_conexion()
    with conexion.cursor() as cursor:
        cursor.execute("""
            UPDATE productos
            SET precio_unitario = %s
            WHERE id = %s
        """, (nuevo_precio, producto_id))
        conexion.commit()

    flash("Precio actualizado correctamente", "success")
    return redirect(url_for('ver_inventario'))

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
from datetime import datetime, timedelta, date

@app.route('/control_gastos', methods=['GET', 'POST'])
def control_gastos():
    if 'usuario' not in session or session.get('rol') not in ['admin', 'jefeT', 'bodega']:
        flash("No tienes acceso a esta página", "danger")
        return redirect(url_for('login'))

    # Inicializar lista temporal en la sesión si no existe
    if 'gastos_temporales' not in session:
        session['gastos_temporales'] = []

    conexion = obtener_conexion()
    centros_costo = []
    rol_usuario = session.get('rol')
    rut_usuario = session.get('rut')

    with conexion.cursor(cursor_factory=psycopg2.extras.DictCursor) as cursor:
        if rol_usuario == 'admin':
            cursor.execute("SELECT DISTINCT centro_costo FROM asignacion_personal ORDER BY centro_costo")
        else:
            # Normalización de RUT para asegurar coincidencia en la consulta
            cursor.execute("""
                SELECT DISTINCT centro_costo FROM asignacion_personal 
                WHERE REPLACE(REPLACE(rut, '.', ''), ' ', '') = REPLACE(REPLACE(%s, '.', ''), ' ', '')
                ORDER BY centro_costo
            """, (rut_usuario,))
        centros_costo = [row['centro_costo'] for row in cursor.fetchall()]

    # ACCIÓN 1: Agregar a la Vista Previa (Temporal)
    if request.method == 'POST' and 'agregar_a_vista_previa' in request.form:
        monto_raw = request.form.get('monto_registro', '').strip()
        
        # Mejora: Validación y conversión a float para evitar errores NaN en Excel
        try:
            monto_valor = float(monto_raw) if monto_raw else 0.0
        except ValueError:
            flash("⚠️ El monto debe ser un valor numérico válido.", "error")
            return redirect(url_for('control_gastos'))

        nuevo_gasto = {
            'centro_costo': request.form.get('centro_costo', '').strip(),
            'categoria': request.form.get('categoria', '').strip(),
            'fecha': request.form.get('fecha_factura', '').strip(),
            'tipo_documento': request.form.get('tipo_documento', '').strip(),
            'numero_documento': request.form.get('numero_factura', '').strip(),
            'registro_compra': request.form.get('registro_compra', '').strip(),
            'tipo_pago': request.form.get('tipo_pago', '').strip(),
            'monto_registro': monto_valor, # Sincronizado con la columna de la DB
            'usuario': session.get('usuario')
        }

        if not nuevo_gasto['centro_costo'] or not nuevo_gasto['categoria']:
            flash("⚠️ Campos obligatorios faltantes (Centro de Costo y Categoría).", "error")
        else:
            session['gastos_temporales'].append(nuevo_gasto)
            session.modified = True
            flash("📝 Gasto agregado a la vista previa.", "info")
        return redirect(url_for('control_gastos'))

    # ACCIÓN 2: Confirmar y Subir definitivamente a la Base de Datos
    if request.method == 'POST' and 'confirmar_subida_definitiva' in request.form:
        if not session.get('gastos_temporales'):
            flash("⚠️ No hay datos en la vista previa para subir.", "warning")
            return redirect(url_for('control_gastos'))

        try:
            with conexion.cursor() as cursor:
                for gasto in session['gastos_temporales']:
                    # Inserción en registro_costos
                    cursor.execute("""
                        INSERT INTO registro_costos (
                            centro_costo, categoria, fecha, tipo_documento,
                            numero_documento, registro_compra, monto_registro, usuario, tipo_pago
                        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """, (gasto['centro_costo'], gasto['categoria'], gasto['fecha'] or None, 
                          gasto['tipo_documento'], gasto['numero_documento'] or None, 
                          gasto['registro_compra'], gasto['monto_registro'], 
                          gasto['usuario'], gasto['tipo_pago']))

                    # Sincronización con tabla facturaOC para documentos tributarios
                    if gasto['tipo_documento'].lower() in ['factura', 'orden de compra'] and gasto['numero_documento']:
                        cursor.execute("""
                            INSERT INTO facturaOC (numero_factura, fecha_factura, monto_factura, origen)
                            VALUES (%s, %s, %s, %s)
                        """, (gasto['numero_documento'], gasto['fecha'], gasto['monto_registro'], 'control_gastos'))

                conexion.commit()
                session.pop('gastos_temporales', None)
                flash("✅ Registros procesados exitosamente en la base de datos.", "success")
        except Exception as e:
            if conexion: conexion.rollback()
            flash(f"❌ Error al procesar la subida: {str(e)}", "danger")
        finally:
            if conexion: conexion.close()
        return redirect(url_for('control_gastos'))

    # Carga de datos para renderizar la vista
    try:
        with conexion.cursor(cursor_factory=psycopg2.extras.DictCursor) as cursor:
            cursor.execute("SELECT * FROM registro_costos ORDER BY fecha DESC LIMIT 50")
            gastos_guardados = cursor.fetchall()
            cursor.execute("SELECT DISTINCT categoria FROM clasificacion_costos ORDER BY categoria ASC")
            categorias = cursor.fetchall()
    finally:
        if conexion: conexion.close()

    return render_template(
        'control_gastos.html',
        historial_adquisiciones=gastos_guardados,
        gastos_temporales=session.get('gastos_temporales', []),
        centros_costo=centros_costo,
        categorias=categorias,
        mostrar_descarga=True,
        url_descarga="/descargar_excel/gastos"
    )
    
#################################
@app.route('/eliminar_gasto_temporal/<int:index>')
def eliminar_gasto_temporal(index):
    if 'gastos_temporales' in session:
        try:
            # Elimina el registro por su posición en la lista
            session['gastos_temporales'].pop(index)
            session.modified = True
            flash("🗑️ Registro eliminado de la vista previa.", "info")
        except IndexError:
            flash("⚠️ No se pudo encontrar el registro a eliminar.", "error")
    return redirect(url_for('control_gastos'))

#################################
@app.route('/guardar_cambios_planilla', methods=['POST'])
def guardar_cambios_planilla():
    if 'gastos_temporales' in session:
        for i in range(len(session['gastos_temporales'])):
            session['gastos_temporales'][i]['centro_costo'] = request.form.get(f'centro_{i}')
            session['gastos_temporales'][i]['fecha'] = request.form.get(f'fecha_{i}')
            session['gastos_temporales'][i]['tipo_documento'] = request.form.get(f'tipo_{i}')
            session['gastos_temporales'][i]['numero_documento'] = request.form.get(f'numero_{i}')
            session['gastos_temporales'][i]['registro_compra'] = request.form.get(f'desc_{i}')
            session['gastos_temporales'][i]['tipo_pago'] = request.form.get(f'pago_{i}')
            
            # Mejora: Conversión segura para edición manual evitando NaNs
            monto_editado = request.form.get(f'monto_{i}')
            try:
                session['gastos_temporales'][i]['monto_registro'] = float(monto_editado) if monto_editado else 0.0
            except ValueError:
                session['gastos_temporales'][i]['monto_registro'] = 0.0
        
        session.modified = True
        flash("💾 Vista previa actualizada correctamente.", "success")
    return redirect(url_for('control_gastos'))
#####################################################################################################
# RUTA PARA ASIGNAR PERSONAL
def limpiar_rut(rut):
    return rut.replace('.', '').replace(' ', '').replace('\n', '').replace('\r', '').strip()

def limpiar_texto(texto):
    return texto.replace('\n', ' ').replace('\r', ' ').strip()
@app.route('/asignar_personal', methods=['GET', 'POST']) 
def asignar_personal():
    if 'usuario' not in session or session.get('rol') not in ['admin', 'jefeT']:
        flash("No tienes acceso a esta página", "danger")
        return redirect(url_for('login'))

    conexion = obtener_conexion()

    def limpiar_rut(rut):
        return rut.replace('.', '').replace(' ', '').replace('\n', '').replace('\r', '').strip()

    if request.method == 'POST':
        usuario = session.get('usuario')

        # ➕ Agregar nuevo personal
        if 'agregar_personal' in request.form:
            nuevo_nombre = limpiar_texto(request.form.get('nuevo_nombre', ''))
            nuevo_apellido = limpiar_texto(request.form.get('nuevo_apellido', ''))
            nuevo_rut = limpiar_rut(request.form.get('nuevo_rut', ''))
            nuevo_especialidad = limpiar_texto(request.form.get('nuevo_especialidad', ''))
            nuevo_rol = limpiar_texto(request.form.get('nuevo_rol', ''))
            nuevo_genero = limpiar_texto(request.form.get('nuevo_genero', ''))
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

        # 📌 Asignar personal a múltiples centros
        elif 'confirmar_asignacion' in request.form:
            centros_seleccionados = request.form.getlist('centros_costo')
            personas_seleccionadas = request.form.getlist('seleccionados')

            if not centros_seleccionados or not personas_seleccionadas:
                flash("⚠️ Debes seleccionar al menos una persona y un centro de costo.", "warning")
                return redirect(url_for('asignar_personal'))

            with conexion.cursor() as cursor:
                for dato in personas_seleccionadas:
                    rut, nombre, apellido, rol = [d.strip() for d in dato.split('|')]
                    rut = limpiar_rut(rut)
                    for centro in centros_seleccionados:
                        cursor.execute("""
                            SELECT 1 FROM asignacion_personal
                            WHERE rut = %s AND centro_costo = %s
                        """, (rut, centro))
                        existe = cursor.fetchone()
                        if not existe:
                            cursor.execute("""
                                INSERT INTO asignacion_personal (nombre, apellido, rut, rol, centro_costo, asignado_por)
                                VALUES (%s, %s, %s, %s, %s, %s)
                            """, (nombre, apellido, rut, rol, centro, usuario))
            conexion.commit()
            flash("✅ Personal asignado correctamente a los centros seleccionados.", "success")
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

        if rol_usuario in ['jefeT']:
            cursor.execute("""
                SELECT centro_costo, COUNT(*) as cantidad
                FROM asignacion_personal
                WHERE rut = %s
                GROUP BY centro_costo
                ORDER BY centro_costo
            """, (rut_usuario,))
        else:
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
@app.route('/eliminar_personal/<rut>', methods=['POST'])
def eliminar_personal(rut):
    if 'usuario' not in session or session.get('rol') not in ['admin','jefeT']:
        flash("No tienes acceso a esta función", "danger")
        return redirect(url_for('login'))

    conexion = obtener_conexion()
    try:
        with conexion.cursor() as cursor:
            cursor.execute("DELETE FROM personal WHERE rut = %s", (rut,))
        conexion.commit()
        flash("✅ Personal eliminado correctamente.", "success")
    except Exception as e:
        flash(f"❌ Error al eliminar: {str(e)}", "danger")
    return redirect(url_for('asignar_personal'))

##################################################################################################################
@app.route('/registro_horas', methods=['GET', 'POST'])
def registro_horas():
    # 1. Verificación de Autenticación
    if 'usuario' not in session or session.get('rol') not in ['admin', 'jefeT', 'jefeB']:
        flash("No tienes acceso a esta página", "danger")
        return redirect(url_for('login'))

    conexion = obtener_conexion()
    if conexion is None:
        flash("❌ No se pudo conectar a la base de datos", "danger")
        return redirect(url_for('login'))

    # Contexto del usuario logueado
    usuario_login = session.get('usuario')
    rut_usuario = session.get('rut')
    rol_usuario = session.get('rol')
    # Especialidad obtenida durante el login (desde tabla jefe_especialidad)
    especialidad_jefe = session.get('especialidad_a_cargo')

    trabajadores = []
    semana_actual = ''
    centro_costo_actual = ''
    fechas_por_dia = {}
    resumen = {}
    valores_guardados = {}
    centros_costo = []

    # --- CARGA DE CENTROS DE COSTO SEGÚN ROL ---
    with conexion.cursor() as cursor:
        if rol_usuario == 'admin':
            cursor.execute("SELECT DISTINCT centro_costo FROM asignacion_personal ORDER BY centro_costo")
        else:
            cursor.execute("SELECT DISTINCT centro_costo FROM asignacion_personal WHERE rut = %s ORDER BY centro_costo", (rut_usuario,))
        centros_costo = [row[0] for row in cursor.fetchall()]

    if request.method == 'POST':
        if 'guardar_semana' in request.form:
            semana = request.form.get('semana', '').strip()
            centro_costo = request.form.get('centro_costo', '').strip()

            if semana:
                year, week = semana.split('-W')
                primer_dia = datetime.fromisocalendar(int(year), int(week), 1)
                dias = ['lun', 'mar', 'mie', 'jue', 'vie', 'Sab', 'dom']
                for i, d in enumerate(dias):
                    fechas_por_dia[d] = (primer_dia + timedelta(days=i)).strftime('%Y-%m-%d')

            dia_a_guardar = request.form.get('dia_a_guardar', '').strip().lower()
            fecha_real = fechas_por_dia.get(dia_a_guardar)
            hoy = date.today()

            if not fecha_real:
                flash("⚠️ Día no válido", "warning")
                return redirect(url_for('registro_horas'))

            # Validación de temporalidad (Semana actual y 4 anteriores)
            fecha_real_dt = datetime.strptime(fecha_real, '%Y-%m-%d').date()
            semana_actual_dt = hoy.isocalendar().week
            semana_objetivo = fecha_real_dt.isocalendar().week
            año_actual = hoy.isocalendar().year
            año_objetivo = fecha_real_dt.isocalendar().year

            #if año_actual != año_objetivo:
            #    flash("⚠️ Solo se pueden editar semanas dentro del año actual.", "warning")
            #    return redirect(url_for('registro_horas'))
            
            #if semana_objetivo < semana_actual_dt - 4 or fecha_real_dt > hoy:
            #    flash("⚠️ Solo se pueden editar la semana actual y las 4 anteriores.", "warning")
            #    return redirect(url_for('registro_horas'))

            mensaje_mostrado = False
            with conexion.cursor(cursor_factory=psycopg2.extras.DictCursor) as cursor:
                
                # --- MEJORA: FILTRADO POR ESPECIALIDAD ---
                if rol_usuario == 'jefeT' and especialidad_jefe:
                    query_pers = """
                        SELECT a.rut, a.nombre, a.apellido 
                        FROM asignacion_personal a
                        JOIN personal p ON a.rut = p.rut
                        WHERE a.centro_costo = %s 
                        AND (p.especialidad = %s OR p.rol = 'Prevencionista')
                    """
                    cursor.execute(query_pers, (centro_costo, especialidad_jefe))
                else:
                    cursor.execute("SELECT rut, nombre, apellido FROM asignacion_personal WHERE centro_costo = %s", (centro_costo,))
                
                personas = cursor.fetchall()

                for persona in personas:
                    rut = persona['rut'].strip()
                    nombre = persona['nombre'].strip()
                    apellido = persona['apellido'].strip()

                    hn_key = f'hn_{rut}_{dia_a_guardar}'
                    he_key = f'he_{rut}_{dia_a_guardar}'

                    if hn_key not in request.form:
                        continue

                    hn_val = request.form.get(hn_key, '').strip().upper()
                    he_val = request.form.get(he_key, '').strip()
                    observacion = None
                    observacionP = None

                    try:
                        # Manejo de estados (L, V, F, P, D)
                        if hn_val in ['L', 'V', 'F', 'P', 'D']:
                            horas_normales = 0
                            observacion = hn_val
                            if hn_val == 'P':
                                tp = request.form.get(f'tipo_permiso_{rut}_{dia_a_guardar}', '').strip()
                                rp = request.form.get(f'razon_permiso_{rut}_{dia_a_guardar}', '').strip()
                                observacionP = f"{tp} - {rp}" if tp and rp else (tp or rp or None)
                        elif hn_val == '':
                            horas_normales = 0
                        else:
                            horas_normales = round(float(hn_val.replace(',', '.')), 1)
                            if horas_normales < 0 or horas_normales > 24:
                                flash(f"⚠️ Horas normales inválidas para {rut}", "warning")
                                continue

                        # --- MEJORA: CONTROL CRÍTICO 9 HH TOTALES ---
                        # Sumamos horas registradas en OTROS centros para el mismo día
                        cursor.execute("""
                            SELECT SUM(horas_normales)
                            FROM registro_horas
                            WHERE rut = %s AND horas_fecha = %s AND centro_costo != %s
                        """, (rut, fecha_real, centro_costo))
                        total_previas = cursor.fetchone()[0] or 0

                        if (float(total_previas) + horas_normales) > 9.0:
                            flash(f"🚨 BLOQUEO: {nombre} {apellido} ya registra {total_previas}h en otros centros. No se puede exceder el límite legal de 9h.", "danger")
                            continue 
                        # --- FIN MEJORA ---

                        horas_extras = int(he_val) if he_val != '' else 0
                        dias_trabajados = 1 if observacion == 'V' else round(horas_normales / 9, 1) if horas_normales else 0

                        # Guardado o Actualización (Upsert)
                        cursor.execute("SELECT 1 FROM registro_horas WHERE horas_fecha = %s AND centro_costo = %s AND rut = %s", (fecha_real, centro_costo, rut))
                        if cursor.fetchone():
                            cursor.execute("""
                                UPDATE registro_horas SET horas_normales = %s, horas_extras = %s, observacion = %s, 
                                observacionP = %s, dias_trabajados = %s, usuario = %s
                                WHERE rut = %s AND horas_fecha = %s AND centro_costo = %s
                            """, (horas_normales, horas_extras, observacion, observacionP, dias_trabajados, usuario_login, rut, fecha_real, centro_costo))
                        else:
                            cursor.execute("""
                                INSERT INTO registro_horas (rut, nombre, apellido, centro_costo, horas_normales, horas_extras, 
                                horas_fecha, fecha_registro, usuario, observacion, dias_trabajados, observacionP)
                                VALUES (%s, %s, %s, %s, %s, %s, %s, CURRENT_DATE, %s, %s, %s, %s)
                            """, (rut, nombre, apellido, centro_costo, horas_normales, horas_extras, fecha_real, usuario_login, observacion, dias_trabajados, observacionP))

                        if not mensaje_mostrado:
                            flash("✅ Horas procesadas correctamente.", "success")
                            mensaje_mostrado = True

                    except ValueError:
                        flash(f"⚠️ Error en formato de horas para {rut}", "warning")

            conexion.commit()
            return redirect(url_for('registro_horas'))

        else:
            # --- LÓGICA DE VISUALIZACIÓN (GET / Cambio de Filtros) ---
            centro_costo_actual = request.form.get('centro_costo', '').strip()
            semana_actual = request.form.get('semana', '').strip()

            if semana_actual and centro_costo_actual:
                try:
                    year, week = semana_actual.split('-W')
                    primer_dia = datetime.fromisocalendar(int(year), int(week), 1).date()
                    domingo = primer_dia + timedelta(days=6)

                    dias_lista = ['lun', 'mar', 'mie', 'jue', 'vie', 'Sab', 'Dom']
                    for i, d in enumerate(dias_lista):
                        fechas_por_dia[d] = (primer_dia + timedelta(days=i)).strftime('%Y-%m-%d')

                    with conexion.cursor(cursor_factory=psycopg2.extras.DictCursor) as cursor:
                        # Visualización filtrada por Especialidad
                        if rol_usuario == 'jefeT' and especialidad_jefe:
                            cursor.execute("""
                                SELECT a.nombre, a.apellido, a.rut 
                                FROM asignacion_personal a
                                JOIN personal p ON a.rut = p.rut
                                WHERE a.centro_costo = %s AND p.especialidad = %s
                                ORDER BY a.nombre ASC
                            """, (centro_costo_actual, especialidad_jefe))
                        else:
                            cursor.execute("SELECT nombre, apellido, rut FROM asignacion_personal WHERE centro_costo = %s ORDER BY nombre ASC", (centro_costo_actual,))
                        
                        trabajadores = cursor.fetchall()

                        # Carga de registros guardados para poblar los inputs
                        cursor.execute("""
                            SELECT rut, horas_fecha, horas_normales, horas_extras, observacion
                            FROM registro_horas
                            WHERE centro_costo = %s AND horas_fecha BETWEEN %s AND %s
                        """, (centro_costo_actual, primer_dia, domingo))
                        registros = cursor.fetchall()

                        for r in registros:
                            rut, fecha, hn, he, obs = r['rut'], r['horas_fecha'], r['horas_normales'], r['horas_extras'], r['observacion']
                            for k, fecha_str in fechas_por_dia.items():
                                if fecha.strftime('%Y-%m-%d') == fecha_str:
                                    valores_guardados.setdefault(rut, {})[k] = {'hn': hn, 'he': he, 'observacion': obs}

                except Exception as e:
                    flash(f"⚠️ Error al procesar la vista: {e}", "danger")

    # Selección por defecto de centro de costo
    if not centro_costo_actual and centros_costo:
        centro_costo_actual = centros_costo[0]

    # Carga de Resumen del Centro
    if centro_costo_actual:
        with conexion.cursor() as cursor:
            cursor.execute("""
                SELECT MAX(horas_fecha) AS ultima_fecha,
                       SUM(COALESCE(horas_normales, 0) + COALESCE(horas_extras, 0)) AS total_horas
                FROM registro_horas
                WHERE centro_costo = %s AND horas_fecha <= CURRENT_DATE
            """, (centro_costo_actual,))
            fila = cursor.fetchone()
            resumen = {'ultima_fecha': fila[0], 'total_horas': fila[1] if fila[1] else 0}

    return render_template("registro_horas.html",
                            trabajadores=trabajadores,
                            semana=semana_actual,
                            centro_costo=centro_costo_actual,
                            centros_costo=centros_costo,
                            fechas_por_dia=fechas_por_dia,
                            resumen=resumen,
                            valores_guardados=valores_guardados)    

#########################################################################################
@app.route('/exportar_trabajador', methods=['POST'])
def exportar_trabajador():
    if 'usuario' not in session or session.get('rol') not in ['admin', 'jefeT']:
        return redirect(url_for('login'))

    rut = request.form.get('rut_trabajador')
    nueva_especialidad = request.form.get('nueva_especialidad')
    usuario_origen = session.get('usuario')

    conexion = obtener_conexion()
    try:
        with conexion.cursor(cursor_factory=psycopg2.extras.DictCursor) as cursor:
            # 1. Obtener nombre y especialidad actual
            cursor.execute("SELECT nombre, apellido, especialidad FROM personal WHERE rut = %s", (rut,))
            p = cursor.fetchone()
            if not p: return redirect(url_for('asignar_personal'))

            # 2. Actualizar Especialidad (Esto lo cambia de "jefe")
            cursor.execute("UPDATE personal SET especialidad = %s WHERE rut = %s", (nueva_especialidad, rut))
            
            # 3. Registrar en Historial (Notificación diferida)
            cursor.execute("""
                INSERT INTO historial_rotacion (rut, especialidad_anterior, nueva_especialidad, movido_por, fecha)
                VALUES (%s, %s, %s, %s, NOW())
            """, (rut, p['especialidad'], nueva_especialidad, usuario_origen))
            
            conexion.commit()
            flash(f"🔄 EXITOSO: {p['nombre']} {p['apellido']} ha sido exportado a {nueva_especialidad}.", "success")
    except Exception as e:
        flash(f"Error en la exportación: {e}", "danger")
    finally:
        if conexion: conexion.close()
    return redirect(url_for('asignar_personal'))

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
    import os

    # Mapeo de tablas para la base de datos
    tabla_map = {
        "solicitudes": "historial_solicitudes",
        "devoluciones": "historial_devoluciones",
        "gastos": "registro_costos",
        "entradas": "historial_entradas",
        "inventario": "productos",
        "registro_horas": "registro_horas",
        "asignacion_personal": "asignacion_personal",
        "devoluciones_pendientes": "devoluciones_pendientes",
        "inventario_proyectos": None
    }

    if tabla not in tabla_map:
        return "Tabla no válida", 400

    centro_costo = request.args.get("centro_costo")
    conexion = obtener_conexion()

    try:
        # Lógica de obtención de datos según el módulo
        if tabla == "inventario_proyectos":
            if not centro_costo:
                return "Debes seleccionar un centro de costo antes de descargar.", 400
            
            nombre_archivo = f"inventario_proyecto_{centro_costo.replace(' ', '_')}.xlsx"
            query = """
                SELECT id, nombre_solicitante, rut_solicitante, producto_id, producto_nombre, cantidad, 
                       centro_costo, motivo, usuario, fecha, marca, n_serie
                FROM devoluciones_pendientes
                WHERE centro_costo = %s ORDER BY fecha DESC
            """
            df = pd.read_sql(query, conexion, params=(centro_costo,))
        else:
            if tabla_map[tabla] in ["registro_horas", "registro_costos", "asignacion_personal"]:
                if not centro_costo:
                    return "Debes seleccionar un centro de costo antes de descargar.", 400
                query = f"SELECT * FROM {tabla_map[tabla]} WHERE centro_costo = %s"
                df = pd.read_sql(query, conexion, params=(centro_costo,))
                nombre_archivo = f"{tabla_map[tabla]}_{centro_costo.replace(' ', '_')}.xlsx"
            else:
                query = f"SELECT * FROM {tabla_map[tabla]}"
                df = pd.read_sql(query, conexion)
                nombre_archivo = f"{tabla_map[tabla]}.xlsx"
        
        # Limpieza de valores nulos para estabilidad del Excel
        df = df.fillna('')
    finally:
        conexion.close()

    # --- LÓGICA DE DISEÑO INSTITUCIONAL ---
    output = BytesIO()
    writer = pd.ExcelWriter(output, engine='xlsxwriter')
    
    # Escribir datos a partir de la fila 2 (índice 1)
    df.to_excel(writer, index=False, sheet_name='Reporte', startrow=1)
    
    workbook  = writer.book
    worksheet = writer.sheets['Reporte']

    # Definición de formatos
    formato_cuadricula = workbook.add_format({'border': 1, 'valign': 'vcenter'})
    # NOTA: formato_moneda se conserva por compatibilidad pero se prioriza write_number para "monto" y "precio"
    formato_moneda = workbook.add_format({'border': 1, 'num_format': '"$ "#,##0', 'align': 'right', 'valign': 'vcenter'})
    formato_fecha = workbook.add_format({'border': 1, 'num_format': 'dd-mm-yyyy', 'align': 'center', 'valign': 'vcenter'})
    formato_encabezado_tabla = workbook.add_format({'bold': True, 'border': 1, 'bg_color': '#D9D9D9', 'align': 'center', 'valign': 'vcenter'})
    formato_titulo = workbook.add_format({'bold': True, 'font_size': 14, 'align': 'center', 'valign': 'vcenter', 'font_color': '#D45D00'})

    # Aplicar formatos a las celdas de datos
    for r_idx in range(len(df)):
        for c_idx in range(len(df.columns)):
            valor = df.iloc[r_idx, c_idx]
            nombre_columna = str(df.columns[c_idx]).lower().strip()
            
            # --- MEJORA APLICADA: Detectar si inicia con 'precio' o 'monto' ---
            if (nombre_columna.startswith('precio') or nombre_columna.startswith('monto')) and valor != '':
                try:
                    # Se escribe como número puro sin el formato de moneda (símbolo $)
                    worksheet.write_number(r_idx + 2, c_idx, float(valor), formato_cuadricula)
                except:
                    worksheet.write(r_idx + 2, c_idx, valor, formato_cuadricula)
            
            # Formato de Fecha
            elif 'fecha' in nombre_columna and valor != '':
                try:
                    fecha_dt = pd.to_datetime(valor)
                    worksheet.write_datetime(r_idx + 2, c_idx, fecha_dt, formato_fecha)
                except:
                    worksheet.write(r_idx + 2, c_idx, valor, formato_cuadricula)
            
            # Formato General (Cuadriculado)
            else:
                worksheet.write(r_idx + 2, c_idx, valor, formato_cuadricula)

    # Escribir encabezados con formato gris (Fila 2)
    for c_idx, col_name in enumerate(df.columns):
        worksheet.write(1, c_idx, col_name, formato_encabezado_tabla)

    # Insertar Logo de la Empresa (Fila 1)
    ruta_logo = os.path.join(app.root_path, 'static', 'logo.png')
    if os.path.exists(ruta_logo):
        worksheet.insert_image('A1', ruta_logo, {'x_scale': 0.35, 'y_scale': 0.35, 'x_offset': 5, 'y_offset': 0})

    # Insertar Título Centrado (Fila 1)
    titulo_texto = f"REPORTE: {tabla.upper().replace('_', ' ')}"
    if len(df.columns) > 1:
        worksheet.merge_range(0, 1, 0, len(df.columns) - 1, titulo_texto, formato_titulo)

    # Ajustes finales de dimensiones
    worksheet.set_row(0, 30) 
    for i, col in enumerate(df.columns):
        max_len = max(df[col].astype(str).map(len).max(), len(col)) + 4
        worksheet.set_column(i, i, max_len)

    writer.close()
    output.seek(0)
    return send_file(output, download_name=nombre_archivo, as_attachment=True)

#####################################################################################################################################
@app.route('/resultado_hh', methods=['GET', 'POST'])
def resultado_hh():
    # 1. Verificación de sesión y conexión
    if 'usuario' not in session:
        flash("Debes iniciar sesión", "danger")
        return redirect(url_for('login'))

    conexion = obtener_conexion()
    centros_costo = []
    especialidades = []
    datos = []
    
    # Inicialización de variables para el template
    tipo_filtro = 'ninguno'
    fecha_filtro = None
    centro_costo_seleccionado = None
    especialidad_seleccionada = None

    try:
        # 2. Obtener listas de filtros disponibles
        with conexion.cursor() as cursor:
            cursor.execute("SELECT DISTINCT centro_costo FROM asignacion_personal ORDER BY centro_costo")
            centros_costo = [fila[0] for fila in cursor.fetchall()]

            cursor.execute("SELECT DISTINCT especialidad FROM personal WHERE especialidad IS NOT NULL ORDER BY especialidad")
            especialidades = [fila[0] for fila in cursor.fetchall()]
    except Exception as e:
        flash(f"Error al cargar filtros: {e}", "danger")
        return render_template('resultado_hh.html', centros_costo=[], especialidades=[])

    # 3. Manejo de la Solicitud POST (Filtro)
    if request.method == 'POST':
        tipo_filtro = request.form.get('tipo_filtro')
        fecha_filtro = request.form.get('fecha_filtro')
        centro_costo_seleccionado = request.form.get('centro_costo')
        especialidad_seleccionada = request.form.get('especialidad')

        # --- A. Lógica para manejar filtros de fecha ---
        condiciones_fecha = ""
        parametros_query = []

        if tipo_filtro and tipo_filtro != 'ninguno' and fecha_filtro:
            try:
                if tipo_filtro == 'semana':
                    anio, semana_num = map(int, fecha_filtro.split('-W'))
                    primer_dia = datetime.date.fromisocalendar(anio, semana_num, 1)
                    ultimo_dia = primer_dia + datetime.timedelta(days=6)
                    condiciones_fecha = "AND rh.horas_fecha BETWEEN %s AND %s"
                    parametros_query.extend([primer_dia, ultimo_dia])
                elif tipo_filtro == 'mes':
                    anio, mes = map(int, fecha_filtro.split('-'))
                    condiciones_fecha = "AND EXTRACT(YEAR FROM rh.horas_fecha) = %s AND EXTRACT(MONTH FROM rh.horas_fecha) = %s"
                    parametros_query.extend([anio, mes])
            except ValueError:
                flash("Formato de fecha inválido.", "warning")
                return redirect(url_for('resultado_hh'))

        # --- B. Ejecución de la Consulta con Filtros Dinámicos Combinados ---
        try:
            with conexion.cursor(cursor_factory=psycopg2.extras.DictCursor) as cursor:
                # Base de la query: Siempre unimos Personal con Registro_Horas
                # El WHERE 1=1 permite añadir condiciones dinámicamente
                query = f"""
                    SELECT p.nombre, p.apellido, p.rut, p.pago_hora,
                        COALESCE(SUM(CASE WHEN rh.horas_normales > 0 THEN rh.horas_normales ELSE 0 END), 0) AS total_hn,
                        COALESCE(SUM(CASE WHEN rh.horas_extras > 0 THEN rh.horas_extras ELSE 0 END), 0) AS total_he,
                        COALESCE(COUNT(DISTINCT rh.horas_fecha) FILTER (WHERE rh.horas_normales > 0 OR rh.horas_extras > 0), 0) AS dias_trabajados,
                        COUNT(*) FILTER (WHERE rh.observacion ILIKE 'L') AS licencias,
                        COUNT(*) FILTER (WHERE rh.observacion ILIKE 'P') AS permisos,
                        COUNT(*) FILTER (WHERE rh.observacion ILIKE 'F') AS fallas,
                        COUNT(*) FILTER (WHERE rh.observacion ILIKE 'V') AS vacaciones,
                        (COALESCE(SUM(CASE WHEN rh.horas_normales > 0 THEN rh.horas_normales ELSE 0 END), 0) * p.pago_hora) AS monto_a_pagar
                    FROM personal p
                    LEFT JOIN registro_horas rh ON p.rut = rh.rut
                    WHERE 1=1
                """

                # Filtro combinable 1: Centro de Costo
                if centro_costo_seleccionado:
                    query += " AND rh.centro_costo = %s"
                    parametros_query.append(centro_costo_seleccionado)

                # Filtro combinable 2: Especialidad
                if especialidad_seleccionada:
                    query += " AND p.especialidad = %s"
                    parametros_query.append(especialidad_seleccionada)

                # Aplicar condiciones de fecha si existen
                if condiciones_fecha:
                    query += f" {condiciones_fecha}"

                # Agrupación y orden
                query += " GROUP BY p.nombre, p.apellido, p.rut, p.pago_hora ORDER BY p.apellido, p.nombre"
                
                cursor.execute(query, parametros_query)
                datos = cursor.fetchall()

        except Exception as e:
            flash(f"Error al ejecutar la consulta SQL: {e}", "danger")
            datos = []
        finally:
            conexion.close()

    # 4. Renderizar el template con los filtros persistidos
    return render_template('resultado_hh.html',
                           centros_costo=centros_costo,
                           especialidades=especialidades,
                           centro_seleccionado=centro_costo_seleccionado,
                           especialidad_seleccionada=especialidad_seleccionada,
                           tipo_filtro=tipo_filtro,
                           fecha_filtro=fecha_filtro,
                           datos=datos)
    
######################################

@app.route('/exportar_resultado_hh_excel', methods=['POST'])
def exportar_resultado_hh_excel():
    from flask import send_file, request, redirect, url_for
    import pandas as pd
    from io import BytesIO
    import datetime
    import os
    import psycopg2.extras 

    centro_costo = request.form.get('centro_costo')
    especialidad = request.form.get('especialidad')
    tipo_filtro = request.form.get('tipo_filtro')
    fecha_filtro = request.form.get('fecha_filtro')

    # --- 1. LÓGICA DE FILTROS DINÁMICOS ---
    condiciones_sql = " WHERE 1=1"
    parametros = []

    # Manejo de filtros de fecha (Sincronizado con resultado_hh)
    if tipo_filtro and tipo_filtro != 'ninguno' and fecha_filtro:
        try:
            if tipo_filtro == 'semana':
                anio, semana_num = map(int, fecha_filtro.split('-W'))
                primer_dia = datetime.date.fromisocalendar(anio, semana_num, 1)
                ultimo_dia = primer_dia + datetime.timedelta(days=6)
                condiciones_sql += " AND rh.horas_fecha BETWEEN %s AND %s"
                parametros.extend([primer_dia, ultimo_dia])
            elif tipo_filtro == 'mes':
                anio, mes = map(int, fecha_filtro.split('-'))
                condiciones_sql += " AND EXTRACT(YEAR FROM rh.horas_fecha) = %s AND EXTRACT(MONTH FROM rh.horas_fecha) = %s"
                parametros.extend([anio, mes])
        except ValueError:
            pass

    # Filtro combinado: Centro de Costo
    if centro_costo and centro_costo != '':
        condiciones_sql += " AND rh.centro_costo = %s"
        parametros.append(centro_costo)

    # Filtro combinado: Especialidad
    if especialidad and especialidad != '':
        condiciones_sql += " AND p.especialidad = %s"
        parametros.append(especialidad)

    conexion = obtener_conexion()
    try:
        with conexion.cursor(cursor_factory=psycopg2.extras.DictCursor) as cursor:
            # Columnas seleccionadas (Incluyendo Desvinculados 'D')
            select_columns = """
                p.nombre, p.apellido, p.rut, p.pago_hora,
                COALESCE(SUM(CASE WHEN rh.horas_normales > 0 THEN rh.horas_normales ELSE 0 END), 0) AS total_hn,
                COALESCE(SUM(CASE WHEN rh.horas_extras > 0 THEN rh.horas_extras ELSE 0 END), 0) AS total_he,
                COALESCE(COUNT(DISTINCT rh.horas_fecha) FILTER (WHERE rh.horas_normales > 0 OR rh.horas_extras > 0), 0) AS dias_trabajados,
                COUNT(*) FILTER (WHERE rh.observacion ILIKE 'L') AS licencias,
                COUNT(*) FILTER (WHERE rh.observacion ILIKE 'P') AS permisos,
                COUNT(*) FILTER (WHERE rh.observacion ILIKE 'F') AS fallas,
                COUNT(*) FILTER (WHERE rh.observacion ILIKE 'V') AS vacaciones,
                COUNT(*) FILTER (WHERE rh.observacion ILIKE 'D') AS desvinculados,
                (COALESCE(SUM(CASE WHEN rh.horas_normales > 0 THEN rh.horas_normales ELSE 0 END), 0) * p.pago_hora) AS monto_a_pagar
            """

            # Construcción final de la Query
            query = f"""
                SELECT {select_columns}
                FROM personal p
                LEFT JOIN registro_horas rh ON p.rut = rh.rut
                {condiciones_sql}
                GROUP BY p.nombre, p.apellido, p.rut, p.pago_hora
                ORDER BY p.apellido, p.nombre
            """
            
            cursor.execute(query, parametros)
            datos = cursor.fetchall()
            columnas = [desc.name for desc in cursor.description]
            
    except Exception as e:
        print(f"Error en exportación Excel: {e}")
        return redirect(url_for('resultado_hh'))
    finally:
        if conexion: conexion.close()

    if not datos:
        return redirect(url_for('resultado_hh'))

    # --- 2. PROCESAMIENTO DE DATOS ---
    df = pd.DataFrame(datos, columns=columnas)
    df = df.fillna(0)

    df.rename(columns={
        'nombre': 'Nombre', 'apellido': 'Apellido', 'rut': 'RUT', 'pago_hora': 'Pago por Hora',
        'total_hn': 'Total Horas Normales', 'total_he': 'Total Horas Extras',
        'dias_trabajados': 'Días con Horas Registradas', 'licencias': 'Licencias',
        'permisos': 'Permisos', 'fallas': 'Fallas', 'vacaciones': 'Vacaciones',
        'desvinculados': 'Desvinculados', 'monto_a_pagar': 'Monto a Pagar (HN)'
    }, inplace=True)

    for col in ['Pago por Hora', 'Total Horas Normales', 'Total Horas Extras', 'Monto a Pagar (HN)']:
        if col in df.columns: df[col] = df[col].round(1)

    # --- 3. DISEÑO PROFESIONAL CON XLSXWRITER ---
    output = BytesIO()
    writer = pd.ExcelWriter(output, engine='xlsxwriter')
    df.to_excel(writer, index=False, sheet_name='Reporte', startrow=1)
    
    workbook  = writer.book
    worksheet = writer.sheets['Reporte']

    formato_cuadricula = workbook.add_format({'border': 1, 'valign': 'vcenter'})
    formato_encabezado = workbook.add_format({'bold': True, 'border': 1, 'bg_color': '#D9D9D9', 'align': 'center'})
    formato_titulo = workbook.add_format({'bold': True, 'font_size': 14, 'align': 'center', 'font_color': '#D45D00'})

    # Datos y encabezados
    for r_idx in range(len(df)):
        for c_idx in range(len(df.columns)):
            worksheet.write(r_idx + 2, c_idx, df.iloc[r_idx, c_idx], formato_cuadricula)

    for c_idx, col_name in enumerate(df.columns):
        worksheet.write(1, c_idx, col_name, formato_encabezado)

    # Logo y Título
    ruta_logo = os.path.join(app.root_path, 'static', 'logo.png')
    if os.path.exists(ruta_logo):
        worksheet.insert_image('A1', ruta_logo, {'x_scale': 0.35, 'y_scale': 0.35, 'x_offset': 5, 'y_offset': 0})

    titulo_texto = f"REPORTE RESULTADOS HH - {centro_costo if centro_costo else 'GENERAL'} - {especialidad if especialidad else 'TODAS'}"
    worksheet.merge_range(0, 1, 0, len(df.columns) - 1, titulo_texto, formato_titulo)

    worksheet.set_row(0, 30) 
    for i, col in enumerate(df.columns):
        worksheet.set_column(i, i, max(len(col), 12) + 2)

    writer.close()
    output.seek(0)

    nombre_archivo = f"Resultado_HH_{datetime.date.today()}.xlsx"
    return send_file(output, download_name=nombre_archivo, as_attachment=True)

######################################################################################################
# --- MÓDULO 1: DASHBOARD GENERAL (KPIs de Gestión) ---
@app.route('/dashboard', methods=['GET', 'POST'])
def dashboard():
    # 1. Validación de sesión y roles permitidos
    if 'usuario' not in session or session.get('rol') not in ['admin', 'jefeB', 'jefeT']:
        return redirect(url_for('login'))

    rol = session.get('rol')
    conexion = obtener_conexion()
    
    # Captura de filtros desde la URL para persistencia (Método GET)
    centro_filtro = request.args.get('centro_costo', '')
    fecha_desde = request.args.get('fecha_desde', '')
    fecha_hasta = request.args.get('fecha_hasta', '')

    # 2. Inicialización de variables de respaldo
    centros = []
    datos_gastos = []
    evolucion_gastos = []
    inventario_datos = []
    consumos_centro = [] 
    asistencia = {}
    estados = {'op': 0, 'def': 0, 'no_op': 0}

    try:
        with conexion.cursor(cursor_factory=psycopg2.extras.DictCursor) as cursor:
            # Consulta maestra de centros para el filtro superior
            cursor.execute("SELECT DISTINCT centro_costo FROM asignacion_personal ORDER BY centro_costo")
            centros = [row['centro_costo'] for row in cursor.fetchall()]

            # 3. Lógica para el Administrador
            if rol == 'admin':
                # --- MEJORA APLICADA: Gastos por Categoría Filtrados ---
                query_gastos = "SELECT categoria, SUM(monto_registro) as total FROM registro_costos WHERE 1=1"
                params_gastos = []

                if centro_filtro:
                    query_gastos += " AND centro_costo = %s"
                    params_gastos.append(centro_filtro)
                
                if fecha_desde and fecha_hasta:
                    query_gastos += " AND fecha_registro BETWEEN %s AND %s"
                    params_gastos.extend([fecha_desde, fecha_hasta])
                
                query_gastos += " GROUP BY categoria"
                cursor.execute(query_gastos, params_gastos)
                datos_gastos = cursor.fetchall()

                # Gráfico Horizontal Unificado (Consumos)
                query_consumo = """
                    SELECT producto_nombre, SUM(total_fila) as total
                    FROM (
                        SELECT producto_nombre, (cantidad * precio) as total_fila, centro_costo, fecha_solicitud as fecha
                        FROM historial_solicitudes
                        UNION ALL
                        SELECT producto_nombre, (cantidad * precio_unitario) as total_fila, centro_costo, fecha_entrada as fecha
                        FROM historial_entradas
                    ) AS movimientos
                    WHERE 1=1
                """
                params_consumo = []

                if centro_filtro:
                    query_consumo += " AND centro_costo = %s"
                    params_consumo.append(centro_filtro)
                
                if fecha_desde and fecha_hasta:
                    query_consumo += " AND fecha BETWEEN %s AND %s"
                    params_consumo.extend([fecha_desde, fecha_hasta])
                
                query_consumo += " GROUP BY producto_nombre ORDER BY total DESC LIMIT 10"
                cursor.execute(query_consumo, params_consumo)
                filas_consumo = cursor.fetchall()
                
                consumos_centro = [
                    {
                        "producto_nombre": row["producto_nombre"], 
                        "total": float(row["total"]) if row["total"] else 0
                    } for row in filas_consumo
                ]
                
                # --- MEJORA APLICADA: Estado de Elementos Filtrado por Centro de Costo ---
                query_estados = """
                    SELECT 
                        COUNT(*) FILTER (WHERE estado = 'OPERATIVO') as op,
                        COUNT(*) FILTER (WHERE estado = 'OPERATIVO CON DEFICIENCIA') as def,
                        COUNT(*) FILTER (WHERE estado = 'NO OPERATIVO') as no_op
                    FROM productos 
                    WHERE categoria != 'CAMIONETA'
                """
                params_estados = []

                if centro_filtro:
                    query_estados += " AND centro_costo = %s"
                    params_estados.append(centro_filtro)

                cursor.execute(query_estados, params_estados)
                resultado_estados = cursor.fetchone()
                if resultado_estados:
                    estados = dict(resultado_estados)

    except Exception as e:
        print(f"⚠️ Error en carga de Dashboard: {e}")
    finally:
        if conexion:
            conexion.close()

    # 4. Retorno de plantilla con variables sincronizadas
    return render_template('dashboard.html', 
                           centros=centros, 
                           gastos_cat=datos_gastos, 
                           evolucion=evolucion_gastos,
                           inventario=inventario_datos, 
                           consumos_centro=consumos_centro, 
                           centro_sel=centro_filtro, 
                           fecha_desde=fecha_desde,
                           fecha_hasta=fecha_hasta,
                           asistencia=asistencia,
                           estados=estados, 
                           rol=rol)
                                        
#####################################################
# --- MÓDULO 2: GESTIÓN DE FLOTA (Módulo Nuevo y Autónomo) ---

@app.route('/gestion_flota')
def gestion_flota():
    # 1. Verificación de Autenticación
    if 'usuario' not in session:
        return redirect(url_for('login'))
        
    rol = session.get('rol')
    
    # 2. Lógica de Restricción Específica
    if rol == 'conductor':
        flash("Acceso limitado: Los conductores deben realizar la inspección directa del vehículo.", "info")
        return redirect(url_for('inspeccion_vehiculo'))

    if rol not in ['admin', 'jefeB', 'jefeT', 'supervisor']:
        flash("No tiene permisos para acceder al centro de gestión de flota.", "danger")
        return redirect(url_for('dashboard'))

    vehiculos = []
    reservas = []
    
    conexion = obtener_conexion()
    try:
        with conexion.cursor(cursor_factory=psycopg2.extras.DictCursor) as cursor:
            # AJUSTE SQL: Seleccionamos v.* para obtener 'persona_a_cargo_rut' directamente
            # No necesitamos el JOIN con usuarios aquí porque el mapeo lo hace Python con el diccionario
            cursor.execute("""
                SELECT * FROM vehiculos_empresa 
                ORDER BY patente
            """)
            vehiculos_raw = cursor.fetchall()
            
            # --- MEJORA: Aplicar Nombres Amigables ---
            for v in vehiculos_raw:
                vehiculo_dict = dict(v) 
                
                # Extraemos el RUT directamente de la columna de la tabla vehiculos_empresa
                rut_a_cargo = v.get('persona_a_cargo_rut')
                
                if rut_a_cargo:
                    # Llamamos a tu función robusta (la que limpia espacios y mayúsculas)
                    nombre, apellido = obtener_datos_por_rut(rut_a_cargo)
                    
                    # Si la función no lo encuentra en el diccionario, mostrará "RUT: XXXXX (No Mapeado)"
                    # Si lo encuentra, mostrará el nombre real
                    vehiculo_dict['nombre_responsable_amigable'] = f"{nombre} {apellido}"
                else:
                    vehiculo_dict['nombre_responsable_amigable'] = "Sin asignar"
                
                vehiculos.append(vehiculo_dict)
            
            # Obtiene las reservas activas para el calendario (FullCalendar)
            cursor.execute("""
                SELECT r.*, v.patente 
                FROM reservas_vehiculos r
                JOIN vehiculos_empresa v ON r.vehiculo_id = v.id
            """)
            reservas = cursor.fetchall()
            
    except Exception as e:
        print(f"⚠️ Error en carga de flota: {e}")
        flash("Error interno al cargar los datos de flota.", "warning")
    finally:
        if conexion:
            conexion.close()
            
    return render_template('gestion_flota.html', vehiculos=vehiculos, reservas=reservas)

###################################################################
@app.route('/solicitar_vehiculo', methods=['POST'])
def solicitar_vehiculo():
    if 'usuario' not in session:
        return redirect(url_for('login'))

    # 1. Captura de datos del formulario
    vehiculo_id = request.form.get('vehiculo_id')
    f_inicio_raw = request.form.get('fecha_inicio')
    f_fin_raw = request.form.get('fecha_fin')
    tipo_evento = request.form.get('tipo_evento')
    por_hora = request.form.get('reserva_por_hora') # Captura el checkbox del HTML
    solicitante_rut = session.get('rut')

    # 2. Normalización de Fechas (Lógica Híbrida)
    # Si el input es 'date', vendrá como YYYY-MM-DD
    # Si el input es 'datetime-local', vendrá como YYYY-MM-DDTHH:MM
    
    if not por_hora:
        # Reserva por DÍA COMPLETO: Forzamos el rango horario total
        fecha_inicio = f"{f_inicio_raw} 00:00:00"
        fecha_fin = f"{f_fin_raw} 23:59:59"
    else:
        # Reserva POR HORA: Reemplazamos la 'T' del formato HTML5 por un espacio para PostgreSQL
        fecha_inicio = f_inicio_raw.replace('T', ' ')
        fecha_fin = f_fin_raw.replace('T', ' ')

    conexion = obtener_conexion()
    try:
        with conexion.cursor(cursor_factory=psycopg2.extras.DictCursor) as cursor:
            # 3. Validación de Disponibilidad (Cruce de horarios)
            # Esta consulta detecta si existe CUALQUIER traslape de tiempo
            cursor.execute("""
                SELECT r.*, v.patente 
                FROM reservas_vehiculos r
                JOIN vehiculos_empresa v ON r.vehiculo_id = v.id
                WHERE r.vehiculo_id = %s 
                AND (
                    (fecha_inicio <= %s AND fecha_fin >= %s) -- Caso traslape total o parcial
                )
            """, (vehiculo_id, fecha_fin, fecha_inicio))
            
            conflicto = cursor.fetchone()

            if conflicto:
                # Si hay conflicto, mostramos el error y redirigimos a Flota (no al login)
                msg = f"⚠️ BLOQUEO: El vehículo {conflicto['patente']} ya tiene una reserva "
                msg += f"desde {conflicto['fecha_inicio'].strftime('%d/%m %H:%M')} "
                msg += f"hasta {conflicto['fecha_fin'].strftime('%d/%m %H:%M')}."
                flash(msg, "danger")
                return redirect(url_for('gestion_flota'))

            # 4. Inserción de la Reserva
            cursor.execute("""
                INSERT INTO reservas_vehiculos (vehiculo_id, solicitante_rut, fecha_inicio, fecha_fin, tipo_evento)
                VALUES (%s, %s, %s, %s, %s)
            """, (vehiculo_id, solicitante_rut, fecha_inicio, fecha_fin, tipo_evento))
            
            conexion.commit()
            flash("✅ Reserva registrada exitosamente.", "success")

    except Exception as e:
        print(f"⚠️ Error al solicitar vehículo: {e}")
        flash("Error interno al procesar la solicitud.", "danger")
    finally:
        if conexion:
            conexion.close()

    return redirect(url_for('gestion_flota'))

###################################################################
@app.route('/api/auditoria_vehiculo/<int:vehiculo_id>')
def api_auditoria_vehiculo(vehiculo_id):
    # 1. Seguridad: Solo roles autorizados pueden ver auditorías
    if 'usuario' not in session or session.get('rol') not in ['admin', 'jefeB', 'jefeT', 'supervisor']:
        return jsonify({"error": "No autorizado"}), 403

    # 2. Captura de filtros de fecha desde la URL (enviados por el Modal)
    f_desde = request.args.get('desde')
    f_hasta = request.args.get('hasta')

    conexion = obtener_conexion()
    historial_datos = []

    try:
        with conexion.cursor(cursor_factory=psycopg2.extras.DictCursor) as cursor:
            # 3. Consulta SQL con JOINs para traer Reservas + Inspecciones
            # Usamos alias para 'estado_vehiculo' como solicitaste
            query = """
                SELECT 
                    r.solicitante_rut, 
                    r.fecha_inicio, 
                    r.fecha_fin, 
                    r.tipo_evento AS motivo,
                    i.estado_vehiculo, 
                    i.observaciones AS detalle_tecnico,
                    v.patente
                FROM reservas_vehiculos r
                JOIN vehiculos_empresa v ON r.vehiculo_id = v.id
                LEFT JOIN inspecciones_flota i ON r.vehiculo_id = i.vehiculo_id 
                    AND (i.fecha::date BETWEEN r.fecha_inicio AND r.fecha_fin)
                WHERE r.vehiculo_id = %s
            """
            params = [vehiculo_id]

            # Aplicar filtros de fecha si el admin los ingresó en el modal
            if f_desde and f_hasta:
                query += " AND r.fecha_inicio BETWEEN %s AND %s"
                params.extend([f_desde, f_hasta])
            
            query += " ORDER BY r.fecha_inicio DESC"
            
            cursor.execute(query, tuple(params))
            rows = cursor.fetchall()

            # 4. Procesamiento de datos con "Variables Auxiliares" (Mapeo de nombres)
            for row in rows:
                nombre, apellido = obtener_datos_por_rut(row['solicitante_rut'])
                
                historial_datos.append({
                    'nombre': nombre,
                    'apellido': apellido,
                    'rut': row['solicitante_rut'],
                    'fecha_solicitud': row['fecha_inicio'].strftime('%d/%m/%Y'),
                    'periodo': f"{row['fecha_inicio'].strftime('%d/%m/%Y')} al {row['fecha_fin'].strftime('%d/%m/%Y')}",
                    'motivo': row['motivo'],
                    'estado_final': row['estado_vehiculo'] or "Sin reporte",
                    'detalle': row['detalle_tecnico'] or "Sin observaciones",
                    'patente': row['patente']
                })

    except Exception as e:
        print(f"⚠️ Error en API Auditoría: {e}")
        return jsonify({"error": "Error interno"}), 500
    finally:
        if conexion:
            conexion.close()

    # Enviamos la lista final a la ventana emergente
    return jsonify(historial_datos)

######################################################################################################
@app.route('/inspeccion_vehiculo', methods=['GET', 'POST'])
def inspeccion_vehiculo():
    if 'usuario' not in session:
        return redirect(url_for('login'))

    # Inicialización para evitar UnboundLocalError
    vehiculos = []
    conexion = obtener_conexion()
    
    try:
        with conexion.cursor(cursor_factory=psycopg2.extras.DictCursor) as cursor:
            if request.method == 'POST':
                # 1. Captura de datos
                vehiculo_id = request.form.get('vehiculo_id')
                kilometraje = request.form.get('kilometraje')
                estado_vehiculo = request.form.get('estado_vehiculo')
                observaciones = request.form.get('observaciones')
                rut_inspector = session.get('rut')

                # 2. Registro en tabla de inspecciones
                cursor.execute("""
                    INSERT INTO inspecciones_flota (vehiculo_id, rut_inspector, kilometraje, estado_vehiculo, observaciones, fecha)
                    VALUES (%s, %s, %s, %s, %s, CURRENT_TIMESTAMP)
                """, (vehiculo_id, rut_inspector, kilometraje, estado_vehiculo, observaciones))
                
                # 3. MEJORA INDUSTRIAL: Actualización automática de kilometraje en la tabla maestra
                # Esto permite tener el dato siempre actualizado para alertas de mantenimiento
                cursor.execute("""
                    UPDATE vehiculos_empresa 
                    SET kilometraje_actual = %s 
                    WHERE id = %s
                """, (kilometraje, vehiculo_id))
                
                conexion.commit()
                flash("✅ Inspección técnica registrada. Kilometraje actualizado en sistema.", "success")
                return redirect(url_for('gestion_flota')) # Redirección alineada al módulo de flota

            # GET: Cargar vehículos para el selector (Consistente con nombres de tablas verificados)
            cursor.execute("SELECT id, patente, marca, modelo FROM vehiculos_empresa ORDER BY patente")
            vehiculos = cursor.fetchall()
            
    except Exception as e:
        print(f"⚠️ Error en inspección: {e}")
        flash("Error al procesar la inspección técnica.", "danger")
    finally:
        if conexion:
            conexion.close()
            
    return render_template('inspeccion_vehiculo.html', vehiculos=vehiculos)

#########################################
@app.route('/anular_reserva/<int:reserva_id>', methods=['POST'])
def anular_reserva(reserva_id):
    # 1. Verificación de permisos (Seguridad)
    if 'usuario' not in session or session.get('rol') not in ['admin', 'jefeB', 'jefeT', 'supervisor']:
        flash("No tiene permisos para anular reservas.", "danger")
        return redirect(url_for('gestion_flota'))

    conexion = obtener_conexion()
    try:
        with conexion.cursor(cursor_factory=psycopg2.extras.DictCursor) as cursor:
            # 2. Obtener el vehiculo_id antes de borrar la reserva (para liberar el activo)
            cursor.execute("SELECT vehiculo_id FROM reservas_vehiculos WHERE id = %s", (reserva_id,))
            reserva = cursor.fetchone()
            
            if reserva:
                vehiculo_id = reserva['vehiculo_id']

                # 3. ELIMINACIÓN FÍSICA: Borra el registro de la reserva
                cursor.execute("DELETE FROM reservas_vehiculos WHERE id = %s", (reserva_id,))

                # 4. RESTAURACIÓN DEL ACTIVO: Devuelve el vehículo a 'DISPONIBLE'
                # IMPORTANTE: Se limpia también la persona a cargo
                cursor.execute("""
                    UPDATE vehiculos_empresa 
                    SET estado_actual = 'DISPONIBLE', persona_a_cargo_rut = NULL 
                    WHERE id = %s
                """, (vehiculo_id,))

                conexion.commit()
                flash("✅ Reserva anulada con éxito. El vehículo vuelve a estar disponible.", "info")
            else:
                flash("❌ Error: La reserva no existe o ya fue eliminada.", "warning")

    except Exception as e:
        print(f"⚠️ Error al anular reserva: {e}")
        flash("Error interno al procesar la anulación.", "danger")
    finally:
        if conexion:
            conexion.close()
            
    return redirect(url_for('gestion_flota'))

######################################################################################################
@app.route('/logout')
def logout():
    session.pop('usuario', None)
    return redirect(url_for('login'))

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 10000))  # Toma el puerto de la variable de entorno
    app.run(host="0.0.0.0", port=port)
