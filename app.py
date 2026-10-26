from functools import wraps
from hmac import compare_digest
from decimal import Decimal, InvalidOperation
import os
import secrets

import mysql.connector
from flask import Flask, abort, flash, redirect, render_template, request, session, url_for
from mysql.connector import Error, IntegrityError
from werkzeug.security import check_password_hash, generate_password_hash

app = Flask(__name__)
app.config.update(
    SECRET_KEY=os.environ.get("AGROFLOW_SECRET_KEY") or secrets.token_hex(32),
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE="Lax",
)

BASE_DB_CONFIG = {
    "host": os.environ.get("DB_HOST", "localhost"),
    "port": int(os.environ.get("DB_PORT", 3306)),
    "user": os.environ.get("DB_USER", "root"),
    "password": os.environ.get("DB_PASSWORD", ""),
    "autocommit": True,
}

DB_CONFIG = {
    **BASE_DB_CONFIG,
    "database": os.environ.get("DB_NAME", "agroflow_inventory"),
}



CATEGORIAS = ["gallinas", "vacas", "cerdas"]
ALIMENTOS = {"gallinas": "Gallinas", "cerdos": "Cerdas", "vacas": "Vacas"}
ALERTA_ALIMENTO_KG = Decimal("15.000")

CUENTAS_INICIALES = [
    (
        "adminiecamd",
        "scrypt:32768:8:1$b63v9IAFWNnqnbMF$db1195ebfc2a8fca478fa75bd3b553cfb5b9063eb323bff1e37b94dcd11c8f886ba1522097cc47dcbb58d23c5544df368c19b26c99a4a10db7b72fddc48db6fc",
        "admin",
    ),
    (
        "estudianteiecamd",
        "scrypt:32768:8:1$Loow4v0NLpsesGv6$de3013c1f57d4aca621d4787199106d6f17ab1add5ef575ebe9b4eb701947990afd56bc40343f0bd9c2daaf768827ecb31fa19840f21395c52fe9b69fc4b0b3a",
        "student",
    ),
]

CAMPOS_GALLINAS_DIARIO = [
    {"key": "fecha", "label": "FECHA", "type": "date", "kind": "date", "required": True},
    {"key": "edad_semanas", "label": "EDAD (SEMANAS)", "type": "number", "kind": "int", "min": 0, "default": 0},
    {"key": "aves_vivas", "label": "N AVES VIVAS", "type": "number", "kind": "int", "min": 0, "default": 0},
    {"key": "huevos_recogidos", "label": "HUEVOS RECOGIDOS", "type": "number", "kind": "int", "min": 0, "default": 0},
    {"key": "huevos_comerciales", "label": "HUEVOS COMERCIALES", "type": "number", "kind": "int", "min": 0, "default": 0},
    {"key": "huevos_rotos", "label": "HUEVOS ROTOS", "type": "number", "kind": "int", "min": 0, "default": 0},
    {"key": "huevos_sucios", "label": "HUEVOS SUCIOS", "type": "number", "kind": "int", "min": 0, "default": 0},
    {"key": "huevos_cama", "label": "HUEVOS CAMA", "type": "number", "kind": "int", "min": 0, "default": 0},
    {"key": "porcentaje_postura", "label": "% POSTURA", "type": "number", "kind": "float", "step": "0.01", "min": 0, "default": 0},
    {"key": "mortalidad", "label": "MORTALIDAD", "type": "number", "kind": "int", "min": 0, "default": 0},
    {"key": "alimento_kg", "label": "KG ALIMENTO SUMINISTRADO", "type": "number", "kind": "float", "step": "0.01", "min": 0, "default": 0},
    {"key": "consumo_ave_dia_g", "label": "CONSUMO AVE/DÍA (G)", "type": "number", "kind": "float", "step": "0.01", "min": 0, "default": 0},
    {"key": "observaciones", "label": "OBSERVACIONES", "type": "text", "kind": "text"},
]

