from datetime import datetime, timedelta
import unicodedata
import logging
# Importación corregida a ruta absoluta del paquete
from backend.utils.config_utils import normalize_day

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def parse_time(time_str):
    """Convierte una cadena de hora (ej. '08:00am') a un objeto datetime."""
    time_str = str(time_str).replace(' ', '').lower()
    if not time_str:
        return datetime.max
        
    try:
        dt = datetime.strptime(time_str, '%I:%M%p')
        return dt
    except ValueError:
        try:
            dt = datetime.strptime(time_str, '%H:%M') 
            return dt
        except ValueError:
            logging.error(f"Formato de hora no reconocido: {time_str}")
            return datetime.max
        
def get_sort_key(item):
    """Clave de ordenamiento: Día (índice) + Hora (segundos desde medianoche)."""
    dias_semana = ['Lunes', 'Martes', 'Miércoles', 'Jueves', 'Viernes', 'Sábado', 'Domingo']
    try:
        dia_index = dias_semana.index(item['Dia'])
    except ValueError:
        dia_index = 99 
        
    hora_dt = parse_time(item['Hora'])
    
    hora_sort = hora_dt.hour * 3600 + hora_dt.minute * 60 + hora_dt.second
    
    return f"{dia_index:02d}{hora_sort:06d}"

def detectar_conflictos(horario_base):
    """Revisa el horario consolidado y detecta solapamientos reales."""
    conflictos = []
    
    # Exclusión de bloques que inician a las 10:00pm y terminan a las 5:00am al día siguiente
    def get_actual_fin_dt(actual):
        actual_fin_dt = parse_time(actual['Hora_Fin'])
        if actual['Actividad'].startswith('Dormir'):
            # El bloque de dormir termina al día siguiente, ajustamos el tiempo de fin para ordenar
            inicio_dt = parse_time(actual['Hora'])
            fin_dt_despertar = parse_time(actual['Hora_Fin'])
            if inicio_dt.hour >= 12 and fin_dt_despertar.hour < 12:
                return fin_dt_despertar + timedelta(days=1)
        return actual_fin_dt

    horario_ordenado = sorted(horario_base, key=get_sort_key)
    
    for i in range(len(horario_ordenado) - 1):
        actual = horario_ordenado[i]
        siguiente = horario_ordenado[i+1]
        
        if actual['Dia'] == siguiente['Dia']:
            
            actual_fin_dt = get_actual_fin_dt(actual)
            siguiente_inicio_dt = parse_time(siguiente['Hora'])
            
            # Solo detecta conflicto si el fin de la actividad actual se solapa con el inicio de la siguiente
            if actual_fin_dt > siguiente_inicio_dt:
                conflictos.append({
                    "Dia": actual['Dia'],
                    "Actividad_1": actual['Actividad'],
                    "Hora_1": f"{actual['Hora']} - {actual['Hora_Fin']}",
                    "Actividad_2": siguiente['Actividad'],
                    "Hora_2": f"{siguiente['Hora']} - {siguiente['Hora_Fin']}"
                })
                
    return conflictos

