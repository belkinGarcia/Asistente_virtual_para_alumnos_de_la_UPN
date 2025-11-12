# config_utils.py - VERIFICADO Y CORREGIDO

import os
import json
from dotenv import load_dotenv

# Carga variables de entorno (asegura que .env se lea)
load_dotenv()

# Archivos de persistencia de prioridad (para contexto del chat)
LAST_PRIORITIES_FILE = 'last_priorities.json'


def cargar_api_key() -> str:
    """
    Carga la clave API de Gemini del entorno.
    """
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise ValueError("La clave GEMINI_API_KEY no está configurada en el archivo .env.")
    return api_key


def cargar_ultima_prioridad():
    """Carga el último plan guardado (función original)."""
    if os.path.exists(LAST_PRIORITIES_FILE):
        try:
            with open(LAST_PRIORITIES_FILE, 'r') as f:
                return json.load(f)
        except json.JSONDecodeError:
            print("Error: El archivo last_priorities.json está corrupto.")
            return None
    return None

def guardar_prioridad(data):
    """Guarda el plan generado para contexto futuro (función original)."""
    with open(LAST_PRIORITIES_FILE, 'w') as f:
        json.dump(data, f, indent=4)