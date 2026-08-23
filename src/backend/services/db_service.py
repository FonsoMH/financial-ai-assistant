import sqlite3
from datetime import datetime

from src.backend.database import DB_PATH

# El unico usuario que hay
USUARIO_ID_DEFAULT = 1


def get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect("data/finanzas.db")
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


# Validación defensiva para el NL2SQL: el LLM escribe la query, pero
# esto es lo último que se interpone entre "lo que escribió" y la base
# de datos real. No es un sandbox perfecto, pero bloquea lo obvio.
_PREFIJOS_PERMITIDOS = ("select", "with")
_PALABRAS_PROHIBIDAS = (
    "insert", "update", "delete", "drop", "alter", "attach", "detach",
    "pragma", "create", "replace", "vacuum", "--", ";",
)


def ejecutar_consulta_sql(sql: str, limite_filas: int = 50) -> dict:
    if not sql or not sql.strip():
        return {"error": "Consulta vacía"}

    sql_normalizado = sql.strip().lower()

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