TABLAS_PORCINAS = {
    "partos": {
        "nombre": "porcino_partos",
        "columnas": ["id_cerda", "fecha_parto", "hora_inicio", "hora_finaliza", "n_lechones", "machos", "hembras"],
    },
}

CAMPOS_PORCINOS = {
    "partos": [
        {"key": "id_cerda", "label": "ID CERDA", "type": "text", "required": True},
        {"key": "fecha_parto", "label": "FECHA PARTO", "type": "date", "required": True},
        {"key": "hora_inicio", "label": "H-INICIO", "type": "time"},
        {"key": "hora_finaliza", "label": "H-FINALIZA", "type": "time"},
        {"key": "n_lechones", "label": "N LECHONES", "type": "number", "min": 0, "default": 0, "required": True},
        {"key": "machos", "label": "MACHOS", "type": "number", "min": 0, "default": 0, "required": True},
        {"key": "hembras", "label": "HEMBRAS", "type": "number", "min": 0, "default": 0, "required": True},
    ],
}


def ensure_database_exists():
    try:
        conn = mysql.connector.connect(**BASE_DB_CONFIG)
        cursor = conn.cursor()
        cursor.execute("CREATE DATABASE IF NOT EXISTS agroflow_inventory")
        conn.commit()
        cursor.close()
        conn.close()
    except Error as exc:
        raise RuntimeError(f"No se pudo crear la base de datos: {exc}") from exc


def get_db_connection():
    try:
        ensure_database_exists()
        return mysql.connector.connect(**DB_CONFIG)
    except Error as exc:
        raise RuntimeError(f"No se pudo conectar a MySQL: {exc}") from exc


def login_required(view):
    @wraps(view)
    def wrapped_view(*args, **kwargs):
        if not session.get("user_id"):
            return redirect(url_for("login"))
        return view(*args, **kwargs)

    return wrapped_view


def admin_required(view):
    @wraps(view)
    def wrapped_view(*args, **kwargs):
        if not session.get("user_id"):
            return redirect(url_for("login"))
        if session.get("role") != "admin":
            abort(403)
        return view(*args, **kwargs)

    return wrapped_view


@app.before_request
def protect_post_requests():
    if request.method == "POST":
        expected_token = session.get("_csrf_token", "")
        submitted_token = request.form.get("_csrf_token", "")
        if not expected_token or not compare_digest(expected_token, submitted_token):
            abort(400, description="Token de formulario no válido. Recarga la página e inténtalo de nuevo.")


@app.context_processor
def inject_csrf_token():
    def csrf_token():
        if "_csrf_token" not in session:
            session["_csrf_token"] = secrets.token_urlsafe(32)
        return session["_csrf_token"]

    return {"csrf_token": csrf_token}


