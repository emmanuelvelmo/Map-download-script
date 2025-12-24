#include <iostream> // Entrada/salida estándar
#include <fstream> // Operaciones con archivos
#include <string> // Manejo de strings
#include <cmath> // Funciones matemáticas (atan, sinh, etc.)
#include <filesystem> // Operaciones con directorios (C++17)
#include <thread> // Para pausas (sleep_for)
#include <chrono> // Para duraciones de tiempo
#include <algorithm> // Para transformaciones de strings
#include <cctype> // Para funciones de caracteres
#include <vector> // Para contenedor vector
#include <sstream> // Para stringstream
#include <stdexcept> // Para excepciones

// URL DEL SERVICIO DE MAPAS SATELITALES
std::string servicio_mapa = "https://services.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}";

// NIVELES DE ZOOM PREDEFINIDOS
int zoom_mundo = 7; // Equivale a x metros de altura
int zoom_ciudad = 18; // Equivale a x metros de altura

// CONFIGURACIÓN DE DIRECTORIOS Y ARCHIVOS
std::string carpeta_base = "Maps"; // Carpeta principal donde se almacenan todos los mapas
std::string archivo_ciudades = "Cities.txt"; // Archivo de texto con coordenadas de ciudades

// Constante PI para cálculos matemáticos
const double PI = 3.14159265358979323846;

// FUNCIONES
// Descarga un tile individual desde el servicio de mapas usando WinHTTP (Windows API)
bool descargar_tile_servicio(int x_tile, int y_tile, int zoom, const std::string& ruta_archivo)
{
    // Construir URL completa sustituyendo parámetros
    std::string url_completa = servicio_mapa;

    // Reemplazar marcadores con valores reales
    size_t pos_z = url_completa.find("{z}");

    if (pos_z != std::string::npos)
    {
        url_completa.replace(pos_z, 3, std::to_string(zoom));
    }

    size_t pos_y = url_completa.find("{y}");

    if (pos_y != std::string::npos)
    {
        url_completa.replace(pos_y, 3, std::to_string(y_tile));
    }

    size_t pos_x = url_completa.find("{x}");

    if (pos_x != std::string::npos)
    {
        url_completa.replace(pos_x, 3, std::to_string(x_tile));
    }

    // En Windows, podemos usar system para descargar con PowerShell
    std::string comando_powershell = "powershell -Command \"try { $response = Invoke-WebRequest -Uri '" +
        url_completa +
        "' -UserAgent 'Mozilla/5.0' -TimeoutSec 30 -UseBasicParsing; " +
        "if ($response.StatusCode -eq 200 -and $response.Content.Length -gt 1000) { " +
        "[System.IO.File]::WriteAllBytes('" + ruta_archivo + "', $response.Content); " +
        "exit 0 } else { exit 1 } } catch { exit 1 }\"";

    // Ejecutar el comando de PowerShell
    int resultado = system(comando_powershell.c_str());

    return (resultado == 0);
}

// Convierte coordenadas geográficas a coordenadas de tile web (x, y, zoom)
std::pair<int, int> latlon_a_tile(double latitud, double longitud, int nivel_zoom)
{
    // Calcular número total de tiles a este nivel de zoom
    double numero_total_tiles = std::pow(2.0, nivel_zoom);

    // Convertir latitud a radianes para cálculos trigonométricos
    double latitud_radianes = latitud * PI / 180.0;

    // Calcular coordenada X del tile (columna horizontal)
    int coordenada_x = static_cast<int>(((longitud + 180.0) / 360.0) * numero_total_tiles);

    // Calcular coordenada Y del tile (fila vertical) usando proyección Mercator inversa
    int coordenada_y = static_cast<int>(((1.0 - (std::log(std::tan(latitud_radianes) + (1.0 / std::cos(latitud_radianes))) / PI)) / 2.0) * numero_total_tiles);

    return { coordenada_x, coordenada_y };
}

// Convierte coordenadas de tile web (x, y, zoom) a coordenadas geográficas de límites
std::tuple<double, double, double, double> tile_a_limites_geograficos(int x_tile, int y_tile, int nivel_zoom)
{
    // Calcular número total de tiles en este nivel de zoom (2^zoom)
    double numero_total_tiles = std::pow(2.0, nivel_zoom);

    // Convertir coordenadas de tile a coordenadas geográficas de esquina noroeste
    // Longitud oeste: fórmula lineal basada en el número de tile horizontal
    double longitud_oeste = (x_tile / numero_total_tiles * 360.0) - 180.0;

    // Latitud norte: fórmula no lineal debido a proyección Mercator
    double latitud_norte_radianes = std::atan(std::sinh(PI * (1.0 - (2.0 * y_tile / numero_total_tiles))));
    double latitud_norte = latitud_norte_radianes * 180.0 / PI;

    // Calcular latitud sur del mismo tile (tile siguiente en Y)
    double latitud_sur_radianes = std::atan(std::sinh(PI * (1.0 - (2.0 * (y_tile + 1) / numero_total_tiles))));
    double latitud_sur = latitud_sur_radianes * 180.0 / PI;

    // Calcular longitud este del mismo tile (tile siguiente en X)
    double longitud_este = ((x_tile + 1) / numero_total_tiles * 360.0) - 180.0;

    return { latitud_norte, longitud_este, latitud_sur, longitud_oeste };
}

