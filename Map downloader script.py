import requests # Descargar tiles de mapas desde servidores web
import math # Conversión de coordenadas geográficas a tiles
import os # Operaciones de sistema de archivos
import time # Pausas para evitar sobrecargar servidores

# URL DEL SERVICIO DE MAPAS SATELITALES
servicio_mapa = "https://services.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}"

# NIVELES DE ZOOM PREDEFINIDOS
zoom_mundo = 7 # Equivale a x metros de altura
zoom_ciudad = 18 # Equivale a x metros de altura

# CONFIGURACIÓN DE DIRECTORIOS Y ARCHIVOS
carpeta_base = "Maps" # Carpeta principal donde se almacenan todos los mapas
archivo_ciudades = "Cities.txt" # Archivo de texto con coordenadas de ciudades

# FUNCIONES AUXILIARES
# Convierte coordenadas geográficas a coordenadas de tile web (x, y, zoom)
def latlon_a_tile(lat, lon, nivel_zoom):
    # Calcular número total de tiles a este nivel de zoom
    numero_total_tiles = 2.0 ** nivel_zoom
    
    # Convertir latitud a radianes para cálculos trigonométricos
    latitud_radianes = math.radians(lat)
    
    # Calcular coordenada X del tile (columna horizontal)
    coordenada_x = int(((lon + 180.0) / 360.0) * numero_total_tiles)
    
    # Calcular coordenada Y del tile (fila vertical) usando proyección Mercator inversa
    coordenada_y = int(((1.0 - (math.log(math.tan(latitud_radianes) + (1.0 / math.cos(latitud_radianes))) / math.pi)) / 2.0) * numero_total_tiles)
    
    return coordenada_x, coordenada_y

# Convierte coordenadas de tile web (x, y, zoom) a coordenadas geográficas de límites
def tile_a_limites_geograficos(x_tile, y_tile, nivel_zoom):
    # Calcular número total de tiles en este nivel de zoom (2^zoom)
    numero_total_tiles = 2.0 ** nivel_zoom
    
    # Convertir coordenadas de tile a coordenadas geográficas de esquina noroeste
    # Longitud oeste: fórmula lineal basada en el número de tile horizontal
    longitud_oeste = (x_tile / numero_total_tiles * 360.0) - 180.0
    
    # Latitud norte: fórmula no lineal debido a proyección Mercator
    latitud_norte_radianes = math.atan(math.sinh(math.pi * (1.0 - (2.0 * y_tile / numero_total_tiles))))
    latitud_norte = math.degrees(latitud_norte_radianes)
    
    # Calcular latitud sur del mismo tile (tile siguiente en Y)
    latitud_sur_radianes = math.atan(math.sinh(math.pi * (1.0 - (2.0 * (y_tile + 1) / numero_total_tiles))))
    latitud_sur = math.degrees(latitud_sur_radianes)
    
    # Calcular longitud este del mismo tile (tile siguiente en X)
    longitud_este = ((x_tile + 1) / numero_total_tiles * 360.0) - 180.0
    
    return latitud_norte, longitud_este, latitud_sur, longitud_oeste

# Genera nombre de archivo usando formato: N{lat_norte}_E{lon_este}_S{lat_sur}_O{lon_oeste}.jpg
def generar_nombre_tile(lat_norte, lon_este, lat_sur, lon_oeste, precision = 4):
    # Convertir todas las coordenadas a valores absolutos (positivos)
    lat_norte_abs = abs(lat_norte)
    lon_este_abs = abs(lon_este)
    lat_sur_abs = abs(lat_sur)
    lon_oeste_abs = abs(lon_oeste)
    
    # Formato para números con precisión específica de decimales
    formato_coordenada = f"{{:.{precision}f}}"
    
    # Formatear cada coordenada y eliminar ceros innecesarios al final
    norte_str = formato_coordenada.format(lat_norte_abs).rstrip('0').rstrip('.')
    este_str = formato_coordenada.format(lon_este_abs).rstrip('0').rstrip('.')
    sur_str = formato_coordenada.format(lat_sur_abs).rstrip('0').rstrip('.')
    oeste_str = formato_coordenada.format(lon_oeste_abs).rstrip('0').rstrip('.')
    
    # Asegurar que haya al menos un dígito después del punto decimal
    if '.' not in norte_str:
        norte_str += '.0'
    if '.' not in este_str:
        este_str += '.0'
    if '.' not in sur_str:
        sur_str += '.0'
    if '.' not in oeste_str:
        oeste_str += '.0'
    
    # Construir nombre final con orden fijo: N, E, S, O
    nombre_final = f"N{norte_str}_E{este_str}_S{sur_str}_O{oeste_str}.jpg"
    
    return nombre_final

