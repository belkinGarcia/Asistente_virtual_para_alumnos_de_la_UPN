import json
import logging
import os
import time
# --- IMPORTACIONES CORREGIDAS A RELATIVAS (.modulo) ---
from .utils.config_utils import cargar_ultima_prioridad, guardar_prioridad
from .services.schedule_service import generar_recomendacion
from .models.ml_model import inicializar_o_cargar_datos, entrenar_modelo

from flask import Flask, jsonify, request
from flask_cors import CORS
from dotenv import load_dotenv 

from google import genai
from google.genai import types
from google.genai.errors import APIError 
import pandas as pd 
import joblib # Necesario si se usa la función de ML

# --- Configuración de Logging ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Carga variables de entorno
load_dotenv() 

try:
    GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
    if not GEMINI_API_KEY:
        # Nota: En un entorno Canvas, la clave se inyecta, pero la mantenemos aquí para la robustez.
        raise ValueError("La clave GEMINI_API_KEY no está configurada en .env.")
    
    # Intenta usar la clave si está disponible, si no, usa el cliente por defecto (que fallará sin clave, pero manejamos la excepción)
    gemini_client = genai.Client(api_key=GEMINI_API_KEY)
    logging.info("Cliente de Gemini inicializado con éxito.")
except Exception as e:
    logging.warning(f"Advertencia: No se pudo inicializar el cliente de Gemini. Error: {e}")
    gemini_client = None

# --- API de Flask ---
app = Flask(__name__)
CORS(app) 

# Rutas de archivos (Ajustadas para la ejecución directa dentro de backend)
APP_ROOT = os.path.dirname(os.path.abspath(__file__))
HISTORIAL_PATH = os.path.join(APP_ROOT, '..', 'historial.csv')
MODEL_PATH = os.path.join(APP_ROOT, '..', 'horario_model.pkl')
PRIORIDADES_PATH = os.path.join(APP_ROOT, '..', 'last_priorities.json') 


# Inicialización (Entrenamiento del modelo al inicio)
try:
    # Usamos la función importada para entrenar
    entrenar_modelo()
except Exception as e:
    logging.error(f"Error al entrenar el modelo al inicio: {e}")


