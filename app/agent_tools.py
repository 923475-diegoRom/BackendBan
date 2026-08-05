from langchain.tools import tool
from app.core_banking import consultar_saldo, consultar_productos, hacer_transferencia, consultar_contactos, consultar_transacciones
from app.rag import search_context
from app.tools import simular_credito as sim_credito_func

# Identidad estática para las pruebas
CURRENT_USER_ID = "C-TEST"

@tool
def herramienta_ver_saldo() -> str:
    """Útil para consultar el saldo de las cuentas del usuario actual."""
    return consultar_saldo(CURRENT_USER_ID)

@tool
def herramienta_ver_productos() -> str:
    """Útil para consultar los productos contratados (tarjetas, créditos, inversiones) del usuario actual."""
    return consultar_productos(CURRENT_USER_ID)

@tool
def herramienta_ver_contactos() -> str:
    """Útil para consultar la lista de contactos frecuentes y sus cuentas destino a los que el usuario puede transferir dinero."""
    return consultar_contactos(CURRENT_USER_ID)

@tool
def herramienta_ver_transacciones() -> str:
    """Útil para consultar el historial o estado de cuenta con los últimos movimientos y transacciones del usuario."""
    return consultar_transacciones(CURRENT_USER_ID)

@tool
def herramienta_transferir_dinero(cuenta_destino: str, monto: float) -> str:
    """Útil para transferir dinero desde la cuenta del usuario a otra cuenta destino.
    Requiere la cuenta destino y el monto a transferir.
    """
    return hacer_transferencia(CURRENT_USER_ID, cuenta_destino, monto)

@tool
def herramienta_simular_credito(monto: float, plazo_anios: int) -> str:
    """Útil para simular un crédito hipotecario. 
    Requiere el monto del préstamo y el plazo en años.
    """
    resultado = sim_credito_func(monto, plazo_anios)
    return f"Simulación completada: Monto {resultado['monto_solicitado']}, Plazo {resultado['plazo_anios']} años. Pago mensual estimado: ${resultado['pago_mensual_estimado']} con Tasa de {resultado['tasa_aplicada']}."

@tool
def herramienta_buscar_info_institucional(pregunta: str) -> str:
    """Útil para responder dudas generales del banco, requisitos, reglas de tarjetas, anualidades, etc.
    Hace una búsqueda en la base de conocimientos interna del banco (RAG).
    """
    context, sources = search_context(pregunta)
    import json
    return json.dumps({
        "info": context,
        "fuentes_usadas": sources
    }, ensure_ascii=False)

# Lista maestra de herramientas
get_agent_tools = [
    herramienta_ver_saldo,
    herramienta_ver_productos,
    herramienta_ver_contactos,
    herramienta_ver_transacciones,
    herramienta_transferir_dinero,
    herramienta_simular_credito,
    herramienta_buscar_info_institucional
]
