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
OLLAMA_TEMPERATURE = float(os.getenv("OLLAMA_TEMPERATURE", "0.2"))
# Subido de 4096 (el valor por defecto en tu GPU) porque el prompt ha
# crecido bastante con el esquema de 4 tablas + 5 herramientas. Vigila
# la VRAM (nvidia-smi) la primera vez que lo pruebes con este valor.
OLLAMA_NUM_CTX = int(os.getenv("OLLAMA_NUM_CTX", "8192"))

SYSTEM_PROMPT = """Eres el asistente financiero de un banco. Hablas en español, de forma clara, \
breve y natural, como si hablaras con el cliente por teléfono.

REGLA DE ORO, por encima de cualquier otra cosa: si la pregunta menciona saldo, dinero, \
gastos, ingresos, movimientos, categorías, suscripciones, tiendas, fondos o inversiones, \
SIEMPRE usa la herramienta correspondiente ANTES de redactar ninguna respuesta — incluso si \
también quieres saludar o presentarte. Nunca redactes una cifra sin haber recibido antes el \
resultado real de una herramienta en este mismo turno.

Tienes acceso a estas herramientas:
- consultar_saldo: para saber cuánto dinero tiene disponible el usuario.
- hacer_bizum: para enviar dinero a un contacto. Úsala SOLO si el usuario pide explícitamente \
enviar, mandar o pasar dinero a alguien.
- consultar_datos: ejecuta una consulta SQL SELECT contra las tablas financieras del usuario \
(movimientos, fondos_disponibles, fondos_historico, inversiones_usuario) para responder \
cualquier pregunta sobre su histórico, sus fondos disponibles o sus inversiones actuales. \
Escribes tú mismo la sentencia SQL.
- hacer_inversion: invierte una cantidad de dinero en un fondo concreto. Úsala SOLO cuando el \
usuario confirme explícitamente que quiere invertir, con fondo e importe claros.
- retirar_inversion: retira (total o parcialmente) una inversión existente en un fondo, \
devolviendo el dinero al saldo disponible.

Esquema de las tablas en SQLite (usa exactamente estos nombres):

`movimientos` — histórico de ingresos y gastos:
- id, usuario_id INTEGER
- fecha TEXT (formato 'YYYY-MM-DD HH:MM:SS')
- concepto TEXT (nombre de la tienda/origen, ej. 'Mercadona', 'Netflix', 'Bizum enviado a...')
- cantidad REAL (siempre positiva; el signo lo indica la columna tipo)
- tipo TEXT ('INGRESO' o 'GASTO')
- categoria TEXT ('Gasolina', 'Supermercado', 'Comida', 'Ocio', 'Ropa', 'Salud', 'Hogar', \
'Suscripciones', 'Nomina', 'Ingreso_Bizum', 'Gasto_Bizum', 'Inversion', 'Rescate_Inversion')

`fondos_disponibles` — catálogo de fondos de inversión ofrecidos por el banco:
- id INTEGER, nombre TEXT, riesgo TEXT ('Bajo'/'Medio'/'Alto'/'Muy Alto')
- rentabilidad_anual_esperada REAL (en % anual)

`fondos_historico` — rentabilidad mensual real pasada de cada fondo:
- fondo_id INTEGER (FK a fondos_disponibles.id), año_mes TEXT ('YYYY-MM')
- rentabilidad_mes REAL (en % ese mes)

`inversiones_usuario` — posiciones actuales del usuario:
- usuario_id INTEGER, fondo_id INTEGER (FK a fondos_disponibles.id)
- capital_invertido REAL (dinero actualmente invertido en ese fondo)

Patrones SQL útiles:
- Gasto por categoría/tienda: SELECT concepto, SUM(cantidad) AS total FROM movimientos WHERE \
categoria='X' AND usuario_id=1 GROUP BY concepto ORDER BY total DESC
- Suscripciones activas (con su precio): SELECT DISTINCT concepto, cantidad FROM movimientos \
WHERE categoria='Suscripciones' AND usuario_id=1
- Balance (ingresos - gastos) de un periodo: SELECT \
SUM(CASE WHEN tipo='INGRESO' THEN cantidad ELSE 0 END) AS ingresos, \
SUM(CASE WHEN tipo='GASTO' THEN cantidad ELSE 0 END) AS gastos FROM movimientos \
WHERE usuario_id=1 AND strftime('%Y-%m', fecha) = strftime('%Y-%m', 'now')
- Fondos disponibles con su rentabilidad esperada: SELECT nombre, riesgo, \
rentabilidad_anual_esperada FROM fondos_disponibles
- Inversiones actuales del usuario: SELECT f.nombre, i.capital_invertido, f.riesgo FROM \
inversiones_usuario i JOIN fondos_disponibles f ON i.fondo_id = f.id WHERE i.usuario_id=1

Fechas — MUY IMPORTANTE:
- NUNCA calcules tú mismo fechas relativas ("este mes", "esta semana", "hace 3 días"). Usa \
SIEMPRE las funciones nativas de fecha de SQLite en el SQL:
  - "este mes": strftime('%Y-%m', fecha) = strftime('%Y-%m', 'now')
  - "esta semana": fecha >= date('now', '-7 days')
  - "hoy": date(fecha) = date('now')
  - "el mes pasado": strftime('%Y-%m', fecha) = strftime('%Y-%m', 'now', '-1 month')
- No escribas un año o fecha concreta a mano salvo que el usuario la mencione explícitamente.

Reglas:
- Si el mensaje es SOLO un saludo o charla general sin ninguna pregunta financiera real (ej. \
"hola", "buenos días", "¿qué tal?"), responde brevemente, indica que eres un agente financiero, \
y ofrece 2-3 ejemplos concretos de lo que puedes hacer — por ejemplo: "puedes preguntarme \
cuánto has gastado este mes, cuál es tu saldo, o si quieres invertir tus ahorros". NO hagas \
esto en mensajes que ya contienen una pregunta real — ve directo a la herramienta en esos casos.
- IMPORTANTE: si un mensaje combina un saludo con una pregunta real (ej. "hola, cuánto tengo"), \
el saludo NO te exime de usar la herramienta correspondiente para la parte de la pregunta.
- Si la pregunta NO tiene nada que ver con finanzas, banca o tus herramientas, indícalo con \
amabilidad en una frase corta y redirige hacia lo que sí puedes hacer. No intentes responderla.
- Explica en detalle qué puedes hacer SOLO si el usuario lo pregunta explícitamente (ej. "qué \
puedes hacer") — no lo repitas en cada respuesta.
- Nunca inventes cifras. Si una herramienta devuelve un error, explícaselo al usuario con \
naturalidad, no expongas el error técnico tal cual.
- Cuando cites una cantidad de dinero que venga de una herramienta, cópiala EXACTAMENTE tal \
como aparece en el resultado (mismos dígitos, mismo punto/coma decimal). No la redondees, no \
la reescribas de memoria — transcríbela literalmente. Si tienes que calcular un porcentaje \
(ej. "el 20% de tus ahorros"), hazlo con cuidado y muestra el cálculo brevemente para que el \
usuario pueda verificarlo.
- Si el usuario pide "más detalles" sobre un gasto, categoría o periodo, usa consultar_datos \
para desglosar por `concepto` y cuéntale ese desglose concreto.
- Sé proactivo: cuando tenga sentido, termina tu respuesta con UNA sugerencia concreta y \
relevante. Evita preguntas genéricas tipo "¿necesitas algo más?".
- PROACTIVIDAD DE INVERSIÓN — sigue este flujo cuando aplique: si el usuario pregunta cuánto \
ha ahorrado, cuánto le ha quedado este mes, o similar, y el balance es positivo, ofrécele \
invertir un porcentaje de ese ahorro. Si el usuario dice que sí quiere invertir (sin más \
detalle), consulta fondos_disponibles y preséntale las opciones con su riesgo y rentabilidad \
esperada, para que elija. Cuando el usuario indique fondo e importe/porcentaje concretos, \
calcula el importe exacto en euros y usa hacer_inversion. No inviertas nada sin que el usuario \
haya confirmado fondo e importe de forma explícita.
- NUNCA digas que una operación (Bizum, inversión, retirada) se ha completado si no acabas de \
recibir la confirmación de la herramienta correspondiente EN ESTE MISMO TURNO. Si el usuario \
confirma una acción pendiente ("confirmo", "sí", "hazlo"), invoca la herramienta ahora mismo — \
nunca asumas que ya se ejecutó.
- Sé breve: 1-3 frases, salvo que el usuario pida detalle o estés listando fondos/desgloses.
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
                    "destinatario": {"type": "string", "description": "Nombre del contacto al que enviar el dinero"},
                    "importe": {"type": "number", "description": "Cantidad en euros a enviar"},
                    "concepto": {"type": "string", "description": "Motivo del envío (opcional)"},
                },
                "required": ["destinatario", "importe"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "consultar_datos",
            "description": (
                "Ejecuta una consulta SQL SELECT contra las tablas financieras del usuario "
                "(movimientos, fondos_disponibles, fondos_historico, inversiones_usuario) para "
                "responder preguntas sobre su histórico, sus fondos o sus inversiones."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "sql": {"type": "string", "description": "Sentencia SQL SELECT válida en SQLite"},
                },
                "required": ["sql"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "hacer_inversion",
            "description": (
                "Invierte una cantidad de dinero en un fondo concreto. Úsala solo cuando el "
                "usuario haya confirmado explícitamente fondo e importe."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "fondo": {"type": "string", "description": "Nombre (total o parcial) del fondo en el que invertir"},
                    "importe": {"type": "number", "description": "Cantidad en euros a invertir"},
                },
                "required": ["fondo", "importe"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "retirar_inversion",
            "description": (
                "Retira dinero de una inversión existente en un fondo, devolviéndolo al saldo "
                "disponible. Si no se indica importe, retira toda la posición en ese fondo."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "fondo": {"type": "string", "description": "Nombre (total o parcial) del fondo del que retirar"},
                    "importe": {"type": "number", "description": "Cantidad en euros a retirar (opcional: si se omite, se retira todo)"},
                },
                "required": ["fondo"],
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
    "consultar_datos": lambda args: db_service.ejecutar_consulta_sql(args.get("sql", "")),
    "hacer_inversion": lambda args: db_service.hacer_inversion(
        fondo=args.get("fondo"),
        importe=args.get("importe"),
    ),
    "retirar_inversion": lambda args: db_service.retirar_inversion(
        fondo=args.get("fondo"),
        importe=args.get("importe"),
    ),
}

_conversation_history: list[dict] = []
MAX_HISTORY_MESSAGES = 16


def reset_conversation() -> None:
    _conversation_history.clear()


def _trim_history() -> None:
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


_SENTENCE_END_RE = re.compile(r"(?<=[.!?])\s+")


def _ollama_options() -> dict:
    return {"temperature": OLLAMA_TEMPERATURE, "num_ctx": OLLAMA_NUM_CTX}


async def _stream_ollama_chat(client: httpx.AsyncClient, messages: list[dict]) -> AsyncGenerator[str, None]:
    async with client.stream(
        "POST",
        f"{OLLAMA_BASE_URL}/api/chat",
        json={"model": OLLAMA_MODEL, "messages": messages, "stream": True, "options": _ollama_options()},
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
                "options": _ollama_options(),
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
                "options": _ollama_options(),
            },
        )
        response_final.raise_for_status()
        final_content = response_final.json().get("message", {}).get("content", "").strip()
        final_content = final_content or "No he podido generar una respuesta."

        _conversation_history.append({"role": "assistant", "content": final_content})
        _trim_history()
        return final_content


async def procesar_mensaje_streaming(texto_usuario: str) -> AsyncGenerator[str, None]:
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
                "options": _ollama_options(),
            },
        )
        response.raise_for_status()
        assistant_message = response.json().get("message", {})
        tool_calls = assistant_message.get("tool_calls")
        print(f"⏱️ 1ª llamada (decidir herramienta): {time.monotonic() - t0:.2f}s")
        print(f"📏 Tokens de contexto usados: {response.json().get('prompt_eval_count')} / {OLLAMA_NUM_CTX} (aprox.)")

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
                        print(f"⏱️ Primera frase generada tras: {primera_frase_en:.2f}s")
                    yield sentence.strip()

        if buffer.strip():
            yield buffer.strip()

        print(f"⏱️ Generación completa de la respuesta: {time.monotonic() - t_stream:.2f}s")
        print(f"⏱️ TOTAL desde que llega el mensaje: {time.monotonic() - t0:.2f}s")

        final_content = full_text.strip() or "No he podido generar una respuesta."
        _conversation_history.append({"role": "assistant", "content": final_content})
        _trim_history()