@app.route('/api/conversar', methods=['POST'])
def conversar():
    """Ruta conversacional que usa Gemini (SDK) para analizar el prompt y generar un plan."""
    
    if not gemini_client:
        return jsonify({'error': 'Cliente Gemini no inicializado. Verifica tu .env'}), 500
        
    data = request.get_json()
    contents_history = data.get('contents', []) 
    ultima_prioridad = cargar_ultima_prioridad()
    prioridad_context = json.dumps(ultima_prioridad)

    # 2. INSTRUCCIÓN DEL SISTEMA CORREGIDA (Cálculo estricto y uniformidad)
    system_instruction_base = (
        "Actúa como un asistente personal universitario experto en gestión del tiempo. Analiza el historial. "
        "1. **CÁLCULO Y ASIGNACIÓN ESTRICTA (CLAVE):** Los valores de `horas_min` DEBEN reflejar la suma exacta de las horas solicitadas por el usuario de Lunes a Viernes (Horas Diarias * 5). Para las prioridades principales, si el usuario no especifica días, ASIGNA LOS BLOQUES DE TRABAJO, ESTUDIO Y EJERCICIO A LOS 5 DÍAS LABORALES (Lunes a Viernes) UNIFORMEMENTE. "
        "2. **EXTRACCIÓN ESTRICTA DE HORARIOS:** DEBES rellenar los campos de horario de inicio/fin para Estudio, Ejercicio, Trabajo y Sueño. "
        "3. **PERSISTENCIA:** MANTÉN todos los valores del plan anterior si el usuario no los cambia. "
        "4. **FILTRADO ESTRICTO:** Si se pide un día específico (ej. 'rutina del martes'), DEBES establecer **'filtro_dia': 'SINGLE_DAY'** y **'dia_seleccionado': 'Martes'**. Si no, usa **'filtro_dia': 'WEEK'** y **'dia_seleccionado': 'Lunes'**. "
        "5. **RESPUESTA JSON:** SIEMPRE devuelve un objeto JSON COMPLETO. "
    )
    
    final_system_instruction = system_instruction_base + f"\n\nCONTEXTO DEL PLAN ANTERIOR (DEBES USAR ESTOS VALORES POR DEFECTO): {prioridad_context}"

    # Definición del esquema de respuesta JSON esperado (Se omite por brevedad, pero debe estar presente)
    json_schema = types.Schema(
        type=types.Type.OBJECT,
        properties={
            "mensaje": types.Schema(type=types.Type.STRING, description="Respuesta conversacional del asistente, incluyendo si detectas un conflicto potencial."),
            "horas_estudio_min": types.Schema(type=types.Type.NUMBER),
            "horas_ejercicio_min": types.Schema(type=types.Type.NUMBER),
            "horas_trabajo_min": types.Schema(type=types.Type.NUMBER),
            "sueno_min": types.Schema(type=types.Type.NUMBER),
            "estudio_inicio": types.Schema(type=types.Type.STRING), "estudio_fin": types.Schema(type=types.Type.STRING),
            "ejercicio_inicio": types.Schema(type=types.Type.STRING), "ejercicio_fin": types.Schema(type=types.Type.STRING),
            "trabajo_inicio": types.Schema(type=types.Type.STRING), "trabajo_fin": types.Schema(type=types.Type.STRING),
            "sueno_inicio": types.Schema(type=types.Type.STRING), "sueno_fin": types.Schema(type=types.Type.STRING),
            "estudio_fin_miercoles": types.Schema(type=types.Type.STRING, description="Usar SOLO si hay conflicto o cambio en el Miércoles."),
            "trabajo_inicio_miercoles": types.Schema(type=types.Type.STRING, description="Usar SOLO si hay conflicto o cambio en el Miércoles."),
            "estudio_fin_jueves": types.Schema(type=types.Type.STRING, description="Usar SOLO si hay conflicto o cambio en el Jueves."),
            "trabajo_inicio_jueves": types.Schema(type=types.Type.STRING, description="Usar SOLO si hay conflicto o cambio en el Jueves."),
            "otras_actividades": types.Schema(
                type=types.Type.ARRAY, 
                description="Lista de actividades únicas. MANTÉN las actividades anteriores a menos que el usuario pida eliminarlas o modificarlas.",
                items=types.Schema(
                    type=types.Type.OBJECT,
                    properties={
                        "nombre": types.Schema(type=types.Type.STRING),
                        "inicio": types.Schema(type=types.Type.STRING),
                        "fin": types.Schema(type=types.Type.STRING),
                        "dias": types.Schema(type=types.Type.STRING, description="Días aplicables (ej: 'Lunes', 'Miércoles', 'Todos', 'Lunes-Viernes').")
                    }
                )
            ),
            "filtro_dia": types.Schema(type=types.Type.STRING, description="Debe ser 'SINGLE_DAY' o 'WEEK'."),
            "dia_seleccionado": types.Schema(type=types.Type.STRING, description="Nombre del día ('Lunes', 'Martes', etc.)."),
        },
        required=["mensaje", "horas_estudio_min", "horas_ejercicio_min", "horas_trabajo_min", "sueno_min", "filtro_dia", "dia_seleccionado"]
    )

    
    MAX_RETRIES = 3
    for attempt in range(MAX_RETRIES):
        try:
            config = types.GenerateContentConfig(
                system_instruction=final_system_instruction, 
                response_mime_type="application/json",
                response_schema=json_schema,
            )
            
            response = gemini_client.models.generate_content(
                model='gemini-2.5-flash',
                contents=contents_history,
                config=config,
            )

            gemini_response = json.loads(response.text)
            
            prioridades = {
                'horas_estudio_min': gemini_response.get('horas_estudio_min', ultima_prioridad['horas_estudio_min']),
                'horas_ejercicio_min': gemini_response.get('horas_ejercicio_min', ultima_prioridad['horas_ejercicio_min']),
                'horas_trabajo_min': gemini_response.get('horas_trabajo_min', ultima_prioridad['horas_trabajo_min']),
                'sueno_min': gemini_response.get('sueno_min', ultima_prioridad['sueno_min']),
                
                'estudio_inicio': gemini_response.get('estudio_inicio', ultima_prioridad.get('estudio_inicio')),
                'estudio_fin': gemini_response.get('estudio_fin', ultima_prioridad.get('estudio_fin')),
                'ejercicio_inicio': gemini_response.get('ejercicio_inicio', ultima_prioridad.get('ejercicio_inicio')),
                'ejercicio_fin': gemini_response.get('ejercicio_fin', ultima_prioridad.get('ejercicio_fin')),
                'trabajo_inicio': gemini_response.get('trabajo_inicio', ultima_prioridad.get('trabajo_inicio')),
                'trabajo_fin': gemini_response.get('trabajo_fin', ultima_prioridad.get('trabajo_fin')),
                'sueno_inicio': gemini_response.get('sueno_inicio', ultima_prioridad.get('sueno_inicio')),
                'sueno_fin': gemini_response.get('sueno_fin', ultima_prioridad.get('sueno_fin')),
                
                'estudio_fin_miercoles': gemini_response.get('estudio_fin_miercoles'),
                'trabajo_inicio_miercoles': gemini_response.get('trabajo_inicio_miercoles'),
                
                'estudio_fin_jueves': gemini_response.get('estudio_fin_jueves'), 
                'trabajo_inicio_jueves': gemini_response.get('trabajo_inicio_jueves'), 
                
                'otras_actividades': gemini_response.get('otras_actividades', ultima_prioridad.get('otras_actividades', [])), 
            }
            
            filtro_dia = gemini_response.get('filtro_dia', 'WEEK')
            dia_seleccionado = gemini_response.get('dia_seleccionado', 'Lunes')


            horario_generado, conflictos_detectados = generar_recomendacion(
                prioridades, 
                filtro_dia, 
                dia_seleccionado
            )
            
            respuesta_texto = gemini_response.get('mensaje', 'Plan generado con éxito.')
            if conflictos_detectados:
                respuesta_texto += " **¡ADVERTENCIA DE CONFLICTO!** Se detectaron solapamientos en el horario. Revisa los detalles."
                
            
            guardar_prioridad(prioridades) 

            horas_programadas_diurnas = round(
                float(prioridades['horas_estudio_min']) + 
                float(prioridades['horas_ejercicio_min']) + 
                float(prioridades['horas_trabajo_min']), 
                0
            )
            
            if 'Plan Sugerido' in respuesta_texto:
                respuesta_texto = respuesta_texto.replace(
                    f'Plan Sugerido (Total: {horas_programadas_diurnas} horas gestionadas)',
                    f'Plan Sugerido (Horas productivas mínimas: {horas_programadas_diurnas}h)'
                )

            # LÓGICA DE MUESTRA CONDICIONAL
            show_plan = False
            keywords_to_show = ["plan sugerido", "muéstrame", "horarios del", "ajustes", "actualizado"]
            
            last_user_prompt = contents_history[-1]['parts'][0]['text'].lower() if contents_history and contents_history[-1]['role'] == 'user' else ""

            if any(k in respuesta_texto.lower() for k in keywords_to_show) or any(k in last_user_prompt for k in keywords_to_show):
                 show_plan = True

            if any(phrase in respuesta_texto.lower() for phrase in ["gracias", "de nada", "no dudes en preguntar", "que tengas un gran día"]):
                show_plan = False 

            if show_plan:
                if filtro_dia == 'SINGLE_DAY':
                    respuesta_texto += f"\n\n**Plan Sugerido para el {dia_seleccionado}:**"
                else:
                    respuesta_texto += f"\n\n**Plan Semanal Sugerido (Horas productivas mínimas: {horas_programadas_diurnas}h):**"
            
            
            return jsonify({
                'respuesta_texto': respuesta_texto,
                'horas_estimadas': horas_programadas_diurnas,
                'horario': horario_generado,
                'conflictos': conflictos_detectados,
                'show_plan': show_plan
            })
            
        except APIError as e:
            error_msg = str(e)
            logging.error(f"ERROR API DE GEMINI DETECTADO: {error_msg}")
            if attempt < MAX_RETRIES - 1:
                time.sleep(2 ** attempt) 
            else:
                return jsonify({'error': f'Fallo de la API después de {MAX_RETRIES} intentos: {error_msg}'}), 500
                
        except json.JSONDecodeError as e:
            logging.error(f"ADVERTENCIA: Falló el parsing del JSON del modelo. Error: {e}. Respuesta: {response.text[:200]}...")
            return jsonify({'error': f'Error de formato: El modelo no devolvió un JSON válido. {e}'}), 500

        except Exception as e:
            logging.error(f"ERROR INTERNO EN FLASK: {e}")
            return jsonify({'error': f'Error de procesamiento interno en Flask: {e}'}), 500

    return jsonify({'error': 'Fallo al comunicarse con el asistente.'}), 500


