import os
import re
import json
import time
import httpx
from datetime import datetime
from typing import AsyncGenerator

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
Ten en cuenta que gimnasios o plataformas de streaming se clasifican como 'Suscripciones'

Fechas — MUY IMPORTANTE:
- NUNCA calcules tú mismo fechas relativas ("este mes", "esta semana", "hace 3 días"). Usa \
SIEMPRE las funciones nativas de fecha de SQLite en el SQL, que calculan la fecha real en el \
momento de ejecutar la consulta:
  - "este mes": strftime('%Y-%m', fecha) = strftime('%Y-%m', 'now')
  - "esta semana": fecha >= date('now', '-7 days')
  - "hoy": date(fecha) = date('now')
  - "el mes pasado": strftime('%Y-%m', fecha) = strftime('%Y-%m', 'now', '-1 month')
- No escribas un año o fecha concreta a mano salvo que el usuario la mencione explícitamente.

Reglas:
- Si la pregunta no necesita ninguna herramienta (saludo, charla general relacionada contigo \
como asistente), responde directamente, pero siempre indica que eres un agente financiero.
- Si la pregunta NO tiene nada que ver con finanzas, banca o tus herramientas (por ejemplo, \
temas de cultura general, el tiempo, chistes, recetas...), indícalo con amabilidad en una \
frase corta y redirige hacia lo que sí puedes hacer. No intentes responderla igualmente.
- Dile al usuario que cosas puede hacer contigo y que herramientas tienes disponibles, si no lo sabe.
- Para cualquier pregunta sobre el histórico, usa SIEMPRE consultar_movimientos con SQL válido, \
filtrando siempre por usuario_id = 1.
- Nunca inventes cifras. Si una herramienta devuelve un error, explícaselo al usuario con \
naturalidad, no expongas el error técnico tal cual.
- Cuando cites una cantidad de dinero que venga de una herramienta, cópiala EXACTAMENTE tal \
como aparece en el resultado (mismos dígitos, mismo punto/coma decimal). No la redondees, no \
la reescribas de memoria, no hagas cálculos mentales con ella — transcríbela literalmente, \
dígito por dígito.
- Si el usuario pide "más detalles" sobre un gasto, categoría o periodo, NO te limites a repetir \
el total que ya diste. Usa consultar_movimientos para desglosar por `concepto` dentro de esa \
categoría/periodo (ej: SELECT concepto, COUNT(*) AS veces, SUM(cantidad) AS total FROM \
movimientos WHERE categoria='Suscripciones' AND usuario_id=1 GROUP BY concepto) y cuéntale al \
usuario ese desglose concreto — por ejemplo, en qué suscripciones concretas se le va el dinero, \
o en qué tiendas ha gastado más en ropa.
- Sé proactivo: cuando tenga sentido, termina tu respuesta con UNA sugerencia concreta y \
relevante basada en los datos que ya conoces (por ejemplo, si acabas de dar el total de \
gasolina, puedes ofrecer contarle en qué gasolineras ha gastado más). Evita preguntas genéricas \
tipo "¿necesitas algo más?" — sé específico sobre qué podrías contarle a continuación.
- NUNCA digas que una operación (como un Bizum) se ha completado si no acabas de recibir la \
confirmación de la herramienta correspondiente EN ESTE MISMO TURNO. Si el usuario confirma una \
acción pendiente (dice "confirmo", "sí", "hazlo", etc.), debes volver a invocar la herramienta \
ahora mismo — nunca asumas que ya se ejecutó por el hecho de que se mencionó antes.
- Cuando le digas al usuario que si quiere más información sobre algun gasto, no ofrezcas información de \
algo que no esté en la base de datos (por ejemplo, no digas "quieres más información sobre que comida compraste" si no \
hay un campo para eso). Solo ofrece información que realmente puedas obtener de la base de datos.
- Sé breve: 1-3 frases, salvo que el usuario pida detalle.
"""

_DIAS_SEMANA = ["lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo"]


def _build_system_prompt() -> str:
    """Añade la fecha/hora real actuales al system prompt en cada llamada,
    para que el modelo no tenga que adivinarla de su entrenamiento."""
    ahora = datetime.now()
    dia_semana = _DIAS_SEMANA[ahora.weekday()]
    contexto_fecha = (
        f"\n\nContexto: hoy es {dia_semana}, {ahora.strftime('%Y-%m-%d')} "
        f"(hora actual: {ahora.strftime('%H:%M')})."
    )
    return SYSTEM_PROMPT + contexto_fecha


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
#TODO ver como hacer que el contenedor no se reinicie solo , que sino se pierde

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


# Frontera de frase: punto/exclamación/interrogación seguido de espacio.
# Heurística simple — no distingue "15.99€" (sin espacio detrás) de un punto
# final real, así que decimales pegados no se cortan mal, pero abreviaturas
# tipo "Sr. Pérez" sí podrían partirse antes de tiempo. Suficiente para el
# alcance del reto.
_SENTENCE_END_RE = re.compile(r"(?<=[.!?])\s+")


async def _stream_ollama_chat(client: httpx.AsyncClient, messages: list[dict]) -> AsyncGenerator[str, None]:
    """Produce trozos de texto (tokens/fragmentos) según los va devolviendo
    Ollama, sin esperar a que la respuesta esté completa."""
    async with client.stream(
        "POST",
        f"{OLLAMA_BASE_URL}/api/chat",
        json={"model": OLLAMA_MODEL, "messages": messages, "stream": True},
    ) as response:
        response.raise_for_status()
        async for line in response.aiter_lines():
            if not line:
                continue
            data = json.loads(line)
            chunk = data.get("message", {}).get("content", "")
            if chunk:
                yield chunk
            if data.get("done"):
                break


async def procesar_mensaje(texto_usuario: str) -> str:
    """Orquesta la conversación con Ollama, incluyendo tool calling.

    Mantiene hilo con las llamadas anteriores (ver _conversation_history),
    así que "Confirmo" o "¿y la semana pasada?" tienen contexto real.
    Devuelve directamente el texto en lenguaje natural listo para TTS.
    """
    _conversation_history.append({"role": "user", "content": texto_usuario})
    messages = [{"role": "system", "content": _build_system_prompt()}] + _conversation_history

    async with httpx.AsyncClient(timeout=60.0) as client:
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


async def procesar_mensaje_streaming(texto_usuario: str) -> AsyncGenerator[str, None]:
    """Igual que procesar_mensaje, pero produce frases completas en cuanto
    están listas — pensado para sintetizar cada una a audio sin esperar a
    que el modelo termine toda la respuesta.

    El primer paso (decidir si hace falta una herramienta) NO se streamea:
    necesitamos el JSON completo del tool_call para poder parsearlo. El
    streaming se aplica a la redacción de la respuesta final, que es la
    parte más larga y la que de verdad importa para la latencia percibida.

    Lleva prints de temporización (⏱️) para poder diagnosticar en los logs
    dónde se va el tiempo exactamente. Quítalos cuando ya no los necesites.
    """
    t0 = time.monotonic()
    _conversation_history.append({"role": "user", "content": texto_usuario})
    messages = [{"role": "system", "content": _build_system_prompt()}] + _conversation_history

    async with httpx.AsyncClient(timeout=60.0) as client:
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
        print(f"⏱️ 1ª llamada (decidir herramienta): {time.monotonic() - t0:.2f}s")

        if not tool_calls:
            final_content = assistant_message.get("content", "").strip() or "No he podido generar una respuesta."
            _conversation_history.append({"role": "assistant", "content": final_content})
            _trim_history()
            yield final_content
            return

        _conversation_history.append(assistant_message)
        messages.append(assistant_message)

        t_tools = time.monotonic()
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
        print(f"⏱️ Ejecución de herramienta(s): {time.monotonic() - t_tools:.2f}s")

        buffer = ""
        full_text = ""
        primera_frase_en = None
        t_stream = time.monotonic()
        async for chunk in _stream_ollama_chat(client, messages):
            buffer += chunk
            full_text += chunk
            while True:
                match = _SENTENCE_END_RE.search(buffer)
                if not match:
                    break
                sentence = buffer[: match.start()]
                buffer = buffer[match.end():]
                if sentence.strip():
                    if primera_frase_en is None:
                        primera_frase_en = time.monotonic() - t_stream
                        print(f"⏱️ Primera frase generada tras: {primera_frase_en:.2f}s (desde el inicio de la 2ª llamada)")
                    yield sentence.strip()

        if buffer.strip():
            yield buffer.strip()

        print(f"⏱️ Generación completa de la respuesta: {time.monotonic() - t_stream:.2f}s")
        print(f"⏱️ TOTAL desde que llega el mensaje: {time.monotonic() - t0:.2f}s")

        final_content = full_text.strip() or "No he podido generar una respuesta."
        _conversation_history.append({"role": "assistant", "content": final_content})
        _trim_history()