import requests  # Descargar tiles de mapas desde servidores web
import math      # Cálculos matemáticos: logaritmos, trigonometría, conversión de coordenadas
import os        # Operaciones de sistema de archivos: crear carpetas, verificar existencia
import time      # Manejo de tiempos y pausas para evitar sobrecargar servidores

# URL DEL SERVICIO DE MAPAS SATELITALES
servicio_mapa = "https://services.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}"

# ALTURAS PREDEFINIDAS PARA LOS DOS NIVELES DE DETALLE EN KILÓMETROS
altura_mundo_km = 78.3  # 78.3 kilómetros por tile para vista mundial completa
altura_ciudad_km = 0.306  # 306 metros por tile para vista detallada de ciudades

# CONSTANTES GEOGRÁFICAS
kilometros_por_grado_latitud = 111.0  # Aproximadamente 111 km por grado de latitud
radio_tierra_km = 6371.0  # Radio terrestre promedio en kilómetros

# CONFIGURACIÓN DE DIRECTORIOS Y ARCHIVOS
carpeta_base = "Maps"         # Carpeta principal donde se almacenan todos los mapas
archivo_ciudades = "Cities.txt"  # Archivo de texto con coordenadas y límites de ciudades

# FUNCIONES AUXILIARES
# Calcula el tamaño en grados de un tile basado en su altura en kilómetros
def calcular_tamano_grados(altura_km, latitud_centro):
    # Kilómetros por grado de longitud varían con la latitud (menos en los polos)
    kilometros_por_grado_longitud = kilometros_por_grado_latitud * math.cos(math.radians(latitud_centro))
    
    # Calcular tamaño en grados para latitud y longitud
    tamano_grados_latitud = altura_km / kilometros_por_grado_latitud
    tamano_grados_longitud = altura_km / kilometros_por_grado_longitud
    
    return tamano_grados_latitud, tamano_grados_longitud

# Genera nombre de archivo usando formato: N{lat_norte}_E{lon_este}_S{lat_sur}_O{lon_oeste}.jpg
# Las letras N, E, S, O son fijas y los valores de coordenadas siempre en valor absoluto
def generar_nombre_tile(lat_norte, lon_este, lat_sur, lon_oeste, precision=4):
    # Convertir todas las coordenadas a valores absolutos (positivos)
    # El orden de las letras N, E, S, O es fijo e indica el significado de cada valor
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
    # Esto evita nombres como "N61" que sería ambiguo
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

# Convierte coordenadas de tile web (x, y, zoom) a coordenadas geográficas de límites
def tile_a_limites_geograficos(x_tile, y_tile, zoom, altura_km):
    # Calcular número total de tiles en este nivel de zoom (2^zoom)
    numero_total_tiles = 2.0 ** zoom
    
    # Convertir coordenadas de tile a coordenadas geográficas de esquina noroeste
    # Longitud oeste: fórmula lineal basada en el número de tile horizontal
    longitud_oeste = (x_tile / numero_total_tiles * 360.0) - 180.0
    
    # Latitud norte: fórmula no lineal debido a proyección Mercator
    latitud_norte_radianes = math.atan(math.sinh(math.pi * (1.0 - (2.0 * y_tile / numero_total_tiles))))
    latitud_norte = math.degrees(latitud_norte_radianes)
    
    # Calcular tamaño del tile en grados usando latitud norte como referencia
    tamano_grados_lat, tamano_grados_lon = calcular_tamano_grados(altura_km, latitud_norte)
    
    # Calcular límites sur y este basados en el tamaño del tile
    latitud_sur = latitud_norte - tamano_grados_lat
    longitud_este = longitud_oeste + tamano_grados_lon
    
    return latitud_norte, longitud_este, latitud_sur, longitud_oeste

