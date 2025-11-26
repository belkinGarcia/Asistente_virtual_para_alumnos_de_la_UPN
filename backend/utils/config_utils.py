# config_utils.py - Módulo de utilidades de configuración

import os
import logging
from dotenv import load_dotenv

load_dotenv()

def cargar_api_key():
    """
    Carga la clave de la API de Gemini desde el archivo .env.
    """
    # Se recomienda que el usuario cree un archivo .env en la raíz con:
    # GEMINI_API_KEY="AIzaSy..."
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        logging.error("La variable de entorno GEMINI_API_KEY no está configurada. Usa una clave estática para pruebas.")
        # Retorna una clave estática de prueba o lanza un error si es necesario
        return "CLAVE_NO_CONFIGURADA_FALLARA_LLAMADA_A_GEMINI"
    return api_key

# Esta función es un placeholder para la persistencia del horario, 
# si se necesitara una lógica más compleja de la que tiene schedule_service.py
def guardar_prioridad(data):
    # Lógica de guardado de datos o de persistencia
    pass