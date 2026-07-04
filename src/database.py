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
    
    # 1. USUARIOS
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS usuarios (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nombre TEXT NOT NULL,
            telefono TEXT NOT NULL,
            iban TEXT NOT NULL,
            saldo_actual REAL NOT NULL
        )
    ''')
    
    # 2. MOVIMIENTOS
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
    
    # 3. CONTACTOS
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS contactos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nombre TEXT NOT NULL,
            telefono TEXT NOT NULL
        )
    ''')

    # 4. FONDOS DISPONIBLES
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS fondos_disponibles (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nombre TEXT NOT NULL,
            riesgo TEXT NOT NULL,
            rentabilidad_anual_esperada REAL NOT NULL
        )
    ''')

    # 5. HISTÓRICO DE RENTABILIDAD
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS fondos_historico (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            fondo_id INTEGER,
            año_mes TEXT NOT NULL,
            rentabilidad_mes REAL NOT NULL,
            FOREIGN KEY(fondo_id) REFERENCES fondos_disponibles(id)
        )
    ''')

    # 6. INVERSIONES DEL USUARIO
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

    print("🚀 Generando ecosistema financiero con 12 meses REALES (Suscripciones mensuales fijas)...")

    # Insertar usuario principal
    cursor.execute("INSERT INTO usuarios (nombre, telefono, iban, saldo_actual) VALUES (?, ?, ?, ?)",
                   ("Sofia Heredia", "636636636", fake.iban(), 5000.0))
    usuario_id = cursor.lastrowid

    # 5 Fondos Diversificados
    fondos = [
        (1, "Fondo Tecnológico e IA Megatendencias", "Alto", 14.5),
        (2, "Indexado S&P 500 Global", "Medio", 8.5),
        (3, "Renta Fija del Estado (Bonos)", "Bajo", 3.2),
        (4, "Fondo Inmobiliario Rentas Europeas", "Medio", 5.5),
        (5, "Cripto-Activos de Alta Volatilidad", "Muy Alto", 22.0)
    ]
    cursor.executemany("INSERT INTO fondos_disponibles (id, nombre, riesgo, rentabilidad_anual_esperada) VALUES (?, ?, ?, ?)", fondos)

    # Histórico de 12 meses reales
    meses = [
        "2025-07", "2025-08", "2025-09", "2025-10", "2025-11", "2025-12",
        "2026-01", "2026-02", "2026-03", "2026-04", "2026-05", "2026-06"
    ]

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

    # Inversiones iniciales
    cursor.execute("INSERT INTO inversiones_usuario (usuario_id, fondo_id, capital_invertido) VALUES (?, ?, ?)", (usuario_id, 2, 2000.0))
    cursor.execute("INSERT INTO inversiones_usuario (usuario_id, fondo_id, capital_invertido) VALUES (?, ?, ?)", (usuario_id, 4, 1200.0))

    # Contactos de la agenda
    lista_contactos = [(fake.first_name(), f"6{random.randint(1000000, 9999999)}") for _ in range(10)]
    cursor.executemany("INSERT INTO contactos (nombre, telefono) VALUES (?, ?)", lista_contactos)
    nombres_contactos = [contacto[0] for contacto in lista_contactos]

    # Mapear Conceptos por Categoría (Suscripciones fuera de aquí)
    categorias_gastos = {
        "Gasolina": ["Gasolinera Repsol", "Cepsa", "Galp", "Shell"],
        "Supermercado": ["Mercadona", "Carrefour", "Lidl", "Alcampo"],
        "Comida": ["Uber Eats", "Just Eat", "McDonalds", "La Tagliatella", "Burger King"],
        "Ocio": ["Entradas Cine", "Concierto", "Escape Room", "Discoteca"],
        "Ropa": ["Zara", "Hollister", "Nike", "Decathlon"],
        "Salud": ["Farmacia", "Dentista", "Óptica"],
        "Hogar": ["Factura Luz", "Factura Agua", "Factura Wifi"]
    }

    # Diccionario explícito para procesar suscripciones una vez al mes de forma realista
    suscripciones_fijas = [
        {"concepto": "Netflix", "precio": 17.99, "dia": "05"},
        {"concepto": "Spotify", "precio": 10.99, "dia": "12"},
        {"concepto": "Amazon Prime", "precio": 4.99, "dia": "18"},
        {"concepto": "Gimnasio", "precio": 29.90, "dia": "02"}
    ]

    conceptos_bizum_ingreso = [
        "Cena del viernes", "Regalo de cumpleaños", "Piso compartido", 
        "Taxis compartidos", "Cañas", "Concierto", "Compra a medias"
    ]

    conceptos_bizum_gasto = [
        "Cena de ayer", "Regalo común", "Gasolina viaje", 
        "Entradas concierto", "Café", "Cervezas", "Almuerzo"
    ]

    saldo_acumulado = 12000.0 
    movimientos = []

    # 1. Ingresos fijos (12 Nóminas)
    print("💰 Insertando nóminas...")
    for mes in meses:
        fecha_nom = f"{mes}-28 10:00:00"
        movimientos.append((usuario_id, fecha_nom, "Nómina Mensual", 1950.0, "INGRESO", "Nomina"))
        saldo_acumulado += 1950.0

    # 2. Gastos fijos (12 Alquileres)
    print("🏠 Insertando alquileres...")
    for mes in meses:
        fecha_alquiler = f"{mes}-01 09:00:00"
        movimientos.append((usuario_id, fecha_alquiler, "Alquiler", 850.0, "GASTO", "Hogar"))
        saldo_acumulado -= 850.0

    # 3. NUEVO: Gastos fijos por Suscripciones (Se cargan estrictamente una vez al mes)
    print("📺 Insertando suscripciones mensuales fijas...")
    for mes in meses:
        for sub in suscripciones_fijas:
            fecha_sub = f"{mes}-{sub['dia']} 08:00:00"
            movimientos.append((usuario_id, fecha_sub, sub['concepto'], sub['precio'], "GASTO", "Suscripciones"))
            saldo_acumulado -= sub['precio']

    # 4. Ingresos por Bizum
    print("📲 Insertando ingresos por Bizum...")
    for _ in range(50):
        mes_elegido = random.choice(meses)
        dia_aleatorio = str(random.randint(1, 28)).zfill(2)
        hora_aleatoria = f"{str(random.randint(0, 23)).zfill(2)}:{str(random.randint(0, 59)).zfill(2)}:00"
        fecha_final = f"{mes_elegido}-{dia_aleatorio} {hora_aleatoria}"
        
        amigo = random.choice(nombres_contactos)
        motivo = random.choice(conceptos_bizum_ingreso)
        concepto = f"Bizum de {amigo}: {motivo}"
        cantidad = round(random.uniform(5.0, 45.0), 2)
        
        movimientos.append((usuario_id, fecha_final, concepto, cantidad, "INGRESO", "Ingreso_Bizum"))
        saldo_acumulado += cantidad

    # 5. Gastos por Bizum enviados
    print("💸 Insertando gastos por Bizum...")
    for _ in range(60):
        mes_elegido = random.choice(meses)
        dia_aleatorio = str(random.randint(1, 28)).zfill(2)
        hora_aleatoria = f"{str(random.randint(0, 23)).zfill(2)}:{str(random.randint(0, 59)).zfill(2)}:00"
        fecha_final = f"{mes_elegido}-{dia_aleatorio} {hora_aleatoria}"
        
        amigo = random.choice(nombres_contactos)
        motivo = random.choice(conceptos_bizum_gasto)
        concepto = f"Bizum enviado a {amigo}: {motivo}"
        cantidad = round(random.uniform(5.0, 35.0), 2)
        
        movimientos.append((usuario_id, fecha_final, concepto, cantidad, "GASTO", "Gasto_Bizum"))
        saldo_acumulado -= cantidad

    # 6. Gastos cotidianos aleatorios (600 movimientos sin duplicación de suscripciones)
    print("🛍️ Insertando gastos cotidianos aleatorios...")
    for _ in range(600):
        mes_elegido = random.choice(meses)
        dia_aleatorio = str(random.randint(1, 28)).zfill(2)
        hora_aleatoria = f"{str(random.randint(0, 23)).zfill(2)}:{str(random.randint(0, 59)).zfill(2)}:00"
        fecha_final = f"{mes_elegido}-{dia_aleatorio} {hora_aleatoria}"
        
        cat = random.choice(list(categorias_gastos.keys()))
        concepto = random.choice(categorias_gastos[cat])
        
        if cat == "Hogar":
            cantidad = round(random.uniform(40.0, 110.0), 2)
        elif cat in ["Gasolina", "Supermercado", "Ropa"]:
            cantidad = round(random.uniform(25.0, 95.0), 2)
        else:
            cantidad = round(random.uniform(6.0, 50.0), 2)

        movimientos.append((usuario_id, fecha_final, concepto, cantidad, "GASTO", cat))
        saldo_acumulado -= cantidad

    # Inserción masiva final limpia
    cursor.executemany("INSERT INTO movimientos (usuario_id, fecha, concepto, cantidad, tipo, categoria) VALUES (?, ?, ?, ?, ?, ?)", 
                       movimientos)
    
    # Actualización del saldo final del usuario
    cursor.execute("UPDATE usuarios SET saldo_actual = ? WHERE id = ?", (round(saldo_acumulado, 2), usuario_id))

    conn.commit()
    conn.close()
    print("✅ Base de datos analítica anual lista y 100% realista.")

if __name__ == "__main__":
    init_db()
    seed_data()