# Descarga un tile individual desde el servicio de mapas y lo guarda en disco
def descargar_tile_servicio(x_tile, y_tile, zoom, ruta_archivo):
    try:
        # Construir URL completa sustituyendo parámetros en el patrón del servicio
        url_completa = servicio_mapa.format(z = zoom, x = x_tile, y = y_tile)
        
        # Configurar cabecera de usuario para simular navegador web
        cabeceras_peticion = {"User-Agent": "Mozilla/5.0"}
        
        # Realizar petición HTTP con tiempo límite de 30 segundos
        respuesta_servidor = requests.get(url_completa, timeout = 30, headers = cabeceras_peticion)
        
        # Verificar respuesta exitosa y contenido válido (no vacío o corrupto)
        if respuesta_servidor.status_code == 200 and len(respuesta_servidor.content) > 1000:
            # Guardar contenido binario de la imagen directamente en archivo
            with open(ruta_archivo, 'wb') as archivo_destino:
                archivo_destino.write(respuesta_servidor.content)
            
            return True  # Indicar éxito en la descarga
        else:
            return False  # Indicar fallo en la descarga (respuesta no válida)
            
    except Exception as error:
        # Capturar cualquier excepción (conexión, timeout, etc.) y retornar fallo
        return False

# Busca información de una ciudad en el archivo de texto de ciudades
def buscar_informacion_ciudad(nombre_ciudad, ruta_archivo):
    # Normalizar nombre de ciudad para comparación insensible a mayúsculas/minúsculas
    nombre_normalizado = nombre_ciudad.strip().lower().replace(' ', '_')
    
    try:
        # Abrir archivo de ciudades en modo lectura con codificación UTF-8
        with open(ruta_archivo, 'r', encoding = 'utf-8') as archivo:
            # Procesar cada línea del archivo secuencialmente
            for linea_actual in archivo:
                # Eliminar espacios en blanco al inicio y final de la línea
                linea_limpia = linea_actual.strip()
                
                # Ignorar líneas vacías (no procesables)
                if not linea_limpia:
                    continue
                
                # Dividir línea usando coma como separador de campos
                campos_linea = linea_limpia.split(',')
                
                # Verificar que la línea tenga exactamente 5 campos (nombre + 4 coordenadas)
                if len(campos_linea) == 5:
                    # Extraer y normalizar nombre de ciudad del archivo
                    nombre_archivo = campos_linea[0].strip().lower()
                    
                    # Comparar nombre solicitado con nombre en archivo
                    if nombre_archivo == nombre_normalizado:
                        try:
                            # Convertir strings a números flotantes (coordenadas decimales)
                            coordenada_norte = float(campos_linea[1].strip())
                            coordenada_este = float(campos_linea[2].strip())
                            coordenada_sur = float(campos_linea[3].strip())
                            coordenada_oeste = float(campos_linea[4].strip())
                            
                            # Retornar todas las coordenadas como tupla de 4 valores
                            return coordenada_norte, coordenada_este, coordenada_sur, coordenada_oeste
                        except ValueError:
                            # Error en conversión numérica: ignorar línea y continuar búsqueda
                            continue
    except Exception as error:
        # Error al abrir o leer archivo: retornar None (ciudad no encontrada)
        pass
    
    return None  # Retornar None si ciudad no fue encontrada en el archivo

# Descarga todos los tiles del mundo en el nivel de zoom configurado
def descargar_mapa_mundial():
    # Crear ruta completa para carpeta de mapas mundiales
    carpeta_mundo = os.path.join(carpeta_base, "World")
    
    # Crear carpeta si no existe (exist_ok evita error si ya existe)
    os.makedirs(carpeta_mundo, exist_ok = True)
    
    # Mostrar mensaje indicando inicio de descarga
    print("Downloading...")
    
    # Calcular número total de tiles en cada dimensión para este zoom
    numero_tiles_dimension = 2 ** zoom_mundo
    
    # Bucle para recorrer todas las coordenadas X (columnas) de tiles
    for coordenada_x in range(numero_tiles_dimension):
        # Bucle para recorrer todas las coordenadas Y (filas) de tiles
        for coordenada_y in range(numero_tiles_dimension):
            # Calcular límites geográficos de este tile específico
            latitud_norte, longitud_este, latitud_sur, longitud_oeste = tile_a_limites_geograficos(
                coordenada_x, coordenada_y, zoom_mundo
            )
            
            # Generar nombre de archivo basado en los límites calculados
            nombre_archivo_tile = generar_nombre_tile(latitud_norte, longitud_este, latitud_sur, longitud_oeste)
            ruta_completa_archivo = os.path.join(carpeta_mundo, nombre_archivo_tile)
            
            # Verificar si el archivo ya existe antes de descargar
            if not os.path.exists(ruta_completa_archivo):
                # Intentar descargar el tile desde el servicio web
                descargar_tile_servicio(coordenada_x, coordenada_y, zoom_mundo, ruta_completa_archivo)
            
            # Pausa breve para no sobrecargar el servidor y evitar bloqueos
            time.sleep(0.2)
    
    # Salto de línea
    print("")
    
    # Retornar True si el proceso se completó
    return True