def init_db():
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS usuarios (
            id INT AUTO_INCREMENT PRIMARY KEY,
            username VARCHAR(80) NOT NULL UNIQUE,
            password_hash VARCHAR(255) NOT NULL,
            role ENUM('admin', 'student') NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
        )
        """
    )
    cursor.executemany(
        "INSERT IGNORE INTO usuarios (username, password_hash, role) VALUES (%s, %s, %s)",
        CUENTAS_INICIALES,
    )

    for tabla in CATEGORIAS:
        cursor.execute(
            f"""
            CREATE TABLE IF NOT EXISTS {tabla} (
                id INT AUTO_INCREMENT PRIMARY KEY,
                cantidad INT NOT NULL,
                ubicacion VARCHAR(100) NOT NULL,
                estado_salud VARCHAR(50) NOT NULL,
                observaciones TEXT,
                fecha_registro TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """
        )

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS plantas (
            id INT AUTO_INCREMENT PRIMARY KEY,
            nombre VARCHAR(100) NOT NULL UNIQUE,
            fecha_registro TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """
    )

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS gallinas_diario (
            id INT AUTO_INCREMENT PRIMARY KEY,
            fecha DATE NOT NULL,
            edad_semanas INT NOT NULL DEFAULT 0,
            aves_vivas INT NOT NULL DEFAULT 0,
            huevos_recogidos INT NOT NULL DEFAULT 0,
            huevos_comerciales INT NOT NULL DEFAULT 0,
            huevos_rotos INT NOT NULL DEFAULT 0,
            huevos_sucios INT NOT NULL DEFAULT 0,
            huevos_cama INT NOT NULL DEFAULT 0,
            porcentaje_postura DECIMAL(7, 2) NOT NULL DEFAULT 0,
            mortalidad INT NOT NULL DEFAULT 0,
            alimento_kg DECIMAL(9, 2) NOT NULL DEFAULT 0,
            consumo_ave_dia_g DECIMAL(9, 2) NOT NULL DEFAULT 0,
            observaciones TEXT,
            fecha_registro TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """
    )

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS compras_alimento (
            id INT AUTO_INCREMENT PRIMARY KEY,
            especie ENUM('gallinas', 'cerdos', 'vacas') NOT NULL,
            cantidad_kg DECIMAL(10, 3) NOT NULL,
            fecha_compra DATE NOT NULL,
            observaciones TEXT,
            admin_id INT NOT NULL,
            fecha_registro TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            CONSTRAINT fk_compra_alimento_admin
                FOREIGN KEY (admin_id) REFERENCES usuarios(id)
        )
        """
    )

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS vacas_alimento_diario (
            id INT AUTO_INCREMENT PRIMARY KEY,
            fecha DATE NOT NULL,
            cantidad_kg DECIMAL(10, 3) NOT NULL,
            leche_litros DECIMAL(10, 3) NOT NULL DEFAULT 0,
            observaciones TEXT,
            usuario_id INT NOT NULL,
            fecha_registro TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            CONSTRAINT fk_vacas_alimento_usuario
                FOREIGN KEY (usuario_id) REFERENCES usuarios(id)
        )
        """
    )
    cursor.execute(
        """
        SELECT COUNT(*)
        FROM information_schema.COLUMNS
        WHERE TABLE_SCHEMA = DATABASE()
          AND TABLE_NAME = 'vacas_alimento_diario'
          AND COLUMN_NAME = 'leche_litros'
        """
    )
    if cursor.fetchone()[0] == 0:
        cursor.execute(
            "ALTER TABLE vacas_alimento_diario "
            "ADD COLUMN leche_litros DECIMAL(10, 3) NOT NULL DEFAULT 0 AFTER cantidad_kg"
        )

    cursor.execute("SHOW TABLES LIKE 'porcino_partos'")
    if cursor.fetchone():
        cursor.execute("SHOW COLUMNS FROM porcino_partos")
        columnas_partos = {row[0] for row in cursor.fetchall()}
        if "n_lechones" not in columnas_partos:
            cursor.execute("DROP TABLE porcino_partos")

    cursor.execute(
        "DROP TABLE IF EXISTS porcino_sanidad_cerda, porcino_plan_lechon, porcino_consumo_concentrado"
    )
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS porcino_partos (
            id INT AUTO_INCREMENT PRIMARY KEY,
            id_cerda VARCHAR(30) NOT NULL,
            fecha_parto DATE NOT NULL,
            hora_inicio TIME,
            hora_finaliza TIME,
            n_lechones INT NOT NULL DEFAULT 0,
            machos INT NOT NULL DEFAULT 0,
            hembras INT NOT NULL DEFAULT 0,
            concentrado_lechones_kg DECIMAL(10, 3)
                GENERATED ALWAYS AS (n_lechones * 0.500) STORED,
            mantenimiento_cerda_kg DECIMAL(10, 3) NOT NULL DEFAULT 2.000,
            total_diario_kg DECIMAL(10, 3)
                GENERATED ALWAYS AS (n_lechones * 0.500 + mantenimiento_cerda_kg) STORED,
            total_levante_2_meses_kg DECIMAL(12, 3)
                GENERATED ALWAYS AS ((n_lechones * 0.500 + mantenimiento_cerda_kg) * 60) STORED
        )
        """
    )

    conn.commit()
    cursor.close()
    conn.close()


