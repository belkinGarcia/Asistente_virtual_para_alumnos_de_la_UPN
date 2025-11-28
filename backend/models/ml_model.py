import pandas as pd
import os
import joblib
from sklearn.ensemble import RandomForestRegressor
from datetime import datetime, timedelta

# Rutas
BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DATA_FILE = os.path.join(BASE_DIR, 'historial.csv')
MODEL_FILE = os.path.join(BASE_DIR, 'modelo_horas.pkl')

COLUMNAS = [
    'Materia', 'Horas_Estudio_Real', 'Dificultad_Cat', 'Dificultad_Num', 
    'Nivel_Energia', 'Cumplio_Objetivo', 'Factor_Bloqueo', 'Calificacion',
    'Horas_Sueno', 'Lugar_Estudio', 'Actividad_Fisica', 'Dia_Semana', 
    'Fecha', 'Tipo_Sesion'
]

def inicializar_o_cargar_datos():
    if os.path.exists(DATA_FILE):
        try:
            df = pd.read_csv(DATA_FILE)
            for col in COLUMNAS:
                if col not in df.columns:
                    val = 'Manual' if col == 'Tipo_Sesion' else ('2000-01-01' if col == 'Fecha' else 0)
                    df[col] = val
            return df
        except Exception as e:
            print(f"Error CSV: {e}")
    return pd.DataFrame(columns=COLUMNAS)

def entrenar_modelo():
    df = inicializar_o_cargar_datos()
    if len(df) < 5: return
    df = df[df['Horas_Estudio_Real'] > 0].copy()
    df['Dificultad_Num'] = df['Dificultad_Num'].fillna(2)
    df['Calificacion'] = df['Calificacion'].fillna(15) 
    X = df[['Dificultad_Num', 'Calificacion']]
    y = df['Horas_Estudio_Real']
    model = RandomForestRegressor(n_estimators=100, random_state=42)
    model.fit(X, y)
    joblib.dump(model, MODEL_FILE)

def predict_study_hours(dificultad_num, calificacion_deseada=20):
    if os.path.exists(MODEL_FILE):
        try:
            model = joblib.load(MODEL_FILE)
            prediction = model.predict([[dificultad_num, calificacion_deseada]])
            return max(0.5, min(12.0, prediction[0]))
        except: pass
    return 1.0 + (dificultad_num * 0.5)

def obtener_materias_unicas():
    df = inicializar_o_cargar_datos()
    if df.empty: return []
    return sorted(df['Materia'].astype(str).unique().tolist())

# --- GAMIFICACIÓN & DASHBOARD ---
def calcular_racha(df):
    if df.empty or 'Fecha' not in df.columns: return 0
    fechas = pd.to_datetime(df['Fecha'], errors='coerce').dropna().dt.date.unique()
    fechas = sorted(fechas, reverse=True)
    if not fechas: return 0
    hoy = datetime.now().date()
    if fechas[0] != hoy and fechas[0] != (hoy - timedelta(days=1)): return 0
    racha = 0
    check_date = fechas[0]
    for f in fechas:
        if f == check_date: racha += 1; check_date -= timedelta(days=1)
        else: break
    return racha

def calcular_logros(df):
    logros = []
    if len(df) >= 1: logros.append({"id": "novato", "icon": "🌱", "title": "Primeros Pasos", "desc": "Registraste tu primera sesión."})
    if not df[df['Horas_Estudio_Real'] >= 3].empty: logros.append({"id": "maraton", "icon": "🏃", "title": "Maratonista", "desc": "Estudiaste +3 horas seguidas."})
    if calcular_racha(df) >= 3: logros.append({"id": "fire", "icon": "🔥", "title": "On Fire", "desc": "Racha de 3 días."})
    if len(df) >= 10: logros.append({"id": "vet", "icon": "🎖️", "title": "Veterano", "desc": "10 sesiones registradas."})
    if df['Horas_Estudio_Real'].sum() >= 50: logros.append({"id": "king", "icon": "👑", "title": "Imparable", "desc": "50 horas totales."})
    if 'Tipo_Sesion' in df.columns:
        pomodoros = df[df['Tipo_Sesion'] == 'Pomodoro']
        if len(pomodoros) >= 5: logros.append({"id": "focus", "icon": "🍅", "title": "Maestro del Tiempo", "desc": "5 Pomodoros completados."})
    return logros

