import os
import json
import httpx

from src.backend.services import db_service

OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://ollama:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "qwen2.5:3b-instruct")

SYSTEM_PROMPT = """Eres el asistente financiero de un banco. Hablas en español, de forma clara, \
breve y natural, como si hablaras con el cliente por teléfono.\

Tienes acceso a estas herramientas:
- consultar_saldo: para saber cuánto dinero tiene disponible el usuario.
- hacer_bizum: para enviar dinero a un contacto. Úsala SOLO si el usuario pide explícitamente \
enviar, mandar o pasar dinero a alguien.
- consultar_movimientos: para responder preguntas sobre el histórico de movimientos (gastos, \
ingresos, categorías, fechas concretas). Escribes tú mismo la sentencia SQL SELECT.

Esquema de la tabla `movimientos` en SQLite (usa exactamente estos nombres):
- id INTEGER
- usuario_id INTEGER
- fecha TEXT (formato 'YYYY-MM-DD HH:MM:SS')
- concepto TEXT
- cantidad REAL (siempre positiva; el signo lo indica la columna tipo)
- tipo TEXT ('INGRESO' o 'GASTO')
- categoria TEXT (valores posibles: 'Gasolina', 'Supermercado', 'Comida', 'Ocio', 'Ropa', \
'Salud', 'Hogar', 'Suscripciones', 'Nomina', 'Ingreso_Bizum', 'Gasto_Bizum')

Reglas:
- Si la pregunta no necesita ninguna herramienta (saludo, charla general relacionada contigo \
como asistente), responde directamente.
- Si la pregunta NO tiene nada que ver con finanzas, banca o tus herramientas (por ejemplo, \
temas de cultura general, el tiempo, chistes, recetas...), indícalo con amabilidad en una \
frase corta y redirige hacia lo que sí puedes hacer. No intentes responderla igualmente.
- Para cualquier pregunta sobre el histórico, usa SIEMPRE consultar_movimientos con SQL válido, \
filtrando siempre por usuario_id = 1.
- Nunca inventes cifras. Si una herramienta devuelve un error, explícaselo al usuario con \
naturalidad, no expongas el error técnico tal cual.
- NUNCA digas que una operación (como un Bizum) se ha completado si no acabas de recibir la \
confirmación de la herramienta correspondiente EN ESTE MISMO TURNO. Si el usuario confirma una \
acción pendiente (dice "confirmo", "sí", "hazlo", etc.), debes volver a invocar la herramienta \
ahora mismo — nunca asumas que ya se ejecutó por el hecho de que se mencionó antes.
- Sé breve: 1-3 frases, salvo que el usuario pida detalle.
"""

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "consultar_saldo",
            "description": "Devuelve el saldo actual disponible del usuario en su cuenta.",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "hacer_bizum",
            "description": (
                "Envía un Bizum (transferencia instantánea) a un contacto. Úsala solo cuando "
                "el usuario pida explícitamente enviar o mandar dinero a alguien."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "destinatario": {
                        "type": "string",
                        "description": "Nombre del contacto al que enviar el dinero",
                    },
                    "importe": {
                        "type": "number",
                        "description": "Cantidad en euros a enviar",
                    },
                    "concepto": {
                        "type": "string",
                        "description": "Motivo del envío (opcional)",
                    },
                },
                "required": ["destinatario", "importe"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "consultar_movimientos",
            "description": (
                "Ejecuta una consulta SQL SELECT contra la tabla `movimientos` para responder "
                "preguntas sobre el histórico financiero del usuario."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "sql": {
                        "type": "string",
                        "description": "Sentencia SQL SELECT válida en SQLite contra la tabla movimientos",
                    },
                },
                "required": ["sql"],
            },
        },
    },
]

