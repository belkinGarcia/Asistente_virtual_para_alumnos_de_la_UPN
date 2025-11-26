# ml_model.py - Módulo para la lógica de Machine Learning (MLOps)

import pandas as pd
import numpy as np
import os
import pickle
import logging

# Simulación de un modelo de Regresión (por ejemplo, Regresión Lineal o SVR)
# El modelo real debe ser implementado aquí.

MODEL_PATH = os.path.join(os.path.dirname(__file__), 'horario_model.pkl')
CSV_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'historial.csv')
ml_model_instance = None
logging.getLogger().setLevel(logging.INFO)

def inicializar_o_cargar_datos():
    """Crea o carga el DataFrame de historial (feedback de MLOps)."""
    if os.path.exists(CSV_PATH):
        try:
            df = pd.read_csv(CSV_PATH)
            return df
        except Exception as e:
            logging.error(f"Error al cargar historial.csv: {e}")
            pass

    # Si el archivo no existe o falla la carga, crea un DataFrame base con datos de ejemplo
    logging.info("Creando historial.csv base.")
    data = {
        'Materia': ['ML', 'Tesis', 'Comunicaciones', 'ML'],
        'Dificultad_Escala': [8, 9, 4, 7], # Escala de 1 a 10
        'Horas_Estudio_Total': [5.0, 10.0, 2.0, 6.5],
        'Calificacion': [9, 7, 10, 8] # Escala de 1 a 10
    }
    df = pd.DataFrame(data)
    # Guarda el archivo base para la siguiente ejecución
    df.to_csv(CSV_PATH, index=False)
    return df

def entrenar_modelo():
    """Simula el reentrenamiento del modelo ML usando los datos del historial."""
    global ml_model_instance
    try:
        df = inicializar_o_cargar_datos()
        
        # --- Lógica de Entrenamiento Real (Aquí se usaría scikit-learn) ---
        # 1. Definir X (features) y Y (target)
        # X = df[['Dificultad_Escala', 'Horas_Estudio_Total']]
        # Y = df['Calificacion']
        
        # 2. Entrenar el modelo de Regresión
        # from sklearn.svm import SVR
        # ml_model_instance = SVR(kernel='linear')
        # ml_model_instance.fit(X, Y)
        
        # 3. Guardar el modelo entrenado
        # with open(MODEL_PATH, 'wb') as file:
        #     pickle.dump(ml_model_instance, file)
        
        logging.info("Modelo ML simulado reentrenado y guardado.")
    except Exception as e:
        logging.error(f"Fallo en el reentrenamiento del modelo ML: {e}")

def cargar_modelo():
    """Carga el modelo ML desde el archivo .pkl."""
    global ml_model_instance
    if os.path.exists(MODEL_PATH):
        try:
            with open(MODEL_PATH, 'rb') as file:
                ml_model_instance = pickle.load(file)
            logging.info("Modelo ML cargado desde .pkl.")
            return True
        except Exception as e:
            logging.warning(f"No se pudo cargar el modelo desde .pkl: {e}. Se usará el valor por defecto.")
    return False

def predict_study_hours(avg_dificultad, horas_disponibles, horas_clase):
    """
    Simula la predicción de la cantidad de horas de estudio necesarias a la semana
    basada en el historial del estudiante. (Función clave del Aprendizaje Adaptativo).
    """
    cargar_modelo()
    if ml_model_instance:
        # Aquí se haría una predicción real con ml_model_instance.predict(...)
        # Por ahora, usamos un cálculo de ejemplo
        base_hours = (avg_dificultad / 10) * 15 # 15 horas base para la dificultad
        return round(base_hours + (horas_clase / 4), 1)
    
    # Valor de recomendación por defecto si el modelo no está entrenado o no se carga
    return 12.0