def get_table_data(tabla):
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute(f"SELECT * FROM {tabla} ORDER BY fecha_registro DESC")
    data = cursor.fetchall()
    cursor.close()
    conn.close()
    return data


def total_cantidad(datos):
    return sum(item["cantidad"] for item in datos)


def get_porcine_data():
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    data = {}
    for clave, config in TABLAS_PORCINAS.items():
        cursor.execute(f"SELECT * FROM {config['nombre']} ORDER BY fecha_parto DESC, id DESC")
        data[clave] = cursor.fetchall()
    cursor.close()
    conn.close()
    return data


def get_gallinas_diario():
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT * FROM gallinas_diario ORDER BY fecha DESC, id DESC")
    registros = cursor.fetchall()
    cursor.close()
    conn.close()
    return registros


def get_plantas():
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT id, nombre, fecha_registro FROM plantas ORDER BY fecha_registro DESC, id DESC")
    plantas = cursor.fetchall()
    cursor.close()
    conn.close()
    return plantas


def get_vacas_alimento_diario():
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT * FROM vacas_alimento_diario ORDER BY fecha DESC, id DESC")
    registros = cursor.fetchall()
    cursor.close()
    conn.close()
    return registros


def get_alimento_data(especie):
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute(
        "SELECT COALESCE(SUM(cantidad_kg), 0) AS total FROM compras_alimento WHERE especie = %s",
        (especie,),
    )
    comprado = cursor.fetchone()["total"] or Decimal("0")
    if especie == "cerdos":
        cursor.execute(
            """
            SELECT COALESCE(SUM(
                total_diario_kg * LEAST(60, GREATEST(DATEDIFF(CURDATE(), fecha_parto), 0))
            ), 0) AS total
            FROM porcino_partos
            """
        )
    else:
        tabla, columna = {
            "gallinas": ("gallinas_diario", "alimento_kg"),
            "vacas": ("vacas_alimento_diario", "cantidad_kg"),
        }[especie]
        cursor.execute(f"SELECT COALESCE(SUM({columna}), 0) AS total FROM {tabla}")
    consumido = cursor.fetchone()["total"] or Decimal("0")
    cursor.execute(
        "SELECT * FROM compras_alimento WHERE especie = %s ORDER BY fecha_compra DESC, id DESC",
        (especie,),
    )
    compras = cursor.fetchall()
    cursor.close()
    conn.close()

    disponible = comprado - consumido
    tiene_movimientos = comprado > 0 or consumido > 0
    return {
        "comprado": comprado,
        "consumido": consumido,
        "disponible": disponible,
        "tiene_movimientos": tiene_movimientos,
        "alerta": tiene_movimientos and disponible <= ALERTA_ALIMENTO_KG,
        "compras": compras,
    }


def alimento_redirect(especie):
    return redirect(url_for("index", vista="alimento", especie=especie, _anchor="control-alimento"))


def guardar_consumo_vacas(record_id=None, vista="alimento"):
    fecha = request.form.get("fecha", "").strip()
    observaciones = request.form.get("observaciones", "").strip() or None
    try:
        cantidad_kg = Decimal(request.form.get("cantidad_kg", "0").strip())
        leche_litros = Decimal(request.form.get("leche_litros", "0").strip())
    except InvalidOperation:
        flash("Ingresa cantidades válidas de alimento y leche.", "danger")
        return redirect(url_for("index", vista=vista, especie="vacas" if vista == "alimento" else None))

    if not fecha or cantidad_kg <= 0 or leche_litros < 0:
        flash("La fecha, el alimento mayor que cero y la leche igual o mayor que cero son obligatorios.", "danger")
        return redirect(url_for("index", vista=vista, especie="vacas" if vista == "alimento" else None))

    conn = get_db_connection()
    cursor = conn.cursor()
    if record_id is None:
        cursor.execute(
            "INSERT INTO vacas_alimento_diario "
            "(fecha, cantidad_kg, leche_litros, observaciones, usuario_id) "
            "VALUES (%s, %s, %s, %s, %s)",
            (fecha, cantidad_kg, leche_litros, observaciones, session["user_id"]),
        )
    else:
        cursor.execute(
            "UPDATE vacas_alimento_diario "
            "SET fecha = %s, cantidad_kg = %s, leche_litros = %s, observaciones = %s WHERE id = %s",
            (fecha, cantidad_kg, leche_litros, observaciones, record_id),
        )
    conn.commit()
    cursor.close()
    conn.close()
    return redirect(url_for("index", vista=vista, especie="vacas" if vista == "alimento" else None))


