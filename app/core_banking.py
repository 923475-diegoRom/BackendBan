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
    rows = select("cuentas", "cuenta_id, tipo, saldo", cliente_id=cliente_id)
    if not rows:
        return "No tienes cuentas registradas."
    resultado = "Saldos actuales:\n"
    for cta in rows:
        resultado += f"- Cuenta {cta['tipo']} ({cta['cuenta_id']}): ${cta['saldo']:,.2f} MXN\n"
    return resultado

def consultar_productos(cliente_id: str) -> str:
    rows = select("productos", "nombre, detalle", cliente_id=cliente_id)
    if not rows:
        return "No tienes productos contratados."
    resultado = "Tus productos contratados:\n"
    for prod in rows:
        resultado += f"- {prod['nombre']} ({prod['detalle']})\n"
    return resultado

def consultar_contactos(cliente_id: str) -> str:
    rows = select("contactos", "alias, cuenta_destino", cliente_id=cliente_id)
    if not rows:
        return "No tienes contactos guardados."
    resultado = "Tus contactos frecuentes:\n"
    for cont in rows:
        resultado += f"- {cont['alias']} (Cuenta: {cont['cuenta_destino']})\n"
    return resultado

def consultar_transacciones(cliente_id: str) -> str:
    rows = select("transacciones", "tipo, monto, cuenta_destino, fecha", cliente_id=cliente_id)
    if not rows:
        return "No tienes transacciones recientes."
    resultado = "Tus últimas transacciones:\n"
    for tx in rows:
        resultado += f"- {tx['fecha']}: {tx['tipo']} de ${tx['monto']:,.2f} hacia la cuenta {tx['cuenta_destino']}\n"
    return resultado

def hacer_transferencia(cliente_id: str, cuenta_destino: str, monto: float) -> str:
    # Resolve destination account via contacts if alias provided
    contacto = select("contactos", "cuenta_destino", cliente_id=cliente_id, alias=cuenta_destino)
    cuenta_final = contacto[0]["cuenta_destino"] if contacto else cuenta_destino
    # Get first account for origin
    cuentas = select("cuentas", "cuenta_id, saldo", cliente_id=cliente_id)
    if not cuentas:
        return "No tienes cuentas desde donde transferir."
    cuenta_origen = cuentas[0]["cuenta_id"]
    saldo_actual = float(cuentas[0]["saldo"])
    if saldo_actual < monto:
        return f"Saldo insuficiente. Tu saldo es ${saldo_actual:,.2f} y quieres transferir ${monto:,.2f}."
    nuevo_saldo = saldo_actual - monto
    # Update origin balance
    update("cuentas", {"saldo": nuevo_saldo}, cuenta_id=cuenta_origen)
    # Insert transaction record
    insert("transacciones", {
        "cliente_id": cliente_id,
        "tipo": "Transferencia Enviada",
        "monto": monto,
        "cuenta_destino": cuenta_final
    })
    return f"✅ Transferencia exitosa de ${monto:,.2f} MXN a la cuenta {cuenta_final}. Tu nuevo saldo es ${nuevo_saldo:,.2f} MXN."
