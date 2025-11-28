import logging
import os
import json
import pandas as pd 
from datetime import datetime

from flask import Flask, jsonify, request
from flask_cors import CORS
from dotenv import load_dotenv 

# --- LIBRERÍAS DE GOOGLE CALENDAR ---
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

from backend.services.schedule_service import (
    process_chat, save_user_profile, generate_initial_schedule, 
    load_user_profile, delete_user_profile, generate_exam_schedule,
    generate_crisis_schedule, load_chat_history, save_chat_history,
    load_projects, save_projects, generate_project_plan_ai
)
from backend.models.ml_model import (
    inicializar_o_cargar_datos, entrenar_modelo, DATA_FILE, 
    obtener_datos_dashboard, obtener_materias_unicas
)

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
load_dotenv() 

app = Flask(__name__)
CORS(app, resources={r"/api/*": {"origins": "*"}}) 

# --- CONFIGURACIÓN GOOGLE CALENDAR ---
SCOPES = ['https://www.googleapis.com/auth/calendar']
TOKEN_FILE = 'token.json'
CREDENTIALS_FILE = 'client_secret.json'

# --- ENDPOINTS EXISTENTES ---
@app.route('/api/chat_history', methods=['GET'])
def get_chat_history(): return jsonify(load_chat_history())

@app.route('/api/conversar', methods=['POST'])
def conversar():
    try:
        data = request.get_json()
        return jsonify(process_chat(data.get('history', [])))
    except Exception as e: return jsonify({"error": str(e)}), 500

@app.route('/api/check_perfil', methods=['GET'])
def check_perfil(): return jsonify({"existe": load_user_profile() is not None})

@app.route('/api/obtener_perfil', methods=['GET'])
def obtener_perfil():
    p = load_user_profile()
    return jsonify(p) if p else (jsonify({"error": "No perfil"}), 404)

@app.route('/api/crear_perfil', methods=['POST'])
def crear_perfil():
    try:
        data = request.get_json()
        save_user_profile(data)
        schedule = generate_initial_schedule(data)
        save_chat_history([schedule])
        return jsonify(schedule)
    except Exception as e: return jsonify({"error": str(e)}), 500

@app.route('/api/actualizar_perfil', methods=['POST'])
def actualizar_perfil():
    save_user_profile(request.get_json())
    return jsonify({"mensaje": "Ok"})

@app.route('/api/reset_perfil', methods=['POST'])
def reset_perfil():
    delete_user_profile()
    # También borramos el token de Google para desconectar
    if os.path.exists(TOKEN_FILE): os.remove(TOKEN_FILE)
    return jsonify({"mensaje": "Reset"})

@app.route('/api/planificar_examenes', methods=['POST'])
def planificar_examenes():
    data = request.get_json()
    return jsonify(generate_exam_schedule(load_user_profile(), data.get('examenes', [])))

@app.route('/api/planificar_crisis', methods=['POST'])
def planificar_crisis():
    data = request.get_json()
    return jsonify(generate_crisis_schedule(load_user_profile(), data.get('examenes', [])))

@app.route('/api/dashboard_stats', methods=['GET'])
def dashboard_stats():
    return jsonify(obtener_datos_dashboard())

@app.route('/api/materias', methods=['GET'])
def get_materias():
    return jsonify(obtener_materias_unicas())

@app.route('/api/registrar_historial', methods=['POST'])
def registrar_historial():
    try:
        data = request.get_json()
        materia = data.get('materia', '').strip().title()
        if not materia: return jsonify({'error': 'Falta materia'}), 400
        
        df = inicializar_o_cargar_datos()
        nuevo = pd.DataFrame([{
            'Materia': materia,
            'Horas_Estudio_Real': float(data.get('horas_reales', 0)),
            'Dificultad_Cat': data.get('dificultad', 'media'),
            'Dificultad_Num': 2,
            'Nivel_Energia': data.get('nivel_energia', 3),
            'Cumplio_Objetivo': data.get('cumplio_objetivo', 'sí'),
            'Factor_Bloqueo': data.get('factor_bloqueo', 'Ninguno'),
            'Calificacion': 0,
            'Horas_Sueno': data.get('horas_sueno', 7),
            'Lugar_Estudio': data.get('lugar_estudio', 'Casa'),
            'Actividad_Fisica': data.get('actividad_fisica', 'Ninguna'),
            'Dia_Semana': data.get('dia_semana', 'Lunes'),
            'Fecha': datetime.now().strftime("%Y-%m-%d"),
            'Tipo_Sesion': data.get('tipo_sesion', 'Manual')
        }])
        
        pd.concat([df, nuevo], ignore_index=True).to_csv(DATA_FILE, index=False)
        try: entrenar_modelo()
        except: pass
        return jsonify({'mensaje': 'Registrado'})
    except Exception as e: return jsonify({'error': str(e)}), 500