def guardar_registro_gallina(record_id=None):
    columnas = [field["key"] for field in CAMPOS_GALLINAS_DIARIO]
    valores = []
    for field in CAMPOS_GALLINAS_DIARIO:
        raw_value = request.form.get(field["key"], "").strip()
        if field["kind"] == "int":
            value = int(raw_value or field.get("default", 0))
        elif field["kind"] == "float":
            value = float(raw_value or field.get("default", 0))
        else:
            value = raw_value or None
        valores.append(value)

    conn = get_db_connection()
    cursor = conn.cursor()
    if record_id is None:
        placeholders = ", ".join(["%s"] * len(columnas))
        cursor.execute(
            f"INSERT INTO gallinas_diario ({', '.join(columnas)}) VALUES ({placeholders})",
            valores,
        )
    else:
        assignments = ", ".join(f"{columna} = %s" for columna in columnas)
        cursor.execute(
            f"UPDATE gallinas_diario SET {assignments} WHERE id = %s",
            [*valores, record_id],
        )
    conn.commit()
    cursor.close()
    conn.close()
    return redirect(url_for("index", vista="gallinas", ver_gallinas=1, _anchor="historial-gallinas"))


def porcino_redirect():
    return redirect(url_for("index", vista="cerdos", _anchor="porcinos"))


@app.route("/login", methods=["GET", "POST"])
def login():
    if session.get("user_id"):
        return redirect(url_for("index"))

    try:
        init_db()
        if request.method == "POST":
            username = request.form.get("username", "").strip()
            password = request.form.get("password", "")
            conn = get_db_connection()
            cursor = conn.cursor(dictionary=True)
            cursor.execute("SELECT id, username, password_hash, role FROM usuarios WHERE username = %s", (username,))
            user = cursor.fetchone()
            cursor.close()
            conn.close()

            if user and check_password_hash(user["password_hash"], password):
                session.clear()
                session["user_id"] = user["id"]
                session["username"] = user["username"]
                session["role"] = user["role"]
                return redirect(url_for("index"))

            flash("Usuario o contraseña incorrectos.", "danger")
    except RuntimeError as exc:
        return f"<h2>Error de base de datos</h2><p>{exc}</p>", 500

    return render_template("login.html")


@app.route("/logout", methods=["POST"])
@login_required
def logout():
    session.clear()
    return redirect(url_for("login"))


@app.route("/admin/cuentas", methods=["GET", "POST"])
@admin_required
def admin_cuentas():
    if request.method == "POST":
        user_id = request.form.get("user_id", type=int)
        new_password = request.form.get("new_password", "")
        confirmation = request.form.get("confirm_password", "")
        if not user_id or len(new_password) < 10:
            flash("La contraseña nueva debe tener al menos 10 caracteres.", "danger")
        elif new_password != confirmation:
            flash("Las contraseñas no coinciden.", "danger")
        else:
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute(
                "UPDATE usuarios SET password_hash = %s WHERE id = %s",
                (generate_password_hash(new_password), user_id),
            )
            conn.commit()
            updated = cursor.rowcount
            cursor.close()
            conn.close()
            if updated:
                flash("Contraseña actualizada.", "success")
            else:
                flash("No se encontró esa cuenta.", "danger")

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT id, username, role FROM usuarios ORDER BY role, username")
    users = cursor.fetchall()
    cursor.close()
    conn.close()
    return render_template("admin_cuentas.html", users=users)


