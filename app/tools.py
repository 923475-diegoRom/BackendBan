def simular_credito(monto: float, plazo_anios: int) -> dict:
    """Calcula la mensualidad de un crédito hipotecario"""
    tasa_anual = 0.095  # 9.5%
    tasa_mensual = tasa_anual / 12
    num_pagos = float(plazo_anios) * 12
    
    if num_pagos <= 0:
        return {
            "monto_solicitado": float(monto),
            "plazo_anios": plazo_anios,
            "pago_mensual_estimado": 0.0,
            "tasa_aplicada": "9.5% Fija"
        }
        
    mensualidad = (float(monto) * tasa_mensual) / (1 - (1 + tasa_mensual) ** -num_pagos)
    return {
        "monto_solicitado": float(monto),
        "plazo_anios": plazo_anios,
        "pago_mensual_estimado": round(mensualidad, 2),
        "tasa_aplicada": "9.5% Fija"
    }
