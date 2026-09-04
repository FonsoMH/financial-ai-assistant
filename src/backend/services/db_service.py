import sqlite3
from datetime import datetime

from src.backend.database import DB_PATH

USUARIO_ID_DEFAULT = 1


def get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def obtener_saldo(usuario_id: int = USUARIO_ID_DEFAULT) -> dict:
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute("SELECT nombre, saldo_actual FROM usuarios WHERE id = ?", (usuario_id,))
        row = cur.fetchone()
        if not row:
            return {"error": "Usuario no encontrado"}
        return {"nombre": row["nombre"], "saldo_actual": round(row["saldo_actual"], 2)}
    finally:
        conn.close()


def hacer_bizum(destinatario: str, importe: float, concepto: str = "Bizum", usuario_id: int = USUARIO_ID_DEFAULT) -> dict:
    if not destinatario:
        return {"error": "Falta el destinatario"}
    try:
        importe = float(importe)
    except (TypeError, ValueError):
        return {"error": "El importe no es un número válido"}
    if importe <= 0:
        return {"error": "El importe debe ser mayor que cero"}

    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute("SELECT saldo_actual FROM usuarios WHERE id = ?", (usuario_id,))
        row = cur.fetchone()
        if not row:
            return {"error": "Usuario no encontrado"}

        saldo_actual = row["saldo_actual"]
        if importe > saldo_actual:
            return {"error": "Saldo insuficiente", "saldo_actual": round(saldo_actual, 2)}

        nuevo_saldo = round(saldo_actual - importe, 2)
        fecha = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        cur.execute("UPDATE usuarios SET saldo_actual = ? WHERE id = ?", (nuevo_saldo, usuario_id))
        cur.execute(
            "INSERT INTO movimientos (usuario_id, fecha, concepto, cantidad, tipo, categoria) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (usuario_id, fecha, f"Bizum enviado a {destinatario}: {concepto}", importe, "GASTO", "Gasto_Bizum"),
        )
        conn.commit()

        return {
            "exito": True,
            "destinatario": destinatario,
            "importe": importe,
            "concepto": concepto,
            "nuevo_saldo": nuevo_saldo,
        }
    finally:
        conn.close()


def _buscar_fondo(nombre_buscado: str) -> dict | None:
    """Busca un fondo por coincidencia parcial de nombre (LIKE, no exacto).
    Devuelve None si no hay ninguna coincidencia o si hay más de una
    (ambiguo) — en ambos casos, mejor que el modelo pida aclaración a que
    adivine el fondo equivocado."""
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            "SELECT id, nombre, riesgo, rentabilidad_anual_esperada FROM fondos_disponibles "
            "WHERE nombre LIKE ?",
            (f"%{nombre_buscado}%",),
        )
        filas = cur.fetchall()
        if len(filas) != 1:
            return None
        return dict(filas[0])
    finally:
        conn.close()


def hacer_inversion(fondo: str, importe: float, usuario_id: int = USUARIO_ID_DEFAULT) -> dict:
    if not fondo:
        return {"error": "Falta indicar en qué fondo invertir"}
    try:
        importe = float(importe)
    except (TypeError, ValueError):
        return {"error": "El importe no es un número válido"}
    if importe <= 0:
        return {"error": "El importe debe ser mayor que cero"}

    fondo_row = _buscar_fondo(fondo)
    if not fondo_row:
        return {
            "error": (
                f"No se ha encontrado (o es ambiguo) un fondo que coincida con '{fondo}'. "
                "Consulta fondos_disponibles primero para confirmar el nombre exacto."
            )
        }

    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute("SELECT saldo_actual FROM usuarios WHERE id = ?", (usuario_id,))
        row = cur.fetchone()
        if not row:
            return {"error": "Usuario no encontrado"}

        saldo_actual = row["saldo_actual"]
        if importe > saldo_actual:
            return {"error": "Saldo insuficiente", "saldo_actual": round(saldo_actual, 2)}

        nuevo_saldo = round(saldo_actual - importe, 2)
        fecha = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        cur.execute("UPDATE usuarios SET saldo_actual = ? WHERE id = ?", (nuevo_saldo, usuario_id))

        cur.execute(
            "SELECT id, capital_invertido FROM inversiones_usuario WHERE usuario_id = ? AND fondo_id = ?",
            (usuario_id, fondo_row["id"]),
        )
        existente = cur.fetchone()
        if existente:
            nuevo_capital = round(existente["capital_invertido"] + importe, 2)
            cur.execute(
                "UPDATE inversiones_usuario SET capital_invertido = ? WHERE id = ?",
                (nuevo_capital, existente["id"]),
            )
        else:
            cur.execute(
                "INSERT INTO inversiones_usuario (usuario_id, fondo_id, capital_invertido) VALUES (?, ?, ?)",
                (usuario_id, fondo_row["id"], importe),
            )

        cur.execute(
            "INSERT INTO movimientos (usuario_id, fecha, concepto, cantidad, tipo, categoria) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (usuario_id, fecha, f"Inversión en {fondo_row['nombre']}", importe, "GASTO", "Inversion"),
        )
        conn.commit()

        return {
            "exito": True,
            "fondo": fondo_row["nombre"],
            "importe_invertido": importe,
            "nuevo_saldo": nuevo_saldo,
        }
    finally:
        conn.close()