# Convierte coordenadas geográficas a coordenadas de tile web (x, y, zoom)
def latlon_a_tile(lat, lon, altura_km):
    # Calcular circunferencia terrestre a esta latitud (en kilómetros)
    circunferencia_km = 2.0 * math.pi * radio_tierra_km * math.cos(math.radians(lat))
    
    # Calcular zoom aproximado basado en la altura deseada del tile
    # Fórmula: zoom = log2(circunferencia / altura_deseada)
    zoom_aproximado = int(math.log2(circunferencia_km / altura_km))
    
    # Calcular número total de tiles a este nivel de zoom
    numero_total_tiles = 2.0 ** zoom_aproximado
    
    # Convertir latitud a radianes para cálculos trigonométricos
    latitud_radianes = math.radians(lat)
    
    # Calcular coordenada X del tile (columna horizontal)
    coordenada_x = int(((lon + 180.0) / 360.0) * numero_total_tiles)
    
    # Calcular coordenada Y del tile (fila vertical) usando proyección Mercator inversa
    coordenada_y = int(((1.0 - (math.log(math.tan(latitud_radianes) + (1.0 / math.cos(latitud_radianes))) / math.pi)) / 2.0) * numero_total_tiles)
    
    return coordenada_x, coordenada_y, zoom_aproximado

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
    # Reemplazar espacios por guiones bajos para coincidir con formato del archivo
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
                # Formato esperado: "nombre_ciudad, norte, este, sur, oeste"
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

# Descarga todos los tiles del mundo en la altura configurada
def descargar_mapa_mundial():
    # Crear ruta completa para carpeta de mapas mundiales
    carpeta_mundo = os.path.join(carpeta_base, "World")
    
    # Crear carpeta si no existe (exist_ok evita error si ya existe)
    os.makedirs(carpeta_mundo, exist_ok = True)
    
    # Calcular zoom aproximado para la altura del mundo
    circunferencia_ecuador_km = 2.0 * math.pi * radio_tierra_km
    zoom_mundo = int(math.log2(circunferencia_ecuador_km / altura_mundo_km))
    
    # Mostrar mensaje indicando inicio de descarga
    print("Downloading...")
    
    # Calcular número total de tiles en cada dimensión para este zoom
    numero_tiles_dimension = 2 ** zoom_mundo
    
    # Inicializar contadores para seguimiento del progreso
    total_tiles_descargados = 0
    total_tiles_procesados = 0
    
    # Bucle para recorrer todas las coordenadas X (columnas) de tiles
    for coordenada_x in range(numero_tiles_dimension):
        # Bucle para recorrer todas las coordenadas Y (filas) de tiles
        for coordenada_y in range(numero_tiles_dimension):
            # Calcular límites geográficos de este tile específico
            latitud_norte, longitud_este, latitud_sur, longitud_oeste = tile_a_limites_geograficos(
                coordenada_x, coordenada_y, zoom_mundo, altura_mundo_km
            )
            
            # Generar nombre de archivo basado en los límites calculados
            nombre_archivo_tile = generar_nombre_tile(latitud_norte, longitud_este, latitud_sur, longitud_oeste)
            ruta_completa_archivo = os.path.join(carpeta_mundo, nombre_archivo_tile)
            
            # Intentar descargar el tile desde el servicio web
            if descargar_tile_servicio(coordenada_x, coordenada_y, zoom_mundo, ruta_completa_archivo):
                total_tiles_descargados += 1  # Incrementar contador de éxitos
            
            total_tiles_procesados += 1  # Incrementar contador total procesado
            
            # Pausa breve para no sobrecargar el servidor y evitar bloqueos
            time.sleep(0.05)
    
    # Mostrar resumen final de la operación de descarga
    print(f"Downloaded {total_tiles_descargados} of {total_tiles_procesados} tiles")
    
    # Retornar True si se descargó al menos un tile, False en caso contrario
    return total_tiles_descargados > 0