// Función auxiliar para formatear números con precisión
std::string formatear_coordenada(double valor, int precision)
{
    std::string texto = std::to_string(valor);

    // Encontrar la posición del punto decimal
    size_t pos_punto = texto.find('.');

    if (pos_punto != std::string::npos)
    {
        // Recortar ceros finales
        texto.erase(texto.find_last_not_of('0') + 1, std::string::npos);

        // Si el punto decimal queda al final, eliminarlo también
        if (texto.back() == '.')
        {
            texto.pop_back();
        }
    }

    // Asegurar que haya al menos un dígito después del punto decimal
    if (texto.find('.') == std::string::npos)
    {
        texto += ".0";
    }

    return texto;
}

// Genera nombre de archivo usando formato: N{lat_norte}_E{lon_este}_S{lat_sur}_O{lon_oeste}.jpg
std::string generar_nombre_tile(double lat_norte, double lon_este, double lat_sur, double lon_oeste, int precision = 4)
{
    // Convertir todas las coordenadas a valores absolutos (positivos)
    double lat_norte_abs = std::abs(lat_norte);
    double lon_este_abs = std::abs(lon_este);
    double lat_sur_abs = std::abs(lat_sur);
    double lon_oeste_abs = std::abs(lon_oeste);

    // Formatear cada coordenada
    std::string norte_str = formatear_coordenada(lat_norte_abs, precision);
    std::string este_str = formatear_coordenada(lon_este_abs, precision);
    std::string sur_str = formatear_coordenada(lat_sur_abs, precision);
    std::string oeste_str = formatear_coordenada(lon_oeste_abs, precision);

    // Construir nombre final con orden fijo: N, E, S, O
    std::string nombre_final = "N" + norte_str + "_E" + este_str + "_S" + sur_str + "_O" + oeste_str + ".jpg";

    return nombre_final;
}

// Función auxiliar para convertir string a minúsculas
std::string a_minusculas(const std::string& texto)
{
    std::string resultado = texto;
    std::transform(resultado.begin(), resultado.end(), resultado.begin(),
        [](unsigned char c) { return std::tolower(c); });

    return resultado;
}

// Función auxiliar para reemplazar espacios por guiones bajos
std::string reemplazar_espacios(const std::string& texto)
{
    std::string resultado = texto;

    for (char& c : resultado)
    {
        if (c == ' ')
        {
            c = '_';
        }
    }

    return resultado;
}

// Busca información de una ciudad en el archivo de texto de ciudades
std::tuple<double, double, double, double> buscar_informacion_ciudad(const std::string& nombre_ciudad, const std::string& ruta_archivo)
{
    // Normalizar nombre de ciudad para comparación insensible a mayúsculas/minúsculas
    std::string nombre_normalizado = a_minusculas(nombre_ciudad);
    nombre_normalizado = reemplazar_espacios(nombre_normalizado);

    std::ifstream archivo(ruta_archivo);

    if (!archivo.is_open())
    {
        return { 0.0, 0.0, 0.0, 0.0 }; // Indica error
    }

    std::string linea_actual;

    while (std::getline(archivo, linea_actual))
    {
        // Eliminar espacios en blanco al inicio y final de la línea
        size_t inicio = linea_actual.find_first_not_of(" \t");

        if (inicio == std::string::npos)
        {
            continue; // Línea vacía
        }

        size_t fin = linea_actual.find_last_not_of(" \t");
        std::string linea_limpia = linea_actual.substr(inicio, fin - inicio + 1);

        if (linea_limpia.empty())
        {
            continue;
        }

        // Buscar comas para dividir campos
        std::vector<std::string> campos_linea;
        size_t inicio_campo = 0;
        size_t pos_coma;

        while ((pos_coma = linea_limpia.find(',', inicio_campo)) != std::string::npos)
        {
            campos_linea.push_back(linea_limpia.substr(inicio_campo, pos_coma - inicio_campo));
            inicio_campo = pos_coma + 1;
        }

        // Agregar el último campo
        campos_linea.push_back(linea_limpia.substr(inicio_campo));

        // Verificar que la línea tenga exactamente 5 campos
        if (campos_linea.size() == 5)
        {
            // Normalizar nombre de ciudad del archivo
            std::string nombre_archivo = a_minusculas(campos_linea[0]);
            nombre_archivo = reemplazar_espacios(nombre_archivo);

            if (nombre_archivo == nombre_normalizado)
            {
                try
                {
                    double coordenada_norte = std::stod(campos_linea[1]);
                    double coordenada_este = std::stod(campos_linea[2]);
                    double coordenada_sur = std::stod(campos_linea[3]);
                    double coordenada_oeste = std::stod(campos_linea[4]);

                    archivo.close();

                    return { coordenada_norte, coordenada_este, coordenada_sur, coordenada_oeste };
                }
                catch (...)
                {
                    // Error en conversión numérica: continuar con siguiente línea
                    continue;
                }
            }
        }
    }

    archivo.close();

    return { 0.0, 0.0, 0.0, 0.0 }; // Indica ciudad no encontrada
}