def obtener_datos_dashboard():
    df = inicializar_o_cargar_datos()
    stats = { "total_horas": 0, "sesiones_totales": 0, "promedio_energia": 0, "tasa_exito": 0, "materias_chart": [], "energia_chart": [], "nivel": 1, "xp_actual": 0, "xp_siguiente": 500, "racha_dias": 0, "logros": [] }
    if df.empty: return stats

    total_horas = df['Horas_Estudio_Real'].sum()
    sesiones = len(df)
    df['Nivel_Energia'] = pd.to_numeric(df['Nivel_Energia'], errors='coerce').fillna(0)
    promedio_energia = round(df['Nivel_Energia'].mean(), 1)
    exitos = df[df['Cumplio_Objetivo'] == 'sí']
    tasa_exito = int((len(exitos) / sesiones) * 100) if sesiones > 0 else 0

    xp_total = int((total_horas * 100) + (sesiones * 50))
    nivel = int(xp_total / 1000) + 1
    xp_en_nivel = xp_total % 1000
    xp_siguiente = 1000
    racha = calcular_racha(df)
    logros = calcular_logros(df)

    materia_grp = df.groupby('Materia')['Horas_Estudio_Real'].sum().sort_values(ascending=False).head(5)
    materias_chart = []
    max_horas = materia_grp.max() if not materia_grp.empty else 1
    for materia, horas in materia_grp.items():
        materias_chart.append({"label": materia, "value": round(horas, 1), "percent": int((horas / max_horas) * 100)})

    ultimas = df.tail(7).copy()
    ultimas['Label'] = ultimas.get('Dia_Semana', ultimas.index.astype(str))
    energia_chart = []
    for _, row in ultimas.iterrows():
        energia_chart.append({"label": str(row['Label'])[:3], "value": row['Nivel_Energia'], "percent": int((row['Nivel_Energia'] / 5) * 100)})

    return {
        "total_horas": round(total_horas, 1), "sesiones_totales": sesiones, "promedio_energia": promedio_energia,
        "tasa_exito": tasa_exito, "materias_chart": materias_chart, "energia_chart": energia_chart,
        "nivel": nivel, "xp_actual": xp_en_nivel, "xp_siguiente": xp_siguiente, "racha_dias": racha, "logros": logros
    }

def generar_reporte_analitico():
    df = inicializar_o_cargar_datos()
    if df.empty: return "No hay datos registrados aún."
    
    top_materias = df.groupby('Materia')['Horas_Estudio_Real'].sum().sort_values(ascending=False).head(3)
    texto_materias = ", ".join([f"{m} ({h}h)" for m, h in top_materias.items()])
    
    df['Nivel_Energia'] = pd.to_numeric(df['Nivel_Energia'], errors='coerce')
    energia_avg = df['Nivel_Energia'].mean()
    dia_mejor = df.groupby('Dia_Semana')['Nivel_Energia'].mean().idxmax() if not df.empty else "N/A"
    
    sueno_avg = df['Horas_Sueno'].mean() if 'Horas_Sueno' in df.columns else 0
    gym_freq = len(df[df['Actividad_Fisica'].str.contains('Gimnasio|Deporte', na=False)])

    return (
        f"ANÁLISIS DE DATOS:\n- Total estudiado: {df['Horas_Estudio_Real'].sum()}h.\n"
        f"- Top Materias: {texto_materias}.\n- Energía media: {energia_avg:.1f}/5. Mejor día: {dia_mejor}.\n"
        f"- Sueño promedio: {sueno_avg:.1f}h. Sesiones con Gym: {gym_freq}.\n"
    )