def generar_recomendacion(prioridades, filtro_dia, dia_seleccionado):
    """Genera un horario semanal condensado basado en prioridades."""
    
    dias_semana = ['Lunes', 'Martes', 'Miércoles', 'Jueves', 'Viernes', 'Sábado', 'Domingo']
    horario_base = []

    actividades_prioritarias = [
        ('estudio', 'Académico'),
        ('ejercicio', 'Físico'),
        ('trabajo', 'Laboral'),
    ]

    for dia in dias_semana:
        
        dia_normalized = normalize_day(dia)
        dia_eventos = []
        
        hora_despertar = prioridades.get('sueno_fin', '06:00 am')
        hora_dormir = prioridades.get('sueno_inicio', '10:00 pm')
        sueno_min = prioridades.get('sueno_min', 8)
        
        dia_eventos.append({'Dia': dia, 'Hora': hora_despertar, 'Actividad': 'Despertar y Desayuno', 'Prioridad': 'Bienestar', 'Tipo': 'Fijo', 'Fin_Hora': hora_despertar})
        dia_eventos.append({'Dia': dia, 'Hora': hora_dormir, 'Actividad': f"Dormir ({sueno_min}h)", 'Prioridad': 'Sueño', 'Tipo': 'Dormir', 'Fin_Hora': hora_despertar})


        if dia in ['Lunes', 'Martes', 'Miércoles', 'Jueves', 'Viernes']:
            
            for actividad, prioridad_tipo in actividades_prioritarias:
                
                inicio_key_specific = f'{actividad}_inicio_{dia_normalized}'
                fin_key_specific = f'{actividad}_fin_{dia_normalized}'
                
                # Prioriza el valor específico del día, si no existe, usa el valor base.
                inicio = prioridades.get(inicio_key_specific) or prioridades.get(f'{actividad}_inicio')
                fin = prioridades.get(fin_key_specific) or prioridades.get(f'{actividad}_fin')
                
                if inicio and fin:
                    dia_eventos.append({
                        'Dia': dia, 'Hora': inicio, 'Actividad': f"Bloque de {actividad.capitalize()}", 
                        'Prioridad': prioridad_tipo, 'Fin_Hora': fin, 'Tipo': 'Principal'
                    })
                    
            dia_eventos.append({'Dia': dia, 'Hora': '12:00 pm', 'Actividad': 'Almuerzo y Pausa Activa', 'Prioridad': 'Bienestar', 'Tipo': 'Principal', 'Fin_Hora': '01:00 pm'})
            
            for actividad_extra in prioridades.get('otras_actividades', []):
                dias_aplicables = actividad_extra.get('dias', 'Todos').upper()
                
                aplica_a_hoy = 'TODOS' in dias_aplicables or dia.upper() in dias_aplicables or ('LUNES-VIERNES' in dias_aplicables and dia in ['Lunes', 'Martes', 'Miércoles', 'Jueves', 'Viernes'])

                if aplica_a_hoy:
                    nombre = actividad_extra.get('nombre', 'Actividad Extra')
                    inicio = actividad_extra.get('inicio')
                    fin = actividad_extra.get('fin')
                    
                    prioridad_tipo_extra = 'Académico' if 'examen' in nombre.lower() or 'cita' in nombre.lower() or 'conferencia' in nombre.lower() else 'Ocio'
                    
                    if inicio and fin:
                        dia_eventos.append({
                            'Dia': dia, 'Hora': inicio, 'Actividad': nombre, 
                            'Prioridad': prioridad_tipo_extra, 'Fin_Hora': fin, 'Tipo': 'Extra'
                        })

        elif dia == 'Sábado':
            dia_eventos.append({'Dia': dia, 'Hora': '10:00 am', 'Actividad': 'Bloque Flexible (Repaso/Ocio)', 'Prioridad': 'Flexible', 'Tipo': 'Principal', 'Fin_Hora': '12:00 pm'})
            dia_eventos.append({'Dia': dia, 'Hora': '12:00 pm', 'Actividad': 'Almuerzo y Pausa Activa', 'Prioridad': 'Bienestar', 'Tipo': 'Principal', 'Fin_Hora': '01:00 pm'})

        elif dia == 'Domingo':
            dia_eventos.append({'Dia': dia, 'Hora': '10:00 am', 'Actividad': 'Descanso / Planificación Semanal', 'Prioridad': 'Bienestar', 'Tipo': 'Principal', 'Fin_Hora': '12:00 pm'})
            dia_eventos.append({'Dia': dia, 'Hora': '12:00 pm', 'Actividad': 'Almuerzo y Pausa Activa', 'Prioridad': 'Bienestar', 'Tipo': 'Principal', 'Fin_Hora': '01:00 pm'})

        dia_eventos_ordenados = sorted(dia_eventos, key=get_sort_key)
        
        bloques_consolidados = []
        for i, evento in enumerate(dia_eventos_ordenados):
            
            if evento['Tipo'] in ['Principal', 'Extra', 'Dormir', 'Fijo']:
                
                inicio_dt = parse_time(evento['Hora'])
                explicit_fin_dt = parse_time(evento.get('Fin_Hora', ''))
                
                fin_dt = explicit_fin_dt
                
                # Manejo de Bloque de Dormir que cruza la medianoche
                if evento['Tipo'] == 'Dormir':
                    fin_dt_despertar = parse_time(hora_despertar)
                    if inicio_dt.hour >= 12 and fin_dt_despertar.hour < 12:
                        fin_dt = fin_dt_despertar + timedelta(days=1)
                    else:
                        fin_dt = fin_dt_despertar
                        
                # Recortar el bloque si choca con el inicio del siguiente bloque de mayor prioridad
                if i + 1 < len(dia_eventos_ordenados):
                    siguiente_inicio_dt = parse_time(dia_eventos_ordenados[i+1]['Hora'])
                    
                    if fin_dt > siguiente_inicio_dt:
                        fin_dt = siguiente_inicio_dt
                
                if fin_dt <= inicio_dt:
                    continue

                duration_seconds = (fin_dt - inicio_dt).total_seconds()
                duracion_horas = round(duration_seconds / 3600, 1)

                if duracion_horas > 0:
                    bloques_consolidados.append({
                        'Dia': evento['Dia'],
                        'Hora': evento['Hora'].replace(' ', '').lower(),
                        'Hora_Fin': fin_dt.strftime('%I:%M %p').lstrip('0').lower(), 
                        'Actividad': evento['Actividad'],
                        'Prioridad': evento['Prioridad'],
                        'Duracion_Horas': duracion_horas 
                    })
        
        horario_base.extend(bloques_consolidados)


    conflictos_detectados = detectar_conflictos(horario_base)
    
    if filtro_dia and filtro_dia.upper() == 'SINGLE_DAY' and dia_seleccionado:
        dia_norm_buscado = normalize_day(dia_seleccionado)
        return [item for item in horario_base if normalize_day(item['Dia']) == dia_norm_buscado], conflictos_detectados

    return horario_base, conflictos_detectados