// Verifica si el archivo de ciudades existe en el directorio actual
bool verificar_existencia_archivo_ciudades()
{
    return std::filesystem::exists(archivo_ciudades);
}

// Descarga todos los tiles del mundo en el nivel de zoom configurado
bool descargar_mapa_mundial()
{
    // Crear ruta completa para carpeta de mapas mundiales
    std::filesystem::path carpeta_mundo = std::filesystem::path(carpeta_base) / "World";

    // Crear carpeta si no existe
    std::filesystem::create_directories(carpeta_mundo);

    // Mostrar mensaje indicando inicio de descarga
    std::cout << "Downloading..." << std::endl;

    // Calcular número total de tiles en cada dimensión para este zoom
    int numero_tiles_dimension = std::pow(2, zoom_mundo);

    // Bucle para recorrer todas las coordenadas X (columnas) de tiles
    for (int coordenada_x = 0; coordenada_x < numero_tiles_dimension; ++coordenada_x)
    {
        // Bucle para recorrer todas las coordenadas Y (filas) de tiles
        for (int coordenada_y = 0; coordenada_y < numero_tiles_dimension; ++coordenada_y)
        {
            // Calcular límites geográficos de este tile específico
            auto [latitud_norte, longitud_este, latitud_sur, longitud_oeste] =
                tile_a_limites_geograficos(coordenada_x, coordenada_y, zoom_mundo);

            // Generar nombre de archivo basado en los límites calculados
            std::string nombre_archivo_tile = generar_nombre_tile(latitud_norte, longitud_este, latitud_sur, longitud_oeste);
            std::filesystem::path ruta_completa_archivo = carpeta_mundo / nombre_archivo_tile;

            // Verificar si el archivo ya existe antes de descargar
            if (!std::filesystem::exists(ruta_completa_archivo))
            {
                // Intentar descargar el tile desde el servicio web
                bool descarga_exitosa = descargar_tile_servicio(coordenada_x, coordenada_y, zoom_mundo, ruta_completa_archivo.string());

                if (!descarga_exitosa)
                {
                    std::cout << "Warning: Failed to download tile at (" << coordenada_x << ", " << coordenada_y << ")" << std::endl;
                }
            }

            // Pausa breve para no sobrecargar el servidor y evitar bloqueos
            std::this_thread::sleep_for(std::chrono::milliseconds(200));
        }
    }

    // Salto de línea
    std::cout << std::endl;

    return true;
}

