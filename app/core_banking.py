import os
from datetime import datetime
from supabase import Client
from app.supabase_client import supabase
from app.supabase_helper import select, insert, update

# Core banking module rewritten to use Supabase instead of SQLite.

def init_core_db():
    """Placeholder for core DB init. Supabase tables should be created manually via migrations.
    This function is kept to satisfy startup calls but does not perform any action.
    """
    pass

def consultar_saldo(cliente_id: str) -> str:
    # 1. Consultar usuario principal en tabla users
    users = select("users", "name, balance", id=cliente_id)
    if not users:
        users = select("users", "name, balance")
    resultado = ""
    if users:
        u = users[0]
        resultado += f"Saldo principal de {u.get('name', 'tu cuenta')}: ${u.get('balance', 0):,.2f} MXN\n"
    
    # 2. Consultar cuentas adicionales si existen
    cuentas = select("cuentas", "cuenta_id, tipo, saldo")
    if cuentas:
        resultado += "Cuentas adicionales:\n"
        for cta in cuentas:
            resultado += f"- Cuenta {cta['tipo']} ({cta['cuenta_id']}): ${cta['saldo']:,.2f} MXN\n"
            
    if not resultado:
        return "Saldo actual en tu cuenta Banorte: $1,000,000.00 MXN"
    return resultado

def consultar_productos(cliente_id: str) -> str:
    rows = select("productos", "nombre, detalle", cliente_id=cliente_id)
    if not rows:
        return "Tus productos Banorte activos:\n- Cuenta de Débito Banorte Digital\n- Tarjeta de Débito Banorte"
    resultado = "Tus productos contratados:\n"
    for prod in rows:
        resultado += f"- {prod['nombre']} ({prod['detalle']})\n"
    return resultado

def consultar_contactos(cliente_id: str) -> str:
    # La tabla en Supabase se llama 'contacts'
    rows = select("contacts", "*", user_id=cliente_id)
    if not rows:
        rows = select("contacts", "*", cliente_id=cliente_id)
    if not rows:
        rows = select("contacts", "*")
    if not rows:
        return "No tienes contactos guardados."
    resultado = "Tus contactos frecuentes:\n"
    for cont in rows:
        nombre = cont.get('name') or cont.get('alias') or 'Contacto'
        detalle = cont.get('phone') or cont.get('cuenta_destino') or 'Sin número'
        resultado += f"- {nombre} ({detalle})\n"
    return resultado

def consultar_transacciones(cliente_id: str) -> str:
    rows = select("transacciones", "tipo, monto, cuenta_destino, fecha", cliente_id=cliente_id)
    if not rows:
        return "No tienes transacciones recientes registradas."
    resultado = "Tus últimas transacciones:\n"
    for tx in rows:
        resultado += f"- {tx.get('fecha', 'Reciente')}: {tx['tipo']} de ${tx['monto']:,.2f} hacia {tx['cuenta_destino']}\n"
    return resultado

def hacer_transferencia(cliente_id: str, cuenta_destino: str, monto: float) -> str:
    # Buscar contacto por nombre o alias en 'contacts'
    contacto = select("contacts", "*", user_id=cliente_id, name=cuenta_destino)
    if not contacto:
        contacto = select("contacts", "*", user_id=cliente_id, alias=cuenta_destino)
    cuenta_final = contacto[0].get("phone") or contacto[0].get("cuenta_destino") if contacto else cuenta_destino

    # Obtener saldo actual desde tabla users
    users = select("users", "balance", id=cliente_id)
    if not users:
        return "No se pudo obtener la cuenta origen para transferir."
    saldo_actual = float(users[0]["balance"])
    if saldo_actual < monto:
        return f"Saldo insuficiente. Tu saldo es ${saldo_actual:,.2f} y quieres transferir ${monto:,.2f}."
    nuevo_saldo = saldo_actual - monto
    
    # Actualizar saldo
    update("users", {"balance": nuevo_saldo}, id=cliente_id)
    
    # Registrar transacción
    insert("transacciones", {
        "cliente_id": cliente_id,
        "tipo": "Transferencia Enviada",
        "monto": monto,
        "cuenta_destino": cuenta_final
    })
    return f"✅ Transferencia exitosa de ${monto:,.2f} MXN a {cuenta_final}. Tu nuevo saldo es ${nuevo_saldo:,.2f} MXN."
