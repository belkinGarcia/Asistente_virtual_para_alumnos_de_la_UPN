# api.py - VERIFICADO Y CORREGIDO

import logging
import os
import json
import time

# --- IMPORTACIONES CORREGIDAS ---
from .utils import config_utils
from .services.schedule_service import process_chat # FIX: Usa el nombre de la función correcta
from .models.ml_model import inicializar_o_cargar_datos, entrenar_modelo

from flask import Flask, jsonify, request
from flask_cors import CORS
from dotenv import load_dotenv 

import google.generativeai as genai
# La línea de 'errors' se elimina
from google.api_core import exceptions as google_exceptions
import pandas as pd 

# --- Configuración de Logging y Entorno ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
load_dotenv() 

try:
    APP_ROOT = os.path.dirname(os.path.abspath(__file__))
    logging.info("Configuración de entorno lista.")
except Exception as e:
    logging.error(f"Error en la configuración inicial de Flask: {e}")
    
# --- Inicialización de Flask ---
app = Flask(__name__)
CORS(app, resources={r"/api/*": {"origins": "*"}}) 

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
        
        # --- INICIO DE LA CORRECCIÓN ---

        # 1. Validar que los campos numéricos (horas y calificación) sean números
        if not all(isinstance(val, (int, float)) for val in [horas_dedicadas, calificacion]):
             return jsonify({'error': 'Los campos "Horas Dedicadas" y "Calificación" deben ser números.'}), 400
        
        # 2. Validar que el texto de dificultad sea uno de los valores esperados
        if dificultad_texto not in ['fácil', 'media', 'difícil']:
            return jsonify({'error': 'El valor de "Dificultad" no es válido.'}), 400

        # 3. Validar los rangos de los números
        if not (1 <= calificacion <= 10 and horas_dedicadas > 0):
            return jsonify({'error': 'Valores fuera de rango (Calificación 1-10; Horas > 0)'}), 400

        # 4. Convertir la dificultad de texto a un número (escala 1-10) para el modelo ML
        #    Asumimos que 'fácil' es 3, 'media' es 6, 'difícil' es 9 (o ajusta esta escala)
        if dificultad_texto == 'fácil':
            dificultad_numerica = 3
        elif dificultad_texto == 'media':
            dificultad_numerica = 6
        else: # 'difícil'
            dificultad_numerica = 9

        # --- FIN DE LA CORRECCIÓN ---

        df = inicializar_o_cargar_datos()
        
        nuevo_registro = pd.DataFrame([{\
            'Materia': materia,\
            'Dificultad_Escala': dificultad_numerica, # <-- Usamos el número convertido
            'Horas_Estudio_Total': horas_dedicadas,\
            'Calificacion': calificacion\
        }])
        
        df = pd.concat([df, nuevo_registro], ignore_index=True)
        # Asegúrate de que la ruta al CSV es la correcta
        ruta_csv = os.path.join(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')), 'historial.csv')
        # Si 'data' no existe, usa la ruta anterior:
        # ruta_csv = os.path.join(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')), 'historial.csv') 
        
        df.to_csv(ruta_csv, index=False) 
        
        entrenar_modelo()
        
        return jsonify({'mensaje': 'Historial guardado exitosamente. ¡Gracias! Nuestro modelo ahora es más inteligente y ajustará tus futuras recomendaciones de estudio.'})

    except Exception as e:
        logging.error(f"Error al procesar el registro: {e}")
        return jsonify({'error': f'Error de procesamiento interno en Flask: {e}'}), 500

# --- INICIO DEL SERVIDOR ---

if __name__ == '__main__':
    app.run(debug=True, port=5000)