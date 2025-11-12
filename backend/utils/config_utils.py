import json
import os
import unicodedata
from datetime import datetime
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Rutas de archivos
APP_ROOT = os.path.dirname(os.path.abspath(__file__))
PRIORIDADES_PATH = os.path.join(APP_ROOT, '..', 'last_priorities.json') 

def cargar_ultima_prioridad():
    """Carga el último plan de prioridades o devuelve valores por defecto."""
    if os.path.exists(PRIORIDADES_PATH):
        try:
            with open(PRIORIDADES_PATH, 'r') as f:
                return json.load(f)
        except json.JSONDecodeError:
            logging.error("Error al leer el JSON de prioridades. Usando valores por defecto.")
    
    # Valores por defecto iniciales
    return {
        "horas_estudio_min": 15, "horas_ejercicio_min": 6, "horas_trabajo_min": 10, "sueno_min": 7, 
        "estudio_inicio": "08:00 am", "estudio_fin": "11:00 am",
        "ejercicio_inicio": "06:00 pm", "ejercicio_fin": "07:00 pm",
        "trabajo_inicio": "01:00 pm", "trabajo_fin": "03:00 pm",
        "sueno_inicio": "10:00 pm", "sueno_fin": "06:00 am",
        "otras_actividades": []
    }

def guardar_prioridad(prioridades):
    """Guarda el plan de prioridades en un archivo JSON."""
    try:
        with open(PRIORIDADES_PATH, 'w') as f:
            json.dump(prioridades, f, indent=4)
        logging.info("Prioridades guardadas exitosamente.")
    except Exception as e:
        logging.error(f"Error al guardar las prioridades: {e}")

def normalize_day(day_name):
    """Normaliza nombres de días (elimina tildes, minúsculas)."""
    return unicodedata.normalize('NFKD', day_name).encode('ascii', 'ignore').decode('utf-8').lower()