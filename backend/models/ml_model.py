import pandas as pd
from sklearn.ensemble import RandomForestRegressor
from sklearn.preprocessing import LabelEncoder
import joblib
import os
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Rutas de archivos (usadas por la API, pero definidas aquí para ML)
APP_ROOT = os.path.dirname(os.path.abspath(__file__))
HISTORIAL_PATH = os.path.join(APP_ROOT, '..', 'historial.csv')
MODEL_PATH = os.path.join(APP_ROOT, '..', 'horario_model.pkl')

def inicializar_o_cargar_datos():
    """Carga o crea el historial de estudio."""
    if not os.path.exists(HISTORIAL_PATH):
        data = {
            'Materia': ['Cálculo', 'Cálculo', 'Historia', 'Historia', 'Física', 'Física', 'Cálculo', 'Física', 'Cálculo'],
            'Dificultad_Escala': [5, 4, 2, 3, 5, 6, 7, 8, 9], 
            'Horas_Estudio_Total': [15, 12, 5, 8, 18, 20, 25, 28, 30], 
            'Calificacion': [8, 7, 9, 8, 6, 7, 9, 7, 8] 
        }
        df = pd.DataFrame(data)
        df.to_csv(HISTORIAL_PATH, index=False)
    return pd.read_csv(HISTORIAL_PATH)

def entrenar_modelo():
    """Entrena o reentrena el modelo de regresión."""
    df = inicializar_o_cargar_datos()
    mean_hours = df['Horas_Estudio_Total'].mean()
    if mean_hours == 0:
        mean_hours = 1
        
    df['Eficiencia'] = df['Calificacion'] * (df['Horas_Estudio_Total'] / mean_hours)
    
    le = LabelEncoder()
    if not df.empty and 'Materia' in df.columns:
        df['Materia_Encoded'] = le.fit_transform(df['Materia'])
    else:
        df['Materia_Encoded'] = 0 
        le.fit(['Default']) 
        
    X = df[['Dificultad_Escala', 'Horas_Estudio_Total', 'Materia_Encoded']]
    y = df['Calificacion'] 
    model = RandomForestRegressor(n_estimators=100, random_state=42)
    model.fit(X, y)
    
    # Guarda el modelo y el encoder (Necesario para la inferencia futura)
    joblib.dump((model, le, mean_hours), MODEL_PATH)
    logging.info("Modelo ML reentrenado y guardado.")
    return le

# Inicializa el encoder global al cargar el módulo
le_encoder = entrenar_modelo()

def get_encoder():
    """Devuelve el LabelEncoder inicializado."""
    return le_encoder