# schedule_service.py - CORREGIDO (FIX DE 'list' object has no attribute 'get')

import os
import json
import google.generativeai as genai
from google.generativeai import types
from flask import jsonify

# Importaciones relativas al paquete padre (backend)
from ..models import ml_model 
from ..utils import config_utils

# --- CONFIGURACIÓN E INICIALIZACIÓN ---
# --- CONFIGURACIÓN E INICIALIZACIÓN ---
try:
    API_KEY = config_utils.cargar_api_key() 
    genai.configure(api_key=API_KEY)
    # Crea una instancia del modelo que usarás
    model_client = genai.GenerativeModel('gemini-2.5-flash')
    print("Cliente Gemini inicializado correctamente.")
except Exception as e:
    print(f"Error al inicializar el cliente Gemini: {e}")
    model_client = None

# Archivos de persistencia
LAST_PRIORITIES_FILE = 'last_priorities.json'

# --- INTERFACES DE DATOS (TOOLING) ---
PLAN_SEMANAL_TOOL_DICT = {
    "name": "PlanSemanal",
    "description": "Genera un plan de estudio semanal detallado.",
    "parameters": {
        "type": "object",
        "properties": {
            "planSemanal": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "dia": {"type": "string"},
                        "actividad": {"type": "string"},
                        "horas": {"type": "number"},
                        "prioridad": {"type": "string"}
                    }
                }
            }
        },
        "required": ["planSemanal"]
    }
}

# ... (Funciones load/save_last_priorities omitidas por brevedad) ...
def load_last_priorities():
    if os.path.exists(LAST_PRIORITIES_FILE):
        with open(LAST_PRIORITIES_FILE, 'r') as f:
            return json.load(f)
    return None

def save_last_priorities(data):
    with open(LAST_PRIORITIES_FILE, 'w') as f:
        json.dump(data, f, indent=4)

# --- FUNCIONES CORE ---

def format_history_for_gemini(history: list) -> list:
    """
    Convierte la lista de mensajes de Angular al formato requerido por Gemini, 
    filtrando elementos no diccionario.
    """
    formatted_contents = []
    for message in history:
        # FIX CRÍTICO: Filtra elementos que no son diccionarios
        if not isinstance(message, dict):
            continue
            
        role = message.get('role', 'user')
        gemini_role = 'model' if role == 'assistant' else role
        text_content = message.get('text', '')
        
        if text_content: 
            formatted_contents.append({
                "role": gemini_role,
                "parts": [{"text": text_content}] 
            })
    return formatted_contents


def generate_schedule(prompt: str, study_hours_recommendation: float):
    """Genera un horario semanal usando la función PlanSemanal."""
    if not model_client:
        return {"error": "El cliente Gemini no está inicializado."}, 500

    try:
        function_declaration = types.FunctionDeclaration.from_dict(PLAN_SEMANAL_TOOL_DICT)
        tool_config = types.Tool(function_declarations=[function_declaration])
        
        config = types.GenerateContentConfig(
            tools=[tool_config] 
        )
    except Exception as e:
        return {"error": f"Error al configurar la herramienta Gemini: {e}"}, 500

    system_instruction = (
        f"Eres un planificador de horarios experto. Utiliza la función PlanSemanal "
        f"para generar una respuesta. La recomendación clave de ML es: planifica un total de {study_hours_recommendation:.1f} "
        f"horas de estudio académico a la semana..."
    )
    
    response = model_client.generate_content(
        contents=[{"role": "user", "parts": [{"text": prompt}]}],
        generation_config=config, # Renombrado a generation_config
        system_instruction=system_instruction
    )

    if response.function_calls:
        function_call = response.function_calls[0]
        schedule_data = function_call.args
        config_utils.guardar_prioridad(schedule_data) # Usa la función correctamente
        
        return {
            "role": "assistant",
            "text": f"He generado un plan para ti. Deberías enfocarte en aproximadamente {study_hours_recommendation:.1f} horas de estudio a la semana.",
            "horario": schedule_data
        }

    return {
        "role": "assistant",
        "text": "Lo siento, no pude generar un horario. ¿Podrías ser más específico con tu solicitud?",
    }


def process_chat(chat_history: list) -> dict:
    """Función de entrada principal. Maneja la conversación y detecta si se debe generar un horario."""
    if not model_client:
        return {"role": "assistant", "text": "Error: El servicio de IA no está disponible."}

    # 1. Buscar el último mensaje del asistente EN EL HISTORIAL CRUDO
    # 1. ...
    last_assistant_message = next((
    m for m in reversed(chat_history) 
    if isinstance(m, dict) and m.get('role') == 'assistant'
    ), None)

    # 2. Comprobar si el bot ACABA de enviar un horario
    # Si el último mensaje del bot tiene la clave 'horario', significa que acabamos de enviarlo.
    # No debemos generar otro, sino continuar la conversación normal.
    just_sent_schedule = False
    if last_assistant_message and 'horario' in last_assistant_message:
        just_sent_schedule = True

    # 3. Formatear el historial para Gemini (esto no cambia)
    formatted_contents = format_history_for_gemini(chat_history)

    # 4. Obtener el último prompt del usuario (esto no cambia)
    latest_user_message = next((m for m in reversed(formatted_contents) if m.get('role') == 'user'), None)

    if not latest_user_message:
         prompt = "Genera un mensaje de bienvenida."
    else:
         prompt = latest_user_message['parts'][0]['text']


    # 5. Detectar intención (¡LÓGICA ACTUALIZADA!)
    # Si el usuario pide un plan Y el bot NO acaba de enviar uno:
    if not just_sent_schedule and any(word in prompt.lower() for word in ["planificar", "horario", "plan", "programar"]):
        study_hours_recommendation = ml_model.predict_study_hours(5, 20, 8) 
        return generate_schedule(prompt, study_hours_recommendation)

    # 6. Continuar el chat normal (en todos los demás casos)
    # Esto ahora manejará el "ok muestrame" correctamente, pasando
    # la conversación a Gemini para una respuesta natural.
    response = model_client.generate_content(
        contents=formatted_contents 
    )

    return {
        "role": "assistant",
        "text": response.text
    }