def guardar_registro_porcino(clave, record_id=None):
    config = TABLAS_PORCINAS[clave]
    columnas = config["columnas"]
    defaults = {
        field["key"]: field.get("default")
        for field in CAMPOS_PORCINOS[clave]
    }
    valores = [
        request.form.get(columna, "").strip() or defaults.get(columna)
        for columna in columnas
    ]

    conn = get_db_connection()
    cursor = conn.cursor()
    if record_id is None:
        placeholders = ", ".join(["%s"] * len(columnas))
        cursor.execute(
            f"INSERT INTO {config['nombre']} ({', '.join(columnas)}) VALUES ({placeholders})",
            valores,
        )
    else:
        assignments = ", ".join(f"{columna} = %s" for columna in columnas)
        cursor.execute(
            f"UPDATE {config['nombre']} SET {assignments} WHERE id = %s",
            [*valores, record_id],
        )
    conn.commit()
    cursor.close()
    conn.close()
    return porcino_redirect()


@app.route("/")
@login_required
def index():
    try:
        init_db()
        vista = request.args.get("vista", "gallinas")
        if vista not in {"gallinas", "cerdos", "vacas", "plantas", "alimento"}:
            vista = "gallinas"

        especie_alimento = request.args.get("especie", "gallinas")
        if especie_alimento not in ALIMENTOS:
            especie_alimento = "gallinas"

        editing_key = request.args.get("editar")
        editing_id = request.args.get("id", type=int)
        if editing_key not in TABLAS_PORCINAS or editing_id is None:
            editing_key = None
            editing_id = None
        if session.get("role") != "admin":
            editing_key = None
            editing_id = None

        nuevo_porcino = request.args.get("nuevo_porcino")
        if nuevo_porcino not in TABLAS_PORCINAS:
            nuevo_porcino = None

        gallinas_diario = get_gallinas_diario()
        editing_chicken_id = request.args.get("editar_gallina", type=int)
        if editing_chicken_id not in {item["id"] for item in gallinas_diario}:
            editing_chicken_id = None
        if session.get("role") != "admin":
            editing_chicken_id = None
        nuevo_registro_gallina = request.args.get("nuevo_gallina") == "1"
        ver_registros_gallina = request.args.get("ver_gallinas") == "1"

        vacas_alimento_diario = get_vacas_alimento_diario()
        editing_vaca_alimento_id = request.args.get("editar_consumo_vaca", type=int)
        if editing_vaca_alimento_id not in {item["id"] for item in vacas_alimento_diario}:
            editing_vaca_alimento_id = None
        if session.get("role") != "admin":
            editing_vaca_alimento_id = None
        nuevo_registro_vaca = request.args.get("nuevo_vaca") == "1"

        data = {
            "gallinas": get_table_data("gallinas"),
            "vacas": get_table_data("vacas"),
            "cerdas": get_table_data("cerdas"),
        }
        plantas = get_plantas()
        totals = {categoria: total_cantidad(data[categoria]) for categoria in CATEGORIAS}
        total_general = sum(totals.values())
        return render_template(
            "index.html",
            data=data,
            totals=totals,
            total_general=total_general,
            categorias=CATEGORIAS,
            porcinos=get_porcine_data(),
            campos_porcinos=CAMPOS_PORCINOS,
            vista=vista,
            editing_key=editing_key,
            editing_id=editing_id,
            nuevo_porcino=nuevo_porcino,
            gallinas_diario=gallinas_diario,
            campos_gallinas_diario=CAMPOS_GALLINAS_DIARIO,
            editing_chicken_id=editing_chicken_id,
            nuevo_registro_gallina=nuevo_registro_gallina,
            ver_registros_gallina=ver_registros_gallina,
            especie_alimento=especie_alimento,
            alimentos=ALIMENTOS,
            alimento=get_alimento_data(especie_alimento),
            plantas=plantas,
            vacas_alimento_diario=vacas_alimento_diario,
            editing_vaca_alimento_id=editing_vaca_alimento_id,
            nuevo_registro_vaca=nuevo_registro_vaca,
        )
    except RuntimeError as exc:
        return f"<h2>Error de base de datos</h2><p>{exc}</p>", 500


