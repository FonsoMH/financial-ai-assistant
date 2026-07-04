import sqlite3
import os
from faker import Faker
import random
from datetime import datetime, timedelta

fake = Faker('es_ES')
DB_PATH = os.path.join(os.path.dirname(__file__), '../data/finanzas.db')

def init_db():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS usuarios (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nombre TEXT NOT NULL,
            telefono TEXT NOT NULL,
            iban TEXT NOT NULL,
            saldo_actual REAL NOT NULL
        )
    ''')
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS movimientos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            usuario_id INTEGER,
            fecha TEXT NOT NULL,
            concepto TEXT NOT NULL,
            cantidad REAL NOT NULL,
            tipo TEXT NOT NULL,
            categoria TEXT NOT NULL,
            FOREIGN KEY(usuario_id) REFERENCES usuarios(id)
        )
    ''')
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS contactos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nombre TEXT NOT NULL,
            telefono TEXT NOT NULL
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS fondos_disponibles (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nombre TEXT NOT NULL,
            riesgo TEXT NOT NULL,
            rentabilidad_anual_esperada REAL NOT NULL
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS fondos_historico (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            fondo_id INTEGER,
            año_mes TEXT NOT NULL,
            rentabilidad_mes REAL NOT NULL,
            FOREIGN KEY(fondo_id) REFERENCES fondos_disponibles(id)
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS inversiones_usuario (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            usuario_id INTEGER,
            fondo_id INTEGER,
            capital_invertido REAL NOT NULL,
            FOREIGN KEY(usuario_id) REFERENCES usuarios(id),
            FOREIGN KEY(fondo_id) REFERENCES fondos_disponibles(id)
        )
    ''')
    
    conn.commit()
    conn.close()

def seed_data():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute("SELECT COUNT(*) FROM usuarios")
    if cursor.fetchone()[0] > 0:
        conn.close()
        return

    print("🚀 Generando ecosistema financiero avanzado...")

    cursor.execute("INSERT INTO usuarios (nombre, telefono, iban, saldo_actual) VALUES (?, ?, ?, ?)",
                   ("Sofia Heredia", "636636636", fake.iban(), 5000.0))
    usuario_id = cursor.lastrowid


    fondos = [
        (1, "Fondo Tecnológico e IA Megatendencias", "Alto", 14.5),
        (2, "Indexado S&P 500 Global", "Medio", 8.5),
        (3, "Renta Fija del Estado (Bonos)", "Bajo", 3.2),
        (4, "Fondo Inmobiliario Rentas Europeas", "Medio", 5.5),
        (5, "Cripto-Activos de Alta Volatilidad", "Muy Alto", 22.0)
    ]
    cursor.executemany("INSERT INTO fondos_disponibles (id, nombre, riesgo, rentabilidad_anual_esperada) VALUES (?, ?, ?, ?)", fondos)

    # Histórico de Rentabilidad
    meses = ["2026-01", "2026-02", "2026-03", "2026-04", "2026-05", "2026-06"]
    historico_datos = []
    for fondo_id, nombre, riesgo, _ in fondos:
        for mes in meses:
            if riesgo == "Muy Alto":
                rentabilidad = round(random.uniform(-12.0, 18.0), 2) 
            elif riesgo == "Alto":
                rentabilidad = round(random.uniform(-5.0, 8.0), 2)
            elif riesgo == "Medio":
                rentabilidad = round(random.uniform(-1.5, 3.5), 2)
            else:
                rentabilidad = round(random.uniform(0.1, 0.4), 2)
            historico_datos.append((fondo_id, mes, rentabilidad))
    cursor.executemany("INSERT INTO fondos_historico (fondo_id, año_mes, rentabilidad_mes) VALUES (?, ?, ?)", historico_datos)

    cursor.execute("INSERT INTO inversiones_usuario (usuario_id, fondo_id, capital_invertido) VALUES (?, ?, ?)", (usuario_id, 2, 2000.0))
    cursor.execute("INSERT INTO inversiones_usuario (usuario_id, fondo_id, capital_invertido) VALUES (?, ?, ?)", (usuario_id, 4, 1200.0))

    # Generamos los contactos de la agenda primero para poder usarlos en los Bizum
    lista_contactos = [(fake.first_name(), f"6{random.randint(1000000, 9999999)}") for _ in range(10)]
    cursor.executemany("INSERT INTO contactos (nombre, telefono) VALUES (?, ?)", lista_contactos)
    
    # SOLUCIÓN DIRECTA: Extraemos los nombres desde nuestra tupla local de forma segura
    nombres_contactos = [contacto[0] for contacto in lista_contactos]

    # Mapear Conceptos por Categoría
    categorias_gastos = {
        "Gasolina": ["Gasolinera Repsol", "Cepsa", "Galp", "Shell"],
        "Supermercado": ["Mercadona", "Carrefour", "Lidl", "Alcampo"],
        "Comida": ["Uber Eats", "Just Eat", "McDonalds", "La Tagliatella", "Burger King"],
        "Ocio": ["Entradas Cine", "Concierto", "Escape Room", "Discoteca"],
        "Suscripciones": ["Netflix", "Spotify", "Amazon Prime", "Gimnasio"],
        "Ropa": ["Zara", "Hollister", "Nike", "Decathlon"],
        "Salud": ["Farmacia", "Dentista", "Óptica"],
        "Hogar": ["Factura Luz", "Factura Agua", "Factura Wifi"]
    }

    conceptos_bizum_ingreso = [
        "Cena del viernes", "Regalo de cumpleaños", "Piso compartido", 
        "Taxis compartidos", "Cañas", "Concierto", "Compra a medias"
    ]

    fecha_inicio = datetime.now() - timedelta(days=150)
    saldo_acumulado = 6000.0
    movimientos = []

    # 1. Ingresos fijos (Nómina)
    for i in range(5):
        fecha_nom = (fecha_inicio + timedelta(days=30 * i)).strftime("%Y-%m-%d %H:%M:%S")
        movimientos.append((usuario_id, fecha_nom, "Nómina Mensual", 1950.0, "INGRESO", "Nomina"))
        saldo_acumulado += 1950.0

    # 2. Gastos fijos (Alquiler)
    print("🏠 Insertando gastos fijos de alquiler...")
    for i in range(5):
        fecha_mes = datetime.now() - timedelta(days=30 * i)
        fecha_alquiler = fecha_mes.strftime("%Y-%m-%01 09:00:00")
        movimientos.append((usuario_id, fecha_alquiler, "Alquiler", 850.0, "GASTO", "Hogar"))
        saldo_acumulado -= 850.0

    # 3. NUEVO: Generar Ingresos por Bizum realistas (unos 20 Bizums en 5 meses)
    print("📲 Insertando ingresos por Bizum recibidos...")
    for _ in range(20):
        fecha_bizum = fake.date_time_between_dates(datetime_start=fecha_inicio, datetime_end=datetime.now())
        amigo = random.choice(nombres_contactos)
        motivo = random.choice(conceptos_bizum_ingreso)
        concepto = f"Bizum de {amigo}: {motivo}"
        cantidad = round(random.uniform(5.0, 45.0), 2)
        
        movimientos.append((usuario_id, fecha_bizum.strftime("%Y-%m-%d %H:%M:%S"), concepto, cantidad, "INGRESO", "Ingreso_Bizum"))
        saldo_acumulado += cantidad

    # 4. Generar unos 250 movimientos aleatorios de gastos masivos bien repartidos
    print("🛍️ Insertando gastos cotidianos aleatorios...")
    for _ in range(250):
        fecha_aleatoria = fake.date_time_between_dates(datetime_start=fecha_inicio, datetime_end=datetime.now())
        cat = random.choice(list(categorias_gastos.keys()))
        concepto = random.choice(categorias_gastos[cat])
        
        if cat == "Hogar":
            cantidad = round(random.uniform(40.0, 110.0), 2)
        elif cat in ["Gasolina", "Supermercado", "Ropa"]:
            cantidad = round(random.uniform(25.0, 95.0), 2)
        elif cat == "Suscripciones":
            cantidad = round(random.uniform(9.99, 29.99), 2)
        else:
            whitespace = round(random.uniform(6.0, 50.0), 2)
            cantidad = whitespace

        movimientos.append((usuario_id, fecha_aleatoria.strftime("%Y-%m-%d %H:%M:%S"), concepto, cantidad, "GASTO", cat))
        saldo_acumulado -= cantidad

    cursor.executemany("INSERT INTO movimientos (usuario_id, fecha, concepto, cantidad, tipo, categoria) VALUES (?, ?, ?, ?, ?, ?)", 
                       movimientos)
    
    cursor.execute("UPDATE usuarios SET saldo_actual = ? WHERE id = ?", (round(saldo_acumulado, 2), usuario_id))

    conn.commit()
    conn.close()
    print("✅ Base de datos analítica ultra-avanzada lista con Bizums.")

if __name__ == "__main__":
    init_db()
    seed_data()