@app.route('/api/proyectos', methods=['GET'])
def get_proyectos(): return jsonify(load_projects())

@app.route('/api/crear_proyecto', methods=['POST'])
def crear_proyecto():
    try:
        data = request.get_json()
        profile = load_user_profile()
        hitos = generate_project_plan_ai(profile, data)
        nuevo_proyecto = {
            "id": datetime.now().strftime("%Y%m%d%H%M%S"),
            "nombre": data['nombre'], "descripcion": data['descripcion'],
            "fecha_fin": data['fecha_fin'], "progreso": 0, "hitos": hitos
        }
        for h in nuevo_proyecto['hitos']: h['completado'] = False
        projects = load_projects()
        projects.append(nuevo_proyecto)
        save_projects(projects)
        return jsonify(nuevo_proyecto)
    except Exception as e: return jsonify({"error": str(e)}), 500

@app.route('/api/actualizar_hitos', methods=['POST'])
def actualizar_hitos():
    try:
        data = request.get_json()
        projects = load_projects()
        for p in projects:
            if p['id'] == data['project_id']:
                p['hitos'] = data['hitos']
                total = len(p['hitos'])
                completados = sum(1 for h in p['hitos'] if h.get('completado'))
                p['progreso'] = int((completados / total) * 100) if total > 0 else 0
                break
        save_projects(projects)
        return jsonify({"mensaje": "Actualizado"})
    except Exception as e: return jsonify({"error": str(e)}), 500

@app.route('/api/eliminar_proyecto', methods=['POST'])
def eliminar_proyecto():
    try:
        pid = request.get_json().get('id')
        projects = [p for p in load_projects() if p['id'] != pid]
        save_projects(projects)
        return jsonify({"mensaje": "Eliminado"})
    except Exception as e: return jsonify({"error": str(e)}), 500

# --- NUEVOS ENDPOINTS: GOOGLE CALENDAR ---

@app.route('/api/google/connect', methods=['GET'])
def google_connect():
    """Inicia el flujo de autenticación local"""
    if not os.path.exists(CREDENTIALS_FILE):
        return jsonify({"error": "Falta client_secret.json"}), 400
    
    flow = InstalledAppFlow.from_client_secrets_file(CREDENTIALS_FILE, SCOPES)
    creds = flow.run_local_server(port=0)
    
    with open(TOKEN_FILE, 'w') as token:
        token.write(creds.to_json())
        
    return jsonify({"mensaje": "Conectado", "email": "usuario@gmail.com"}) # Simplificado

@app.route('/api/google/status', methods=['GET'])
def google_status():
    return jsonify({"conectado": os.path.exists(TOKEN_FILE)})

@app.route('/api/google/sync', methods=['POST'])
def google_sync():
    """Recibe el horario JSON y lo sube a la nube"""
    if not os.path.exists(TOKEN_FILE):
        return jsonify({"error": "No autenticado"}), 401
    
    creds = Credentials.from_authorized_user_file(TOKEN_FILE, SCOPES)
    service = build('calendar', 'v3', credentials=creds)
    
    data = request.get_json()
    horario = data.get('horario', {}).get('planSemanal', [])
    
    contador = 0
    for item in horario:
        try:
            # Construir fechas ISO (Asumiendo hora local)
            # Formato fecha: YYYY-MM-DD, Formato hora: HH:MM
            start_dt = f"{item['fecha']}T{item['hora_inicio']}:00"
            end_dt = f"{item['fecha']}T{item['hora_fin']}:00"
            
            # Definir color según tipo (ID de colores de Google Calendar: 1-11)
            color_id = '1' # Lavanda (Default)
            tipo = item.get('tipo', 'Estudio')
            if tipo == 'Examen' or tipo == 'Crisis': color_id = '11' # Rojo
            elif tipo == 'Trabajo': color_id = '8' # Gris
            elif tipo == 'Estudio': color_id = '9' # Azul oscuro
            elif tipo == 'Proyecto': color_id = '7' # Azul pavo
            
            event = {
                'summary': f"📚 {item['actividad']}",
                'description': f"Generado por Asistente UPN.\nTipo: {tipo}\nPrioridad: {item.get('prioridad','Normal')}",
                'start': {'dateTime': start_dt, 'timeZone': 'America/Lima'}, # Ajusta tu zona horaria
                'end': {'dateTime': end_dt, 'timeZone': 'America/Lima'},
                'colorId': color_id,
                'reminders': {
                    'useDefault': False,
                    'overrides': [
                        {'method': 'popup', 'minutes': 15},
                    ],
                },
            }
            
            service.events().insert(calendarId='primary', body=event).execute()
            contador += 1
        except Exception as e:
            print(f"Error subiendo evento: {e}")
            
    return jsonify({"mensaje": f"¡Éxito! {contador} eventos sincronizados con tu nube."})

if __name__ == '__main__':
    app.run(debug=True, port=5000)