@app.route("/agregar", methods=["POST"])
@login_required
def agregar_registro():
    categoria = request.form.get("categoria")
    if categoria not in CATEGORIAS:
        return "Categoría no válida", 400

    cantidad = int(request.form.get("cantidad", 0))
    ubicacion = request.form.get("ubicacion", "")
    estado_salud = request.form.get("estado_salud", "Bueno")
    observaciones = request.form.get("observaciones", "")

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        f"""
        INSERT INTO {categoria} (cantidad, ubicacion, estado_salud, observaciones)
        VALUES (%s, %s, %s, %s)
        """,
        (cantidad, ubicacion, estado_salud, observaciones),
    )
    conn.commit()
    cursor.close()
    conn.close()

    return redirect(url_for("index"))


@app.route("/plantas/agregar", methods=["POST"])
@admin_required
def agregar_planta():
    nombre = request.form.get("nombre", "").strip()
    if not nombre or len(nombre) > 100:
        flash("Escribe un nombre de planta de máximo 100 caracteres.", "danger")
        return redirect(url_for("index", vista="plantas"))

    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("INSERT INTO plantas (nombre) VALUES (%s)", (nombre,))
        conn.commit()
        creada = True
    except IntegrityError:
        conn.rollback()
        creada = False
    cursor.close()
    conn.close()

    if creada:
        flash(f"Planta «{nombre}» añadida.", "success")
    else:
        flash(f"La planta «{nombre}» ya está registrada.", "info")
    return redirect(url_for("index", vista="plantas"))


@app.route("/plantas/<int:planta_id>/eliminar", methods=["POST"])
@admin_required
def eliminar_planta(planta_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM plantas WHERE id = %s", (planta_id,))
    eliminada = cursor.rowcount == 1
    conn.commit()
    cursor.close()
    conn.close()

    if eliminada:
        flash("Planta eliminada.", "success")
    else:
        flash("No se encontró esa planta.", "warning")
    return redirect(url_for("index", vista="plantas"))


@app.route("/gallinas/diario/agregar", methods=["POST"])
@login_required
def agregar_registro_gallina():
    return guardar_registro_gallina()


@app.route("/gallinas/diario/<int:record_id>/editar", methods=["POST"])
@admin_required
def editar_registro_gallina(record_id):
    return guardar_registro_gallina(record_id)


@app.route("/gallinas/diario/eliminar", methods=["POST"])
@admin_required
def eliminar_registro_gallina():
    record_id = request.form.get("record_id", type=int)
    if record_id is None:
        return "Selecciona un registro para eliminar", 400
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM gallinas_diario WHERE id = %s", (record_id,))
    conn.commit()
    cursor.close()
    conn.close()
    return redirect(url_for("index", vista="gallinas", ver_gallinas=1, _anchor="historial-gallinas"))


@app.route("/alimento/compras/agregar", methods=["POST"])
@admin_required
def agregar_compra_alimento():
    especie = request.form.get("especie", "")
    fecha_compra = request.form.get("fecha_compra", "").strip()
    observaciones = request.form.get("observaciones", "").strip() or None
    if especie not in ALIMENTOS:
        abort(400)
    try:
        cantidad_kg = Decimal(request.form.get("cantidad_kg", "0").strip())
    except InvalidOperation:
        flash("Ingresa una cantidad válida en kilogramos.", "danger")
        return alimento_redirect(especie)
    if not fecha_compra or cantidad_kg <= 0:
        flash("La fecha y una cantidad mayor que cero son obligatorias.", "danger")
        return alimento_redirect(especie)

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO compras_alimento (especie, cantidad_kg, fecha_compra, observaciones, admin_id) VALUES (%s, %s, %s, %s, %s)",
        (especie, cantidad_kg, fecha_compra, observaciones, session["user_id"]),
    )
    conn.commit()
    cursor.close()
    conn.close()
    flash(f"Compra de {cantidad_kg} kg registrada para {ALIMENTOS[especie]}.", "success")
    return alimento_redirect(especie)


