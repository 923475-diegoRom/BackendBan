import os
import sqlitecloud
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

def get_core_db_connection():
    db_url = os.getenv("SQLITE_CLOUD_URL_CORE")
    if not db_url:
        return None
    try:
        db_url = db_url.strip('"').strip("'")
        return sqlitecloud.connect(db_url)
    except Exception as e:
        print(f"Error connecting to Core Banking DB: {e}")
        return None

def init_core_db():
    conn = get_core_db_connection()
    if conn:
        try:
            cursor = conn.cursor()
            
            # Crear tablas
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS clientes (
                    cliente_id TEXT PRIMARY KEY,
                    nombre TEXT
                )
            ''')
            
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS cuentas (
                    cuenta_id TEXT PRIMARY KEY,
                    cliente_id TEXT,
                    tipo TEXT,
                    saldo REAL,
                    FOREIGN KEY(cliente_id) REFERENCES clientes(cliente_id)
                )
            ''')
            
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS productos (
                    producto_id TEXT PRIMARY KEY,
                    cliente_id TEXT,
                    nombre TEXT,
                    detalle TEXT,
                    FOREIGN KEY(cliente_id) REFERENCES clientes(cliente_id)
                )
            ''')

            cursor.execute('''
                CREATE TABLE IF NOT EXISTS contactos (
                    contacto_id TEXT PRIMARY KEY,
                    cliente_id TEXT,
                    alias TEXT,
                    cuenta_destino TEXT,
                    FOREIGN KEY(cliente_id) REFERENCES clientes(cliente_id)
                )
            ''')

            cursor.execute('''
                CREATE TABLE IF NOT EXISTS transacciones (
                    tx_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    cliente_id TEXT,
                    tipo TEXT,
                    monto REAL,
                    cuenta_destino TEXT,
                    fecha DATETIME DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY(cliente_id) REFERENCES clientes(cliente_id)
                )
            ''')
            
            # Semilla de datos simulados para el cliente C-TEST
            cursor.execute("INSERT OR IGNORE INTO clientes (cliente_id, nombre) VALUES ('C-TEST', 'Usuario Test')")
            cursor.execute("INSERT OR IGNORE INTO cuentas (cuenta_id, cliente_id, tipo, saldo) VALUES ('CTA-9999', 'C-TEST', 'Débito', 100000.00)")
            cursor.execute("INSERT OR IGNORE INTO productos (producto_id, cliente_id, nombre, detalle) VALUES ('PRD-TDC-TEST', 'C-TEST', 'Tarjeta de Crédito Infinite', 'Límite: $500,000')")
            
            # Contactos de prueba
            cursor.execute("INSERT OR IGNORE INTO contactos (contacto_id, cliente_id, alias, cuenta_destino) VALUES ('CONT-1', 'C-TEST', 'Mamá', '99991111')")
            cursor.execute("INSERT OR IGNORE INTO contactos (contacto_id, cliente_id, alias, cuenta_destino) VALUES ('CONT-2', 'C-TEST', 'Renta', '55552222')")
            
            conn.commit()
        except Exception as e:
            print(f"Error initializing Core Banking DB: {e}")
        finally:
            conn.close()

def consultar_saldo(cliente_id: str) -> str:
    conn = get_core_db_connection()
    if not conn: return "Servicio no disponible temporalmente."
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT cuenta_id, tipo, saldo FROM cuentas WHERE cliente_id = ?", (cliente_id,))
        cuentas = cursor.fetchall()
        if not cuentas:
            return "No tienes cuentas registradas."
        
        resultado = "Saldos actuales:\n"
        for cta in cuentas:
            resultado += f"- Cuenta {cta[1]} ({cta[0]}): ${cta[2]:,.2f} MXN\n"
        return resultado
    finally:
        conn.close()

def consultar_productos(cliente_id: str) -> str:
    conn = get_core_db_connection()
    if not conn: return "Servicio no disponible temporalmente."
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT nombre, detalle FROM productos WHERE cliente_id = ?", (cliente_id,))
        productos = cursor.fetchall()
        if not productos:
            return "No tienes productos contratados."
        
        resultado = "Tus productos contratados:\n"
        for prod in productos:
            resultado += f"- {prod[0]} ({prod[1]})\n"
        return resultado
    finally:
        conn.close()

def consultar_contactos(cliente_id: str) -> str:
    conn = get_core_db_connection()
    if not conn: return "Servicio no disponible temporalmente."
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT alias, cuenta_destino FROM contactos WHERE cliente_id = ?", (cliente_id,))
        contactos = cursor.fetchall()
        if not contactos:
            return "No tienes contactos guardados."
        
        resultado = "Tus contactos frecuentes:\n"
        for cont in contactos:
            resultado += f"- {cont[0]} (Cuenta: {cont[1]})\n"
        return resultado
    finally:
        conn.close()

def consultar_transacciones(cliente_id: str) -> str:
    conn = get_core_db_connection()
    if not conn: return "Servicio no disponible temporalmente."
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT tipo, monto, cuenta_destino, fecha FROM transacciones WHERE cliente_id = ? ORDER BY fecha DESC LIMIT 5", (cliente_id,))
        transacciones = cursor.fetchall()
        if not transacciones:
            return "No tienes transacciones recientes."
        
        resultado = "Tus últimas transacciones:\n"
        for tx in transacciones:
            resultado += f"- {tx[3]}: {tx[0]} de ${tx[1]:,.2f} hacia la cuenta {tx[2]}\n"
        return resultado
    finally:
        conn.close()


def hacer_transferencia(cliente_id: str, cuenta_destino: str, monto: float) -> str:
    conn = get_core_db_connection()
    if not conn: return "Servicio no disponible temporalmente."
    try:
        cursor = conn.cursor()
        cuenta_destino_limpia = cuenta_destino.lower().replace("cuenta de", "").strip()
        
        # Intentar resolver cuenta_destino por alias en contactos
        cursor.execute(
            "SELECT cuenta_destino FROM contactos WHERE cliente_id = ? AND (LOWER(alias) = LOWER(?) OR LOWER(alias) = ?)", 
            (cliente_id, cuenta_destino, cuenta_destino_limpia)
        )
        contacto = cursor.fetchone()
        
        cuenta_final = contacto[0] if contacto else cuenta_destino
        
        # Validar si tiene saldo en su primera cuenta
        cursor.execute("SELECT cuenta_id, saldo FROM cuentas WHERE cliente_id = ? LIMIT 1", (cliente_id,))
        cuenta = cursor.fetchone()
        
        if not cuenta:
            return "No tienes cuentas desde donde transferir."
        
        cuenta_origen = cuenta[0]
        saldo_actual = float(cuenta[1])
        
        if saldo_actual < monto:
            return f"Saldo insuficiente. Tu saldo es ${saldo_actual:,.2f} y quieres transferir ${monto:,.2f}."
            
        nuevo_saldo = saldo_actual - monto
        
        # Actualizar saldo
        cursor.execute("UPDATE cuentas SET saldo = ? WHERE cuenta_id = ?", (nuevo_saldo, cuenta_origen))
        
        # Guardar en transacciones
        cursor.execute(
            "INSERT INTO transacciones (cliente_id, tipo, monto, cuenta_destino) VALUES (?, ?, ?, ?)",
            (cliente_id, "Transferencia Enviada", monto, cuenta_final)
        )
        
        conn.commit()
        
        return f"✅ Transferencia exitosa de ${monto:,.2f} MXN a la cuenta {cuenta_final}. Tu nuevo saldo es ${nuevo_saldo:,.2f} MXN."
    except Exception as e:
        conn.rollback()
        return f"Error procesando la transferencia: {str(e)}"
    finally:
        conn.close()