def retirar_inversion(fondo: str, importe: float | None = None, usuario_id: int = USUARIO_ID_DEFAULT) -> dict:
    """Retira `importe` euros de la inversión en `fondo`. Si no se indica
    importe, retira la posición completa. NOTA: devuelve exactamente el
    capital retirado, sin aplicar rentabilidad histórica — es una
    simplificación deliberada, ver comentario en el módulo."""
    if not fondo:
        return {"error": "Falta indicar de qué fondo retirar"}

    fondo_row = _buscar_fondo(fondo)
    if not fondo_row:
        return {"error": f"No se ha encontrado (o es ambiguo) un fondo que coincida con '{fondo}'."}

    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            "SELECT id, capital_invertido FROM inversiones_usuario WHERE usuario_id = ? AND fondo_id = ?",
            (usuario_id, fondo_row["id"]),
        )
        posicion = cur.fetchone()
        if not posicion:
            return {"error": f"No tienes ninguna inversión activa en {fondo_row['nombre']}"}

        capital_disponible = posicion["capital_invertido"]

        if importe is None:
            importe_retirado = capital_disponible
        else:
            try:
                importe_retirado = float(importe)
            except (TypeError, ValueError):
                return {"error": "El importe no es un número válido"}
            if importe_retirado <= 0:
                return {"error": "El importe debe ser mayor que cero"}
            if importe_retirado > capital_disponible:
                return {
                    "error": "No puedes retirar más de lo que tienes invertido en este fondo",
                    "capital_invertido": round(capital_disponible, 2),
                }

        nuevo_capital = round(capital_disponible - importe_retirado, 2)
        if nuevo_capital <= 0:
            cur.execute("DELETE FROM inversiones_usuario WHERE id = ?", (posicion["id"],))
            nuevo_capital = 0
        else:
            cur.execute(
                "UPDATE inversiones_usuario SET capital_invertido = ? WHERE id = ?",
                (nuevo_capital, posicion["id"]),
            )

        cur.execute("SELECT saldo_actual FROM usuarios WHERE id = ?", (usuario_id,))
        saldo_actual = cur.fetchone()["saldo_actual"]
        nuevo_saldo = round(saldo_actual + importe_retirado, 2)
        cur.execute("UPDATE usuarios SET saldo_actual = ? WHERE id = ?", (nuevo_saldo, usuario_id))

        fecha = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        cur.execute(
            "INSERT INTO movimientos (usuario_id, fecha, concepto, cantidad, tipo, categoria) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (
                usuario_id,
                fecha,
                f"Rescate de inversión en {fondo_row['nombre']}",
                importe_retirado,
                "INGRESO",
                "Rescate_Inversion",
            ),
        )
        conn.commit()

        return {
            "exito": True,
            "fondo": fondo_row["nombre"],
            "importe_retirado": importe_retirado,
            "capital_restante_en_fondo": nuevo_capital,
            "nuevo_saldo": nuevo_saldo,
        }
    finally:
        conn.close()


# Validación defensiva para el NL2SQL: el LLM escribe la query, pero
# esto es lo último que se interpone entre "lo que escribió" y la base
# de datos real. No es un sandbox perfecto, pero bloquea lo obvio.
_PREFIJOS_PERMITIDOS = ("select", "with")
_PALABRAS_PROHIBIDAS = (
    "insert", "update", "delete", "drop", "alter", "attach", "detach",
    "pragma", "create", "replace", "vacuum", "--",
)


def ejecutar_consulta_sql(sql: str, limite_filas: int = 50) -> dict:
    if not sql or not sql.strip():
        return {"error": "Consulta vacía"}

    sql = sql.strip()
    if sql.endswith(";"):
        sql = sql[:-1].strip()

    sql_normalizado = sql.lower()

    if not sql_normalizado.startswith(_PREFIJOS_PERMITIDOS):
        return {"error": "Solo se permiten consultas SELECT"}

    if any(palabra in sql_normalizado for palabra in _PALABRAS_PROHIBIDAS):
        return {"error": "La consulta contiene una operación no permitida"}

    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute(sql)
        filas = cur.fetchall()
        resultado = [dict(fila) for fila in filas]
        return {"resultado": resultado[:limite_filas], "total_filas": len(resultado)}
    except Exception as e:
        return {"error": f"Error al ejecutar la consulta SQL: {e}"}
    finally:
        conn.close()