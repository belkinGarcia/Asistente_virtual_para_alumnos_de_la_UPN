# backend/services/schedule_service.py

import os
import json
import google.genai as genai
from google.genai import types
from flask import jsonify 
from google.api_core import exceptions as google_exceptions # Importado para manejo de errores de API

# Importaciones relativas al paquete padre (backend)
try:
    from backend.models import ml_model 
    from backend.utils import config_utils
except ImportError as e:
    # Esto ocurre si falta un __init__.py o si se ejecuta mal
    print(f"Error al importar módulos internos: {e}. Asegúrate de ejecutar desde main.py")
    
# --- CONFIGURACIÓN E INICIALIZACIÓN ---
# NOTA: La inicialización de la API KEY con genai.Client()
# se hace en main.py. Aquí simplemente la obtenemos para usarla si es necesario
# o confiamos en que genai.Client() sin argumentos funcione.
# Eliminamos la inicialización con error: genai.GenerativeModel(...)

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

# --- FUNCIONES DE PERSISTENCIA (Simplificadas) ---
def load_last_priorities():
    if os.path.exists(LAST_PRIORITIES_FILE):
        with open(LAST_PRIORITIES_FILE, 'r') as f:
            return json.load(f)
    return None

def save_last_priorities(data):
    with open(LAST_PRIORITIES_FILE, 'w') as f:
        json.dump(data, f, indent=4)
    # config_utils.guardar_prioridad(data) # Opcional si tienes esta función

# --- FUNCIONES CORE ---

def format_history_for_gemini(history: list) -> list:
    """
    Convierte la lista de mensajes de Angular al formato requerido por Gemini, 
    filtrando elementos no diccionario.
    """
    formatted_contents = []
    for message in history:
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
    try:
        # Inicializa el cliente dentro de la función (o úsalo globalmente si prefieres)
        client = genai.Client()
        
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
    
    try:
        # CORRECCIÓN CLAVE: Usar el método generate_content() del cliente
        response = client.models.generate_content(
            model='gemini-2.5-flash', # Especificar el modelo aquí
            contents=[{"role": "user", "parts": [{"text": prompt}]}],
            generation_config=config,
            system_instruction=system_instruction
        )
    except google_exceptions.GoogleAPICallError as e:
        return {"error": f"Error de API al generar contenido: {e}"}, 500

    if response.function_calls:
        function_call = response.function_calls[0]
        schedule_data = function_call.args
        save_last_priorities(schedule_data) 

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
    
    # Inicializa el cliente (Esto ya debería funcionar si main.py lo configuró)
    client = genai.Client()
    
    # Asegúrate de que ml_model esté disponible antes de usarlo
    if 'ml_model' not in globals() and 'ml_model' not in locals():
         # Asigna un valor por defecto si el módulo ML no se cargó correctamente (Fase de prueba)
         study_hours_recommendation_default = 10.0
    else:
         # 5, 20, 8 deberían ser datos reales del usuario
         study_hours_recommendation_default = ml_model.predict_study_hours(5, 20, 8) 


    # 1. Buscar el último mensaje del asistente
    last_assistant_message = next((
    m for m in reversed(chat_history) 
    if isinstance(m, dict) and m.get('role') == 'assistant'
    ), None)

    # 2. Comprobar si el bot ACABA de enviar un horario
    just_sent_schedule = False
    if last_assistant_message and 'horario' in last_assistant_message:
        just_sent_schedule = True

    # 3. Formatear el historial para Gemini
    formatted_contents = format_history_for_gemini(chat_history)

    # 4. Obtener el último prompt del usuario
    latest_user_message = next((m for m in reversed(formatted_contents) if m.get('role') == 'user'), None)

    if not latest_user_message:
          prompt = "Genera un mensaje de bienvenida."
    else:
          prompt = latest_user_message['parts'][0]['text']


    # 5. Detectar intención
    if not just_sent_schedule and any(word in prompt.lower() for word in ["planificar", "horario", "plan", "programar"]):
        # Usa la recomendación de ML
        return generate_schedule(prompt, study_hours_recommendation_default)

    # 6. Continuar el chat normal
    try:
        # CORRECCIÓN CLAVE: Usar el método generate_content() del cliente
        response = client.models.generate_content(
            model='gemini-2.5-flash', # Especificar el modelo aquí
            contents=formatted_contents 
        )
    except google_exceptions.GoogleAPICallError as e:
        return {"role": "assistant", "text": f"Error de API al continuar chat: {e}"}


    return {
        "role": "assistant",
        "text": response.text
    }