TOOL_DISPATCH = {
    "consultar_saldo": lambda args: db_service.obtener_saldo(),
    "hacer_bizum": lambda args: db_service.hacer_bizum(
        destinatario=args.get("destinatario"),
        importe=args.get("importe"),
        concepto=args.get("concepto", "Bizum"),
    ),
    "consultar_movimientos": lambda args: db_service.ejecutar_consulta_sql(args.get("sql", "")),
}

# Historial de conversación en memoria. Vive mientras el proceso del backend
# esté corriendo — se pierde si reinicias el contenedor, y es compartido por
# el único usuario del MVP (no hay separación por sesión/usuario todavía).
_conversation_history: list[dict] = []

# Cuántos turnos (pares usuario+asistente, aprox.) conservar como máximo,
# para no dejar crecer el contexto sin límite y perjudicar la latencia.
MAX_HISTORY_MESSAGES = 16


def reset_conversation() -> None:
    """Vacía el hilo de conversación — llámalo para empezar de cero."""
    _conversation_history.clear()


def _trim_history() -> None:
    # Nos quedamos con los últimos N mensajes, sin contar el system prompt
    # (que se gestiona aparte, no vive dentro de _conversation_history).
    if len(_conversation_history) > MAX_HISTORY_MESSAGES:
        del _conversation_history[: len(_conversation_history) - MAX_HISTORY_MESSAGES]


def _parse_tool_args(raw_args) -> dict:
    if isinstance(raw_args, dict):
        return raw_args
    if isinstance(raw_args, str):
        try:
            return json.loads(raw_args)
        except json.JSONDecodeError:
            return {}
    return {}


async def procesar_mensaje(texto_usuario: str) -> str:
    """Orquesta la conversación con Ollama, incluyendo tool calling.

    Mantiene hilo con las llamadas anteriores (ver _conversation_history),
    así que "Confirmo" o "¿y la semana pasada?" tienen contexto real.
    Devuelve directamente el texto en lenguaje natural listo para TTS.
    """
    _conversation_history.append({"role": "user", "content": texto_usuario})
    messages = [{"role": "system", "content": SYSTEM_PROMPT}] + _conversation_history

    async with httpx.AsyncClient(timeout=60.0) as client:
        # --- 1ª llamada: el LLM decide si necesita una herramienta ---
        response = await client.post(
            f"{OLLAMA_BASE_URL}/api/chat",
            json={
                "model": OLLAMA_MODEL,
                "messages": messages,
                "tools": TOOLS,
                "stream": False,
            },
        )
        response.raise_for_status()
        assistant_message = response.json().get("message", {})
        tool_calls = assistant_message.get("tool_calls")

        if not tool_calls:
            final_content = assistant_message.get("content", "").strip() or "No he podido generar una respuesta."
            _conversation_history.append({"role": "assistant", "content": final_content})
            _trim_history()
            return final_content

        _conversation_history.append(assistant_message)
        messages.append(assistant_message)

        # --- Ejecutamos cada tool call localmente (el LLM nunca toca la DB directamente) ---
        for call in tool_calls:
            func = call.get("function", {})
            name = func.get("name")
            args = _parse_tool_args(func.get("arguments", {}))

            print(f"🔧 Tool call: {name}({args})")

            handler = TOOL_DISPATCH.get(name)
            resultado = handler(args) if handler else {"error": f"Herramienta desconocida: {name}"}

            tool_message = {"role": "tool", "content": json.dumps(resultado, ensure_ascii=False)}
            _conversation_history.append(tool_message)
            messages.append(tool_message)

        # --- 2ª llamada: el LLM redacta la respuesta final con los resultados reales ---
        response_final = await client.post(
            f"{OLLAMA_BASE_URL}/api/chat",
            json={
                "model": OLLAMA_MODEL,
                "messages": messages,
                "stream": False,
            },
        )
        response_final.raise_for_status()
        final_content = response_final.json().get("message", {}).get("content", "").strip()
        final_content = final_content or "No he podido generar una respuesta."

        _conversation_history.append({"role": "assistant", "content": final_content})
        _trim_history()
        return final_content