# Descarga todos los tiles dentro del área de una ciudad
def descargar_ciudad_completa(nombre_ciudad, norte, este, sur, oeste):
    # Crear nombre de carpeta basado en el nombre de la ciudad
    # Capitalizar palabras y reemplazar espacios con guiones bajos
    nombre_carpeta_ciudad = nombre_ciudad.strip().title()
    carpeta_ciudad = os.path.join(carpeta_base, nombre_carpeta_ciudad)
    
    # Crear carpeta de la ciudad si no existe
    os.makedirs(carpeta_ciudad, exist_ok = True)
    
    # Mostrar mensaje indicando inicio de descarga para esta ciudad
    print(f"Downloading...")
    
    # Calcular latitud central para determinar tamaño de tile en grados
    latitud_centro_ciudad = (norte + sur) / 2.0
    
    # Calcular tamaño en grados para tiles de ciudad
    tamano_grados_lat, tamano_grados_lon = calcular_tamano_grados(altura_ciudad_km, latitud_centro_ciudad)
    
    # Calcular rango geográfico de la ciudad en grados
    diferencia_latitud = norte - sur
    diferencia_longitud = este - oeste
    
    # Asegurar que las diferencias sean positivas (norte > sur, este > oeste)
    if diferencia_latitud < 0:
        norte, sur = sur, norte  # Intercambiar valores
        diferencia_latitud = abs(diferencia_latitud)
    
    if diferencia_longitud < 0:
        este, oeste = oeste, este  # Intercambiar valores
        diferencia_longitud = abs(diferencia_longitud)
    
    # Calcular número de tiles necesarios en cada dirección (redondeando hacia arriba)
    tiles_direccion_norte_sur = int(math.ceil(diferencia_latitud / tamano_grados_lat))
    tiles_direccion_este_oeste = int(math.ceil(diferencia_longitud / tamano_grados_lon))
    
    # Inicializar contadores para seguimiento del progreso
    total_tiles_descargados = 0
    total_tiles_procesados = 0
    
    # Bucle para recorrer tiles en dirección norte-sur
    for indice_norte_sur in range(tiles_direccion_norte_sur):
        # Calcular límite norte del tile actual
        latitud_norte_tile = norte - (indice_norte_sur * tamano_grados_lat)
        
        # Calcular límite sur del tile actual
        latitud_sur_tile = latitud_norte_tile - tamano_grados_lat
        
        # Ajustar límite sur si excede el límite sur de la ciudad
        if latitud_sur_tile < sur:
            latitud_sur_tile = sur
        
        # Bucle para recorrer tiles en dirección este-oeste
        for indice_este_oeste in range(tiles_direccion_este_oeste):
            # Calcular límite oeste del tile actual
            longitud_oeste_tile = oeste + (indice_este_oeste * tamano_grados_lon)
            
            # Calcular límite este del tile actual
            longitud_este_tile = longitud_oeste_tile + tamano_grados_lon
            
            # Ajustar límite este si excede el límite este de la ciudad
            if longitud_este_tile > este:
                longitud_este_tile = este
            
            # Generar nombre de archivo basado en límites del tile
            nombre_archivo_tile = generar_nombre_tile(latitud_norte_tile, longitud_este_tile, latitud_sur_tile, longitud_oeste_tile)
            ruta_completa_archivo = os.path.join(carpeta_ciudad, nombre_archivo_tile)
            
            # Calcular coordenadas centrales del tile para la descarga web
            latitud_centro_tile = (latitud_norte_tile + latitud_sur_tile) / 2.0
            longitud_centro_tile = (longitud_este_tile + longitud_oeste_tile) / 2.0
            
            # Obtener coordenadas de tile web para descarga
            coordenada_x_tile, coordenada_y_tile, zoom_ciudad = latlon_a_tile(latitud_centro_tile, longitud_centro_tile, altura_ciudad_km)
            
            # Intentar descargar el tile desde el servicio web
            if descargar_tile_servicio(coordenada_x_tile, coordenada_y_tile, zoom_ciudad, ruta_completa_archivo):
                total_tiles_descargados += 1  # Incrementar contador de éxitos
            
            total_tiles_procesados += 1  # Incrementar contador total procesado
            
            # Pausa breve para no sobrecargar el servidor y evitar bloqueos
            time.sleep(0.05)
    
    # Mostrar resumen final de la operación de descarga para esta ciudad
    print(f"Downloaded {total_tiles_descargados} of {total_tiles_procesados} tiles")
    
    # Retornar True si se descargó al menos un tile, False en caso contrario
    return total_tiles_descargados > 0

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