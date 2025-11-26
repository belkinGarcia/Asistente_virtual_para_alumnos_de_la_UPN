import logging
import os
import json
import time
import pandas as pd 

from flask import Flask, jsonify, request
from flask_cors import CORS
from dotenv import load_dotenv 

# --- Importaciones absolutas corregidas para que funcionen desde la raíz ---
from backend.utils import config_utils
from backend.services.schedule_service import process_chat 
from backend.models.ml_model import inicializar_o_cargar_datos, entrenar_modelo

import google.genai as genai 
from google.api_core import exceptions as google_exceptions

# --- Configuración de Logging y Entorno ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
load_dotenv() 

try:
    API_KEY = os.getenv("GEMINI_API_KEY")
    if not API_KEY:
        raise ValueError("La variable de entorno GEMINI_API_KEY no está configurada.")
    
    # Esta es la forma correcta de inicializar el cliente en el nuevo SDK
    genai.Client(api_key=API_KEY) 
    
    logging.info("Cliente Gemini inicializado exitosamente.")
except (ValueError, google_exceptions.GoogleAPICallError) as e:
    logging.error(f"Error al inicializar el cliente Gemini: {e}")
    # Opcional: puedes decidir salir del programa si la API es crítica
    # exit(1) 
except Exception as e:
    logging.error(f"Error desconocido al configurar Gemini: {e}")

# --- Inicialización de Flask ---
app = Flask(__name__)
CORS(app, resources={r"/api/*": {"origins": "*"}}) 

# Define la ruta raíz para calcular rutas relativas al archivo historial.csv
PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
logging.info(f"Ruta raíz del proyecto: {PROJECT_ROOT}")


# --- ENDPOINTS DE LA API ---

@app.route('/api/conversar', methods=['POST'])
def conversar():
    """Endpoint principal para recibir el chat history y generar una respuesta o plan."""
    try:
        data = request.get_json()
        chat_history = data.get('history', [])

        if not chat_history:
            return jsonify({"error": "Missing 'history' in request body"}), 400

        # Llama a la función principal del servicio
        response_data = process_chat(chat_history) 

        return jsonify(response_data)
        
    except google_exceptions.GoogleAPICallError as ae:
        logging.error(f"Error de API de Gemini: {ae}")
        return jsonify({'error': f'Error de API de Gemini: {ae}'}), 500
    except Exception as e:
        app.logger.error(f"Error en el endpoint /api/conversar: {e}")
        return jsonify({"error": "ERROR INTERNO EN FLASK: " + str(e)}), 500

@app.route('/api/registrar_historial', methods=['POST'])
def registrar_historial():
    """Endpoint para recibir feedback del usuario (ML) y reentrenar el modelo."""
    try:
        data = request.get_json()
        
        materia = data.get('materia')
        dificultad_texto = data.get('dificultad') # "fácil", "media", "difícil"
        horas_dedicadas = data.get('horas_dedicadas')
        calificacion = data.get('calificacion')
        
        # 1. Validación y Conversión (La lógica de validación es perfecta)
        if not all(isinstance(val, (int, float)) for val in [horas_dedicadas, calificacion]):
             return jsonify({'error': 'Los campos "Horas Dedicadas" y "Calificación" deben ser números.'}), 400
        
        if dificultad_texto not in ['fácil', 'media', 'difícil']:
            return jsonify({'error': 'El valor de "Dificultad" no es válido.'}), 400

        if not (1 <= calificacion <= 10 and horas_dedicadas > 0):
            return jsonify({'error': 'Valores fuera de rango (Calificación 1-10; Horas > 0)'}), 400

        if dificultad_texto == 'fácil':
            dificultad_numerica = 3
        elif dificultad_texto == 'media':
            dificultad_numerica = 6
        else: # 'difícil'
            dificultad_numerica = 9

        # 2. Carga, Concatenación y Guardado de Datos
        df = inicializar_o_cargar_datos()
        
        nuevo_registro = pd.DataFrame([{
            'Materia': materia,
            'Dificultad_Escala': dificultad_numerica, 
            'Horas_Estudio_Total': horas_dedicadas,
            'Calificacion': calificacion
        }])
        
        df = pd.concat([df, nuevo_registro], ignore_index=True)
        
        # Corrección de la ruta: Ahora que estamos en la raíz, la ruta es más simple
        ruta_csv = os.path.join(PROJECT_ROOT, 'historial.csv') 
        
        df.to_csv(ruta_csv, index=False) 
        
        # 3. Reentrenamiento del Modelo (MLOps)
        entrenar_modelo()
        
        return jsonify({'mensaje': 'Historial guardado exitosamente. ¡Gracias! Nuestro modelo ahora es más inteligente y ajustará tus futuras recomendaciones de estudio.'})

    except Exception as e:
        logging.error(f"Error al procesar el registro: {e}")
        return jsonify({'error': f'Error de procesamiento interno en Flask: {e}'}), 500

# --- INICIO DEL SERVIDOR ---

if __name__ == '__main__':
    # Asegúrate de haber ejecutado: pip install pandas flask flask-cors python-dotenv google-genai
    app.run(debug=True, port=5000)