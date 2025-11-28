import os
import json
import logging
import locale
from datetime import datetime
import google.genai as genai
from google.genai import types
from backend.models.ml_model import generar_reporte_analitico, DATA_FILE, MODEL_FILE

try: locale.setlocale(locale.LC_TIME, 'es_ES.UTF-8')
except: pass

PROFILE_FILE = 'user_profile.json'
CHAT_FILE = 'chat_history.json'
PROJECTS_FILE = 'user_projects.json'

# --- TOOLS ---
PLAN_SEMANAL_TOOL = types.FunctionDeclaration(
    name="PlanSemanal", description="Genera horario semanal.",
    parameters={"type": "object", "properties": {"planSemanal": {"type": "array", "items": {"type": "object", "properties": {"dia": {"type": "string"}, "fecha": {"type": "string"}, "hora_inicio": {"type": "string"}, "hora_fin": {"type": "string"}, "actividad": {"type": "string"}, "tipo": {"type": "string", "enum": ["Estudio", "Trabajo", "Sueño", "Ocio", "Deporte", "Doméstico", "Examen", "Crisis", "Proyecto"]}, "prioridad": {"type": "string"}}}}}, "required": ["planSemanal"]}
)
CONSULTAR_ESTADISTICAS_TOOL = types.FunctionDeclaration(
    name="ConsultarEstadisticas", description="Consulta estadísticas.",
    parameters={"type": "object", "properties": {"consulta": {"type": "string"}}, "required": ["consulta"]}
)
PLANIFICADOR_PROYECTOS_TOOL = types.FunctionDeclaration(
    name="PlanificadorProyectos", description="Desglosa proyectos complejos en hitos.",
    parameters={"type": "object", "properties": {"hitos": {"type": "array", "items": {"type": "object", "properties": {"titulo": {"type": "string"}, "descripcion": {"type": "string"}, "fecha_limite": {"type": "string"}, "peso": {"type": "integer"}}}}}, "required": ["hitos"]}
)
GUARDAR_PROYECTO_TOOL = types.FunctionDeclaration(
    name="GuardarProyecto", description="Guarda proyecto.",
    parameters={"type": "object", "properties": {"nombre": {"type": "string"}, "descripcion": {"type": "string"}, "fecha_fin": {"type": "string"}, "hitos": {"type": "array", "items": {"type": "object", "properties": {"titulo": {"type": "string"}, "descripcion": {"type": "string"}, "fecha_limite": {"type": "string"}, "peso": {"type": "integer"}}}}}, "required": ["nombre", "fecha_fin", "hitos"]}
)
ALL_TOOLS = [PLAN_SEMANAL_TOOL, CONSULTAR_ESTADISTICAS_TOOL, PLANIFICADOR_PROYECTOS_TOOL, GUARDAR_PROYECTO_TOOL]

# --- FILE MANAGERS ---
def save_json(file, data):
    with open(file, 'w') as f: json.dump(data, f, indent=4)
def load_json(file, default=None):
    return json.load(open(file)) if os.path.exists(file) else default
def save_user_profile(data): save_json(PROFILE_FILE, data)
def load_user_profile(): return load_json(PROFILE_FILE)
def delete_user_profile(): 
    files = [PROFILE_FILE, CHAT_FILE, PROJECTS_FILE, DATA_FILE, MODEL_FILE]
    for f in files:
        if os.path.exists(f): 
            try: os.remove(f)
            except: pass
    return True
def load_chat_history(): return load_json(CHAT_FILE, [])
def save_chat_history(h): save_json(CHAT_FILE, h)
def load_projects(): return load_json(PROJECTS_FILE, [])
def save_projects(p): save_json(PROJECTS_FILE, p)

# --- AI LOGIC ---
def build_system_instruction(profile):
    if not profile: return "Eres un asistente."
    projects = load_projects()
    p_ctx = ", ".join([p['nombre'] for p in projects]) if projects else "Ninguno"
    today = datetime.now().strftime('%Y-%m-%d')
    laboral = f"TRABAJA: {profile.get('horario_trabajo_inicio')}-{profile.get('horario_trabajo_fin')}" if profile.get('trabaja') else ""
    
    # PROMPT REFORZADO: OBLIGAMOS A USAR HERRAMIENTAS
    return (f"Eres Asistente UPN. Hoy: {today}. Usuario: {profile.get('nombre')}. Carrera: {profile.get('carrera')}. {laboral}. Proyectos: {p_ctx}. "
            "REGLAS CRÍTICAS:\n"
            "1. Si el usuario pide un PLAN DE ESTUDIO o una ESTRUCTURA para aprender algo: ¡ESTÁ PROHIBIDO escribir una lista de texto!\n"
            "2. DEBES usar obligatoriamente la herramienta 'PlanificadorProyectos' para generar los hitos.\n"
            "3. Si pide un horario, usa 'PlanSemanal'.\n"
            "4. Sé conciso.")