@app.route('/api/registrar_historial', methods=['POST'])
def registrar_historial():
    """Ruta para registrar el desempeño y reentrenar el modelo ML."""
    try:
        data = request.get_json()
        
        # Validación estricta
        try:
            materia = data['materia']
            dificultad = int(data['dificultad'])
            horas_dedicadas = float(data['horas_dedicadas'])
            calificacion = int(data['calificacion'])
        except KeyError:
             return jsonify({'error': 'Faltan campos obligatorios (materia, dificultad, horas_dedicadas, calificacion).'}), 400
        except ValueError:
             return jsonify({'error': 'Error de formato: Los campos de número no son válidos.'}), 400
        
        if not (1 <= dificultad <= 10 and 1 <= calificacion <= 10 and horas_dedicadas > 0):
            return jsonify({'error': 'Valores fuera de rango (Dificultad y Calificación 1-10; Horas > 0)'}), 400

        df = inicializar_o_cargar_datos()
        
        nuevo_registro = pd.DataFrame([{
            'Materia': materia,
            'Dificultad_Escala': dificultad,
            'Horas_Estudio_Total': horas_dedicadas,
            'Calificacion': calificacion
        }])
        
        df = pd.concat([df, nuevo_registro], ignore_index=True)
        # Se usa una ruta relativa segura para acceder a historial.csv en el directorio padre
        df.to_csv(os.path.join(APP_ROOT, '..', 'historial.csv'), index=False) 
        
        entrenar_modelo()
        
        return jsonify({
            'mensaje': f'Historial guardado exitosamente. ¡Gracias! Nuestro modelo ahora es más inteligente y ajustará tus futuras recomendaciones de estudio con base en tu calificación de {calificacion}.'
        })

    except Exception as e:
        logging.error(f"Error al procesar el registro: {e}")
        return jsonify({'error': f'Error de procesamiento interno en Flask: {e}'}), 500


if __name__ == '__main__':
    logging.info("Iniciando la aplicación.")
    # Ejecutamos desde la carpeta backend, por eso usamos las rutas relativas en la importación.
    app.run(port=5000, debug=True, use_reloader=False)
