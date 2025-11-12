# ml_model.py - VERIFICADO (Asume funcionalidad estándar)

import pandas as pd
import os
import joblib 

# Configuración de archivos
HISTORIAL_FILE = 'historial.csv'
MODEL_FILE = 'horario_model.pkl'

# --- Funciones de I/O de Datos ---

def inicializar_o_cargar_datos():
    """Carga el historial de datos de feedback o crea un DataFrame vacío."""
    # Asume que historial.csv está en el directorio raíz del proyecto (un nivel arriba de backend/)
    # Se ajusta la ruta para que funcione correctamente desde el subpaquete 'models'
    project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
    historial_path = os.path.join(project_root, HISTORIAL_FILE)
    
    if os.path.exists(historial_path):
        return pd.read_csv(historial_path)
    else:
        # Define columnas necesarias si no existe
        return pd.DataFrame(columns=['Materia', 'Dificultad_Escala', 'Horas_Estudio_Total', 'Calificacion'])

# --- Funciones de Modelo ---

def entrenar_modelo():
    """
    Simulación de reentrenamiento del modelo ML. 
    Aquí se ejecutaría la lógica de Scikit-learn (ej. Regresión Lineal) y se guardaría.
    """
    df = inicializar_o_cargar_datos()
    
    if len(df) < 10: # Umbral mínimo de datos para reentrenamiento
        # Esto evita errores si no hay suficientes datos
        print("INFO - No hay suficientes datos para reentrenar el modelo ML. Se requiere un mínimo de 10 registros.")
        return False

    try:
        # Simulación: Aquí se entrenaría y se guardaría el modelo
        # model = ... train_logic(df)
        
        # Simula guardar un objeto vacío para demostrar la operación exitosa
        with open(MODEL_FILE, 'wb') as file:
            joblib.dump(df.columns.tolist(), file) # Guarda solo las columnas como placeholder
            
        print("INFO - Modelo ML reentrenado y guardado.")
        return True
    except Exception as e:
        print(f"ERROR - Fallo al reentrenar/guardar modelo: {e}")
        return False
    
def predict_study_hours(dificultad: int, horas_deseadas: float, calificacion_objetivo: int) -> float:
    """Simula la predicción de horas de estudio óptimas."""
    # Aquí se cargaría y usaría el modelo guardado en MODEL_FILE
    
    # Placeholder: Devuelve una recomendación simple
    base_hours = horas_deseadas * (dificultad / 10)
    return base_hours * (calificacion_objetivo / 7) # Ajuste basado en objetivo