def generate_project_plan_ai(profile, project_info):
    client = genai.Client()
    prompt = f"PROJECT MANAGER: Desglosa '{project_info['nombre']}' (Fin: {project_info['fecha_fin']}) en hitos."
    try:
        resp = client.models.generate_content(model='gemini-2.5-flash', contents=[{"role":"user","parts":[{"text":prompt}]}], config=types.GenerateContentConfig(tools=[types.Tool(function_declarations=[PLANIFICADOR_PROYECTOS_TOOL])], tool_config=types.ToolConfig(function_calling_config=types.FunctionCallingConfig(mode='ANY'))))
        if resp.function_calls: return resp.function_calls[0].args['hitos']
    except: pass
    return []

def call_gemini_generic(prompt, profile, tools, mode='ANY'):
    client = genai.Client()
    try:
        resp = client.models.generate_content(model='gemini-2.5-flash', contents=[{"role":"user","parts":[{"text":prompt}]}], config=types.GenerateContentConfig(tools=[types.Tool(function_declarations=tools)], tool_config=types.ToolConfig(function_calling_config=types.FunctionCallingConfig(mode=mode)), system_instruction=build_system_instruction(profile)))
        if resp.function_calls:
            args = resp.function_calls[0].args
            return {"role": "assistant", "text": "Plan generado.", "horario": dict(args)}
        return {"role": "assistant", "text": resp.text}
    except Exception as e: return {"role": "assistant", "text": str(e)}

def generate_initial_schedule(profile):
    today = datetime.now().strftime('%Y-%m-%d')
    prompt = f"Genera horario semanal optimizado. Hoy: {today}. "
    if profile.get('trabaja'): prompt += f"Bloquea TRABAJO de {profile.get('horario_trabajo_inicio')} a {profile.get('horario_trabajo_fin')}. "
    return call_gemini_generic(prompt, profile, [PLAN_SEMANAL_TOOL])

def generate_exam_schedule(profile, exams):
    prompt = "Genera plan de estudio para exámenes:\n" + "\n".join([f"- {e['materia']} ({e['fecha']})" for e in exams])
    return call_gemini_generic(prompt, profile, [PLAN_SEMANAL_TOOL])

def generate_crisis_schedule(profile, exams): 
    return call_gemini_generic("MODO CRISIS. Plan de supervivencia exámenes.", profile, [PLAN_SEMANAL_TOOL])

def process_chat(history):
    profile = load_user_profile()
    formatted = [{"role": "model" if m['role']=="assistant" else "user", "parts": [{"text": m['text']}]} for m in history]
    client = genai.Client()
    try:
        resp = client.models.generate_content(
            model='gemini-2.5-flash', contents=formatted, 
            config=types.GenerateContentConfig(tools=[types.Tool(function_declarations=ALL_TOOLS)], tool_config=types.ToolConfig(function_calling_config=types.FunctionCallingConfig(mode='AUTO')), system_instruction=build_system_instruction(profile))
        )
        ai_text = resp.text or "Entendido."
        
        if resp.function_calls:
            call = resp.function_calls[0]
            if call.name == "ConsultarEstadisticas":
                rep = generar_reporte_analitico()
                resp2 = client.models.generate_content(model='gemini-2.5-flash', contents=[{"role":"user","parts":[{"text":f"Datos:\n{rep}\nResponde."}]}])
                ai_text = resp2.text
            elif call.name == "PlanSemanal":
                plan = dict(call.args)
                msg = {"role":"assistant", "text":"📅 He creado tu horario:", "horario":plan}
                history.append(msg); save_chat_history(history)
                return msg
            elif call.name == "PlanificadorProyectos":
                hitos = list(call.args.get('hitos', []))
                # AQUÍ EL CAMBIO: Enviamos 'hitos' como objeto, no solo texto
                msg = {
                    "role": "assistant", 
                    "text": "📋 Aquí tienes una propuesta estructurada para tu proyecto. ¿Te gustaría guardarlo?", 
                    "hitos": hitos
                }
                history.append(msg); save_chat_history(history)
                return msg
            elif call.name == "GuardarProyecto":
                data = dict(call.args)
                nuevo = {
                    "id": datetime.now().strftime("%Y%m%d%H%M%S"),
                    "nombre": data.get('nombre', 'Proyecto IA'),
                    "descripcion": data.get('descripcion', ''),
                    "fecha_fin": data.get('fecha_fin', ''),
                    "progreso": 0,
                    "hitos": list(data.get('hitos', []))
                }
                for h in nuevo['hitos']: h['completado'] = False
                p = load_projects(); p.append(nuevo); save_projects(p)
                ai_text = f"✅ Proyecto **{nuevo['nombre']}** guardado en tu gestor."

        history.append({"role":"assistant", "text":ai_text})
        save_chat_history(history)
        return {"role":"assistant", "text":ai_text}
    except Exception as e: return {"role":"assistant", "text":str(e)}