// Descarga todos los tiles dentro del área de una ciudad sin duplicados
bool descargar_ciudad_completa(const std::string& nombre_ciudad, double norte, double este, double sur, double oeste)
{
    // Crear nombre de carpeta basado en el nombre de la ciudad
    std::string nombre_carpeta_ciudad = nombre_ciudad;

    // Convertir primera letra a mayúscula y resto a minúscula (simplificado)
    if (!nombre_carpeta_ciudad.empty())
    {
        nombre_carpeta_ciudad[0] = std::toupper(nombre_carpeta_ciudad[0]);

        for (size_t i = 1; i < nombre_carpeta_ciudad.size(); ++i)
        {
            nombre_carpeta_ciudad[i] = std::tolower(nombre_carpeta_ciudad[i]);
        }
    }

    std::filesystem::path carpeta_ciudad = std::filesystem::path(carpeta_base) / nombre_carpeta_ciudad;

    // Crear carpeta de la ciudad si no existe
    std::filesystem::create_directories(carpeta_ciudad);

    // Mostrar mensaje indicando inicio de descarga para esta ciudad
    std::cout << "Downloading..." << std::endl;

    // Convertir coordenadas límite a tiles en el nivel de zoom de ciudad
    // Esquina noroeste (norte, oeste) para obtener tile mínimo
    auto [x_min, y_min] = latlon_a_tile(norte, oeste, zoom_ciudad);

    // Esquina sureste (sur, este) para obtener tile máximo
    auto [x_max, y_max] = latlon_a_tile(sur, este, zoom_ciudad);

    // Asegurar que x_min < x_max y y_min < y_max
    if (x_min > x_max)
    {
        std::swap(x_min, x_max);
    }

    if (y_min > y_max)
    {
        std::swap(y_min, y_max);
    }

    // Bucle para recorrer todos los tiles en el rango calculado
    for (int x_tile = x_min; x_tile <= x_max; ++x_tile)
    {
        for (int y_tile = y_min; y_tile <= y_max; ++y_tile)
        {
            // Calcular límites geográficos de este tile específico
            auto [latitud_norte, longitud_este, latitud_sur, longitud_oeste] =
                tile_a_limites_geograficos(x_tile, y_tile, zoom_ciudad);

            // Generar nombre de archivo basado en los límites calculados
            std::string nombre_archivo_tile = generar_nombre_tile(latitud_norte, longitud_este, latitud_sur, longitud_oeste);
            std::filesystem::path ruta_completa_archivo = carpeta_ciudad / nombre_archivo_tile;

            // Verificar si el archivo ya existe antes de descargar
            if (!std::filesystem::exists(ruta_completa_archivo))
            {
                // Intentar descargar el tile desde el servicio web
                bool descarga_exitosa = descargar_tile_servicio(x_tile, y_tile, zoom_ciudad, ruta_completa_archivo.string());

                if (!descarga_exitosa)
                {
                    std::cout << "Warning: Failed to download tile at (" << x_tile << ", " << y_tile << ")" << std::endl;
                }
            }

            // Pausa breve para no sobrecargar el servidor y evitar bloqueos
            std::this_thread::sleep_for(std::chrono::milliseconds(50));
        }
    }

    // Salto de línea
    std::cout << std::endl;

    return true;
}

// PUNTO DE INICIO DEL PROGRAMA
int main()
{
    // Crear carpeta base para mapas si no existe
    std::filesystem::create_directories(carpeta_base);

    // Mostrar instrucción inicial para usuario
    std::cout << "Enter 'world' to download world map" << std::endl;
    std::cout << std::endl;

    // BUCLE PRINCIPAL DEL PROGRAMA
    while (true)
    {
        // Verificar existencia del archivo de ciudades antes de proceder
        if (!verificar_existencia_archivo_ciudades())
        {
            std::cout << "Cities.txt not found" << std::endl;
            std::cout << "Place file in script directory" << std::endl;

            std::cin.get(); // Pausar para que usuario coloque el archivo

            continue; // Volver al inicio del bucle principal
        }

        // BUCLE INTERNO PARA SOLICITUD DE CIUDAD
        while (true)
        {
            // Solicitar nombre de ciudad o comando al usuario
            std::cout << "Enter city name: ";
            std::string entrada_usuario;

            std::getline(std::cin, entrada_usuario);

            // Eliminar espacios al inicio y final
            size_t inicio = entrada_usuario.find_first_not_of(" \t");

            if (inicio == std::string::npos)
            {
                std::cout << std::endl;

                continue; // Entrada vacía
            }

            size_t fin = entrada_usuario.find_last_not_of(" \t");
            entrada_usuario = entrada_usuario.substr(inicio, fin - inicio + 1);

            // CASO 1: Usuario solicita mapa mundial completo
            if (a_minusculas(entrada_usuario) == "world")
            {
                if (descargar_mapa_mundial())
                {
                    break; // Salir del bucle interno, volver al principal
                }
                else
                {
                    std::cout << "Download failed" << std::endl;
                    std::cout << std::endl;

                    continue; // Reintentar en el bucle interno
                }
            }

            // CASO 2: Usuario solicita ciudad específica
            auto [coordenada_norte, coordenada_este, coordenada_sur, coordenada_oeste] =
                buscar_informacion_ciudad(entrada_usuario, archivo_ciudades);

            // Verificar si se encontró la ciudad (valores no cero)
            if (coordenada_norte == 0.0 && coordenada_este == 0.0 &&
                coordenada_sur == 0.0 && coordenada_oeste == 0.0)
            {
                std::cout << "City not available" << std::endl;
                std::cout << std::endl;

                continue; // Volver a solicitar ciudad en bucle interno
            }

            // Intentar descargar ciudad completa con todos sus tiles
            if (descargar_ciudad_completa(entrada_usuario, coordenada_norte, coordenada_este, coordenada_sur, coordenada_oeste))
            {
                break; // Salir del bucle interno, volver al principal
            }
            else
            {
                std::cout << "Download failed" << std::endl;
                std::cout << std::endl;

                continue; // Reintentar en el bucle interno
            }
        }
    }

    return 0;
}