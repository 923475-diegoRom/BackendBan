import re
import json
from typing import Union
from langchain.tools import tool
from app.core_banking import consultar_saldo, consultar_productos, hacer_transferencia, consultar_contactos, consultar_transacciones
from app.rag import search_context
from app.tools import simular_credito as sim_credito_func

def _clean_number(val: Union[float, int, str]) -> float:
    if isinstance(val, (int, float)):
        return float(val)
    cleaned = re.sub(r'[^\d.]', '', str(val))
    try:
        return float(cleaned)
    except ValueError:
        return 0.0

def _clean_int(val: Union[int, float, str]) -> int:
    if isinstance(val, int):
        return val
    cleaned = re.sub(r'[^\d]', '', str(val))
    try:
        return int(cleaned)
    except ValueError:
        return 0

def get_agent_tools_for_user(user_id: str):
    """Crea un conjunto de herramientas del agente enlazadas de forma segura y estricta
    únicamente al ID del usuario autenticado. Ningún usuario puede ver ni operar sobre datos de otro.
    """
    @tool
    def herramienta_ver_saldo() -> str:
        """Útil ÚNICAMENTE cuando el usuario solicita explícitamente consultar su saldo actual."""
        return consultar_saldo(user_id)

    @tool
    def herramienta_ver_productos() -> str:
        """Útil ÚNICAMENTE cuando el usuario solicita consultar sus productos contratados (tarjetas, créditos, inversiones)."""
        return consultar_productos(user_id)

    @tool
    def herramienta_ver_contactos() -> str:
        """Útil ÚNICAMENTE cuando el usuario solicita consultar su lista de contactos frecuentes o cuentas destino."""
        return consultar_contactos(user_id)

    @tool
    def herramienta_ver_transacciones() -> str:
        """Útil ÚNICAMENTE cuando el usuario solicita su historial de movimientos o últimas transacciones."""
        return consultar_transacciones(user_id)

    @tool
    def herramienta_transferir_dinero(cuenta_destino: str, monto: Union[float, str]) -> str:
        """Útil ÚNICAMENTE cuando el usuario solicita realizar una transferencia a una cuenta o contacto especificando un monto."""
        monto_f = _clean_number(monto)
        if monto_f <= 0:
            return "Error: Pasa únicamente un monto numérico positivo (ejemplo: 5000)."
        return hacer_transferencia(user_id, cuenta_destino, monto_f)

    @tool
    def herramienta_simular_credito(monto: Union[float, str], plazo_anios: Union[int, str]) -> str:
        """Útil ÚNICAMENTE cuando el usuario solicita simular un crédito o préstamo indicando monto y plazo."""
        monto_f = _clean_number(monto)
        plazo_i = _clean_int(plazo_anios)
        if monto_f <= 0 or plazo_i <= 0:
            return "Error: El monto y el plazo en años deben ser números mayores a 0."
        resultado = sim_credito_func(monto_f, plazo_i)
        return f"Simulación completada: Monto {resultado['monto_solicitado']}, Plazo {resultado['plazo_anios']} años. Pago mensual estimado: ${resultado['pago_mensual_estimado']} con Tasa de {resultado['tasa_aplicada']}."

    @tool
    def herramienta_buscar_info_institucional(pregunta: str) -> str:
        """Útil ÚNICAMENTE para responder dudas sobre reglamentos, políticas, tarjetas de crédito/nómina o información general de Banorte."""
        context, sources = search_context(pregunta)
        return json.dumps({
            "info": context,
            "fuentes_usadas": sources
        }, ensure_ascii=False)

    return [
        herramienta_ver_saldo,
        herramienta_ver_productos,
        herramienta_ver_contactos,
        herramienta_ver_transacciones,
        herramienta_transferir_dinero,
        herramienta_simular_credito,
        herramienta_buscar_info_institucional
    ]

# Herramientas por defecto para retrocompatibilidad
get_agent_tools = get_agent_tools_for_user("demo-user")

