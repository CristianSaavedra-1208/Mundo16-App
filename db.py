import sqlite3
import pandas as pd

DB_NAME = "ifrs16_platinum.db"

def conectar():
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    return conn

def inicializar_db():
    conn = conectar()
    cursor = conn.cursor()
    cursor.execute('''CREATE TABLE IF NOT EXISTS monedas 
                      (fecha TEXT, moneda TEXT, valor REAL, PRIMARY KEY(fecha, moneda))''')
    cursor.execute('''CREATE TABLE IF NOT EXISTS contratos (
                        Codigo_Interno TEXT PRIMARY KEY, Empresa TEXT, Clase_Activo TEXT, 
                        ID TEXT, Proveedor TEXT, Cod1 TEXT, Cod2 TEXT, Nombre TEXT, 
                        Moneda TEXT, Canon REAL, Tasa REAL, Tasa_Mensual REAL,
                        Valor_Moneda_Inicio REAL, Plazo INTEGER, Inicio TEXT, Fin TEXT, 
                        Estado TEXT DEFAULT 'Activo', Fecha_Baja TEXT, 
                        Ajuste_ROU REAL DEFAULT 0.0, Tipo_Pago TEXT DEFAULT 'Vencido',
                        Fecha_Remedicion TEXT)''')
                        
    cursor.execute('''CREATE TABLE IF NOT EXISTS remediciones (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        Codigo_Interno TEXT, Fecha_Remedicion TEXT,
                        Canon REAL, Tasa REAL, Tasa_Mensual REAL,
                        Fin TEXT, Plazo INTEGER, Ajuste_ROU REAL,
                        FOREIGN KEY(Codigo_Interno) REFERENCES contratos(Codigo_Interno))''')
                        
    cursor.execute('''CREATE TABLE IF NOT EXISTS config_params (
                        tipo TEXT, valor TEXT, PRIMARY KEY(tipo, valor))''')
                        
    cursor.execute('''CREATE TABLE IF NOT EXISTS usuarios (
                        usuario TEXT PRIMARY KEY, password_hash TEXT)''')
    
    # Migraciones para agregar componentes del ROU y Remedición
    nuevas_columnas = {
        'Costos_Directos': 'REAL DEFAULT 0.0',
        'Pagos_Anticipados': 'REAL DEFAULT 0.0',
        'Costos_Desmantelamiento': 'REAL DEFAULT 0.0',
        'Incentivos': 'REAL DEFAULT 0.0',
        'Fecha_Remedicion': 'TEXT'
    }
    for col, tipo in nuevas_columnas.items():
        try:
            cursor.execute(f"ALTER TABLE contratos ADD COLUMN {col} {tipo}")
        except sqlite3.OperationalError:
            pass # La columna ya existe
            
    # Insertar admin por defecto si no hay usuarios
    cursor.execute("SELECT count(*) as c FROM usuarios")
    if cursor.fetchone()['c'] == 0:
        h = hashlib.sha256("1234".encode()).hexdigest()
        cursor.execute("INSERT INTO usuarios VALUES ('admin', ?)", (h,))
        
    # Parámetros por defecto
    cursor.execute("SELECT count(*) as c FROM config_params")
    if cursor.fetchone()['c'] == 0:
        defaults = [('EMPRESA', 'Holdco'), ('EMPRESA', 'Pacifico'),
                    ('CLASE_ACTIVO', 'Oficinas'), ('CLASE_ACTIVO', 'Vehículos'),
                    ('CLASE_ACTIVO', 'Maquinaria'), ('CLASE_ACTIVO', 'Bodegas'),
                    ('CLASE_ACTIVO', 'Inmuebles'),
                    ('CUENTA_ROU_NUM', '1401'), ('CUENTA_ROU_NOM', 'Activo Derecho de Uso ROU'),
                    ('CUENTA_PASIVO_NUM', '2101'), ('CUENTA_PASIVO_NOM', 'Pasivo por Arrendamiento IFRS 16'),
                    ('CUENTA_BCO_AJUSTE_NUM', '1101'), ('CUENTA_BCO_AJUSTE_NOM', 'Banco / Provisiones Ajuste Inicial'),
                    ('CUENTA_GASTO_AMORT_NUM', '4101'), ('CUENTA_GASTO_AMORT_NOM', 'Gasto Amortización ROU'),
                    ('CUENTA_AMORT_ACUM_NUM', '1402'), ('CUENTA_AMORT_ACUM_NOM', 'Amortización Acumulada ROU'),
                    ('CUENTA_GASTO_INT_NUM', '4201'), ('CUENTA_GASTO_INT_NOM', 'Gasto Financiero Interés'),
                    ('CUENTA_BANCO_PAGO_NUM', '1102'), ('CUENTA_BANCO_PAGO_NOM', 'Banco / Efectivo'),
                    ('CUENTA_PERDIDA_TC_NUM', '4301'), ('CUENTA_PERDIDA_TC_NOM', 'Pérdida por Dif. Cambio'),
                    ('CUENTA_GANANCIA_TC_NUM', '4302'), ('CUENTA_GANANCIA_TC_NOM', 'Ganancia por Dif. Cambio')]
        cursor.executemany("INSERT INTO config_params VALUES (?,?)", defaults)
        
    conn.commit()
    conn.close()

import os
import hashlib

def verificar_credenciales(u, p):
    conn = conectar()
    cursor = conn.cursor()
    cursor.execute("SELECT password_hash FROM usuarios WHERE usuario=?", (u,))
    row = cursor.fetchone()
    conn.close()
    if row:
        return hashlib.sha256(p.encode()).hexdigest() == row['password_hash']
    return False