@app.route("/alimento/compras/<int:record_id>/eliminar", methods=["POST"])
@admin_required
def eliminar_compra_alimento(record_id):
    especie = request.form.get("especie", "")
    if especie not in ALIMENTOS:
        abort(400)

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        "DELETE FROM compras_alimento WHERE id = %s AND especie = %s",
        (record_id, especie),
    )
    eliminada = cursor.rowcount == 1
    conn.commit()
    cursor.close()
    conn.close()

    if eliminada:
        flash("Compra de alimento eliminada.", "success")
    else:
        flash("No se encontró esa compra de alimento.", "warning")
    return alimento_redirect(especie)


@app.route("/alimento/vacas/consumo/agregar", methods=["POST"])
@login_required
def agregar_consumo_alimento_vacas():
    return guardar_consumo_vacas(vista="alimento")


@app.route("/alimento/vacas/consumo/<int:record_id>/editar", methods=["POST"])
@admin_required
def editar_consumo_alimento_vacas(record_id):
    return guardar_consumo_vacas(record_id, vista="alimento")


@app.route("/alimento/vacas/consumo/<int:record_id>/eliminar", methods=["POST"])
@admin_required
def eliminar_consumo_alimento_vacas(record_id):
    return borrar_registro_diario_vaca(record_id, "alimento")


def borrar_registro_diario_vaca(record_id, vista):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM vacas_alimento_diario WHERE id = %s", (record_id,))
    conn.commit()
    cursor.close()
    conn.close()
    return redirect(url_for("index", vista=vista, especie="vacas" if vista == "alimento" else None))


@app.route("/vacas/diario/agregar", methods=["POST"])
@login_required
def agregar_registro_diario_vaca():
    return guardar_consumo_vacas(vista="vacas")


@app.route("/vacas/diario/<int:record_id>/editar", methods=["POST"])
@admin_required
def editar_registro_diario_vaca(record_id):
    return guardar_consumo_vacas(record_id, vista="vacas")


@app.route("/vacas/diario/<int:record_id>/eliminar", methods=["POST"])
@admin_required
def eliminar_registro_diario_vaca(record_id):
    return borrar_registro_diario_vaca(record_id, "vacas")


@app.route("/porcinos/<clave>/agregar", methods=["POST"])
@login_required
def agregar_registro_porcino(clave):
    if clave not in TABLAS_PORCINAS:
        return "Tabla porcina no válida", 404
    return guardar_registro_porcino(clave)


@app.route("/porcinos/<clave>/<int:record_id>/editar", methods=["POST"])
@admin_required
def editar_registro_porcino(clave, record_id):
    if clave not in TABLAS_PORCINAS:
        return "Tabla porcina no válida", 404
    return guardar_registro_porcino(clave, record_id)


@app.route("/porcinos/<clave>/<int:record_id>/eliminar", methods=["POST"])
@admin_required
def eliminar_registro_porcino(clave, record_id):
    if clave not in TABLAS_PORCINAS:
        return "Tabla porcina no válida", 404
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        f"DELETE FROM {TABLAS_PORCINAS[clave]['nombre']} WHERE id = %s",
        (record_id,),
    )
    conn.commit()
    cursor.close()
    conn.close()
    return porcino_redirect()


@app.route("/eliminar/<categoria>/<int:id>", methods=["POST"])
@admin_required
def eliminar_registro(categoria, id):
    if categoria not in CATEGORIAS:
        return "Categoría no válida", 400

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(f"DELETE FROM {categoria} WHERE id = %s", (id,))
    conn.commit()
    cursor.close()
    conn.close()

    return redirect(url_for("index"))


if __name__ == "__main__":
    init_db()
    app.run(debug=True, host="0.0.0.0", port=5000)
