from langchain.tools import tool
from app.core_banking import consultar_saldo, consultar_productos, hacer_transferencia, consultar_contactos, consultar_transacciones
from app.rag import search_context
from app.tools import simular_credito as sim_credito_func
from typing import Union

def get_agent_tools_for_user(user_id: str):
    """Crea un conjunto de herramientas del agente enlazadas de forma segura y estricta
    únicamente al ID del usuario autenticado. Ningún usuario puede ver ni operar sobre datos de otro.
    """
    @tool
    def herramienta_ver_saldo() -> str:
        """Útil para consultar el saldo de la cuenta del usuario autenticado."""
        return consultar_saldo(user_id)

    @tool
    def herramienta_ver_productos() -> str:
        """Útil para consultar los productos contratados del usuario autenticado."""
        return consultar_productos(user_id)

    @tool
    def herramienta_ver_contactos() -> str:
        """Útil para consultar la lista de contactos frecuentes del usuario autenticado."""
        return consultar_contactos(user_id)

    @tool
    def herramienta_ver_transacciones() -> str:
        """Útil para consultar el historial de movimientos del usuario autenticado."""
        return consultar_transacciones(user_id)

    @tool
    def herramienta_transferir_dinero(cuenta_destino: str, monto: Union[float, str]) -> str:
        """Útil para transferir dinero desde la cuenta del usuario autenticado a otra cuenta destino."""
        try:
            monto_f = float(monto)
        except ValueError:
            return "Error: el monto debe ser un número válido."
        return hacer_transferencia(user_id, cuenta_destino, monto_f)

    @tool
    def herramienta_simular_credito(monto: Union[float, str], plazo_anios: Union[int, str]) -> str:
        """Útil para simular un crédito hipotecario."""
        try:
            monto_f = float(monto)
            plazo_i = int(plazo_anios)
        except ValueError:
            return "Error: el monto y el plazo deben ser números válidos."
            
        if plazo_i <= 0:
            return "Error: El plazo en años debe ser mayor a 0."
            
        resultado = sim_credito_func(monto_f, plazo_i)
        return f"Simulación completada: Monto {resultado['monto_solicitado']}, Plazo {resultado['plazo_anios']} años. Pago mensual estimado: ${resultado['pago_mensual_estimado']} con Tasa de {resultado['tasa_aplicada']}."

    @tool
    def herramienta_buscar_info_institucional(pregunta: str) -> str:
        """Útil para responder dudas generales del banco, requisitos, reglas de tarjetas, anualidades, etc."""
        context, sources = search_context(pregunta)
        import json
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