def agregar_usuario(u, p):
    conn = conectar()
    h = hashlib.sha256(p.encode()).hexdigest()
    conn.execute("INSERT OR REPLACE INTO usuarios VALUES (?,?)", (u, h))
    conn.commit()
    conn.close()

def obtener_usuarios():
    conn = conectar()
    df = pd.read_sql("SELECT usuario FROM usuarios", conn)
    conn.close()
    return df['usuario'].tolist()

def obtener_parametros(tipo):
    conn = conectar()
    df = pd.read_sql(f"SELECT valor FROM config_params WHERE tipo='{tipo}'", conn)
    conn.close()
    return df['valor'].tolist()

def agregar_parametro(tipo, valor):
    conn = conectar()
    conn.execute("INSERT OR IGNORE INTO config_params VALUES (?,?)", (tipo, valor))
    conn.commit()
    conn.close()

def eliminar_parametro(tipo, valor):
    conn = conectar()
    conn.execute("DELETE FROM config_params WHERE tipo=? AND valor=?", (tipo, valor))
    conn.commit()
    conn.close()

def cargar_monedas():
    conn = conectar()
    df = pd.read_sql("SELECT * FROM monedas ORDER BY fecha DESC", conn)
    conn.close()
    return df

def insertar_moneda(f, m, v):
    conn = conectar()
    conn.execute("INSERT OR REPLACE INTO monedas VALUES (?,?,?)", (f, m, v))
    conn.commit()
    conn.close()

def cargar_masivo_monedas(df):
    conn = conectar()
    cursor = conn.cursor()
    df.columns = [c.lower().strip() for c in df.columns]
    for _, fila in df.iterrows():
        fecha_str = pd.to_datetime(fila['fecha']).strftime('%Y-%m-%d')
        cursor.execute('''INSERT OR REPLACE INTO monedas (fecha, moneda, valor) 
                          VALUES (?, ?, ?)''', (fecha_str, str(fila['moneda']), float(fila['valor'])))
    conn.commit()
    conn.close()

def cargar_contratos():
    conn = conectar()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM contratos")
    rows = [dict(r) for r in cursor.fetchall()]
    conn.close()
    return rows

def insertar_contrato(c):
    conn = conectar()
    
    # Asegurar llaves para nuevas columnas
    for campo in ['Costos_Directos', 'Pagos_Anticipados', 'Costos_Desmantelamiento', 'Incentivos', 'Ajuste_ROU']:
        if campo not in c: c[campo] = 0.0
        
    conn.execute('''INSERT INTO contratos (Codigo_Interno, Empresa, Clase_Activo, ID, Proveedor, 
                    Cod1, Cod2, Nombre, Moneda, Canon, Tasa, Tasa_Mensual, 
                    Valor_Moneda_Inicio, Plazo, Inicio, Fin, Estado, Tipo_Pago,
                    Costos_Directos, Pagos_Anticipados, Costos_Desmantelamiento, Incentivos, Ajuste_ROU) 
                    VALUES (:Codigo_Interno, :Empresa, :Clase_Activo, :ID, :Proveedor, 
                    :Cod1, :Cod2, :Nombre, :Moneda, :Canon, :Tasa, :Tasa_Mensual, 
                    :Valor_Moneda_Inicio, :Plazo, :Inicio, :Fin, :Estado, :Tipo_Pago,
                    :Costos_Directos, :Pagos_Anticipados, :Costos_Desmantelamiento, :Incentivos, :Ajuste_ROU)''', c)
    conn.commit()
    conn.close()

def dar_baja_contrato(cod, fecha):
    conn = conectar()
    conn.execute("UPDATE contratos SET Estado='Baja', Fecha_Baja=? WHERE Codigo_Interno=?", (fecha, cod))
    conn.commit()
    conn.close()

def marcar_contrato_remedido(cod, fecha):
    conn = conectar()
    conn.execute("UPDATE contratos SET Estado='Remedido', Fecha_Baja=? WHERE Codigo_Interno=?", (fecha, cod))
    conn.commit()
    conn.close()

def actualizar_contrato_remedicion(cod, can, tas, t_m, fin, p, f_rem):
    conn = conectar()
    conn.execute("UPDATE contratos SET Canon=?, Tasa=?, Tasa_Mensual=?, Fin=?, Plazo=?, Fecha_Remedicion=? WHERE Codigo_Interno=?", 
                 (can, tas, t_m, fin, p, f_rem, cod))
    conn.commit()
    conn.close()

def insertar_remedicion(cod, f_rem, can, tas, t_m, fin, p, aj_rou):
    conn = conectar()
    conn.execute("INSERT INTO remediciones (Codigo_Interno, Fecha_Remedicion, Canon, Tasa, Tasa_Mensual, Fin, Plazo, Ajuste_ROU) VALUES (?,?,?,?,?,?,?,?)", 
                 (cod, f_rem, can, tas, t_m, fin, p, aj_rou))
    conn.commit()
    conn.close()

def cargar_remediciones(cod=None):
    conn = conectar()
    if cod:
        df = pd.read_sql(f"SELECT * FROM remediciones WHERE Codigo_Interno='{cod}' ORDER BY Fecha_Remedicion ASC", conn)
    else:
        df = pd.read_sql("SELECT * FROM remediciones ORDER BY Codigo_Interno, Fecha_Remedicion ASC", conn)
    conn.close()
    return [dict(r) for _, r in df.iterrows()]

def limpiar_monedas():
    conn = conectar()
    conn.execute("DELETE FROM monedas")
    conn.commit()
    conn.close()

def limpiar_contratos():
    conn = conectar()
    conn.execute("DELETE FROM contratos")
    conn.execute("DELETE FROM remediciones")
    conn.commit()
    conn.close()

inicializar_db()