# Descarga todos los tiles dentro del área de una ciudad sin duplicados
def descargar_ciudad_completa(nombre_ciudad, norte, este, sur, oeste):
    # Crear nombre de carpeta basado en el nombre de la ciudad
    nombre_carpeta_ciudad = nombre_ciudad.strip().title()
    carpeta_ciudad = os.path.join(carpeta_base, nombre_carpeta_ciudad)
    
    # Crear carpeta de la ciudad si no existe
    os.makedirs(carpeta_ciudad, exist_ok = True)
    
    # Mostrar mensaje indicando inicio de descarga para esta ciudad
    print(f"Downloading...")
    
    # Salto de línea
    print("")
    
    # Convertir coordenadas límite a tiles en el nivel de zoom de ciudad
    # Esquina noroeste (norte, oeste) para obtener tile mínimo
    x_min, y_min = latlon_a_tile(norte, oeste, zoom_ciudad)
    
    # Esquina sureste (sur, este) para obtener tile máximo
    x_max, y_max = latlon_a_tile(sur, este, zoom_ciudad)
    
    # Asegurar que x_min < x_max y y_min < y_max
    if x_min > x_max:
        x_min, x_max = x_max, x_min
    
    if y_min > y_max:
        y_min, y_max = y_max, y_min
    
    # Bucle para recorrer todos los tiles en el rango calculado
    for x_tile in range(x_min, x_max + 1):
        for y_tile in range(y_min, y_max + 1):
            # Calcular límites geográficos de este tile específico
            latitud_norte, longitud_este, latitud_sur, longitud_oeste = tile_a_limites_geograficos(
                x_tile, y_tile, zoom_ciudad
            )
            
            # Generar nombre de archivo basado en los límites calculados
            nombre_archivo_tile = generar_nombre_tile(latitud_norte, longitud_este, latitud_sur, longitud_oeste)
            ruta_completa_archivo = os.path.join(carpeta_ciudad, nombre_archivo_tile)
            
            # Verificar si el archivo ya existe antes de descargar
            if not os.path.exists(ruta_completa_archivo):
                # Intentar descargar el tile desde el servicio web
                descargar_tile_servicio(x_tile, y_tile, zoom_ciudad, ruta_completa_archivo)
            
            # Pausa breve para no sobrecargar el servidor y evitar bloqueos
            time.sleep(0.05)
    
    # Retornar True si el proceso se completó
    return True

# Verifica si el archivo de ciudades existe en el directorio actual
def verificar_existencia_archivo_ciudades():
    # Verificar existencia del archivo Cities.txt en el directorio actual
    return os.path.exists(archivo_ciudades)

# PUNTO DE INICIO DEL PROGRAMA
# Crear carpeta base para mapas si no existe
os.makedirs(carpeta_base, exist_ok = True)

# Mostrar instrucción inicial para usuario
print("Enter 'world' to download world map\n")

# BUCLE PRINCIPAL DEL PROGRAMA
while True:
    # Verificar existencia del archivo de ciudades antes de proceder
    if not verificar_existencia_archivo_ciudades():
        print("Cities.txt not found")
        print("Place file in script directory")
        input()  # Pausar para que usuario coloque el archivo
        
        continue  # Volver al inicio del bucle principal
    
    # BUCLE INTERNO PARA SOLICITUD DE CIUDAD
    while True:
        # Solicitar nombre de ciudad o comando al usuario
        entrada_usuario = input("Enter city name: ").strip()
        
        # Ignorar entrada vacía y mostrar línea en blanco
        if not entrada_usuario:
            print("\n")
            
            continue
        
        # CASO 1: Usuario solicita mapa mundial completo
        if entrada_usuario.lower() == "world":
            if descargar_mapa_mundial():
                
                break  # Salir del bucle interno, volver al principal
            else:
                print("Download failed\n")
                
                continue  # Reintentar en el bucle interno
        
        # CASO 2: Usuario solicita ciudad específica
        informacion_ciudad = buscar_informacion_ciudad(entrada_usuario, archivo_ciudades)
        
        # Si ciudad no está en el archivo, informar al usuario
        if informacion_ciudad is None:
            print("City not available\n")
            
            continue  # Volver a solicitar ciudad en bucle interno
        
        # Extraer límites de la ciudad de la tupla retornada
        coordenada_norte, coordenada_este, coordenada_sur, coordenada_oeste = informacion_ciudad
        
        # Intentar descargar ciudad completa con todos sus tiles
        if descargar_ciudad_completa(entrada_usuario, coordenada_norte, coordenada_este, coordenada_sur, coordenada_oeste):
            
            break  # Salir del bucle interno, volver al principal
        else:
            print("Download failed\n")
            
            continue  # Reintentar en el bucle interno