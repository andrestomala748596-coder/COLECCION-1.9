import json
import re
import unicodedata
from pathlib import Path

# ============================================================
# ORGANIZADOR DEL CATÁLOGO
# - Lee urls.txt sin modificarlo.
# - Agrupa las películas por CATEGORIA.
# - Evita duplicados identificables.
# - Actualiza category_list.json.
# - Elimina archivos de categorías obsoletos.
# - No extrae enlaces de reproducción.
# ============================================================

BASE_DIR = Path(__file__).resolve().parent
INPUT_FILE = BASE_DIR / "urls.txt"
MOVIES_DIR = BASE_DIR / "peliculas"
CATEGORY_LIST_FILE = BASE_DIR / "category_list.json"


def normalizar_categoria(categoria):
    categoria = str(categoria or "GENERAL").strip().upper()
    categoria = unicodedata.normalize("NFKD", categoria)
    categoria = "".join(
        caracter
        for caracter in categoria
        if not unicodedata.combining(caracter)
    )
    categoria = re.sub(r"[^A-Z0-9 _-]", "", categoria)
    categoria = re.sub(r"[\s-]+", "_", categoria).strip("_")
    return categoria or "GENERAL"


def obtener_id(pelicula):
    for campo in ("ID_VIDEO", "ID_OKRU", "TMDB_ID", "ID"):
        valor = pelicula.get(campo)
        if valor not in (None, ""):
            return str(valor).strip()
    return None


def clave_deduplicacion(pelicula):
    identificador = obtener_id(pelicula)

    if identificador:
        return ("ID", identificador)

    titulo = (
        pelicula.get("TITULO")
        or pelicula.get("NOMBRE")
        or pelicula.get("title")
    )

    if titulo:
        titulo = " ".join(str(titulo).casefold().split())
        anio = str(
            pelicula.get("ANIO")
            or pelicula.get("YEAR")
            or ""
        ).strip()
        return ("TITULO", titulo, anio)

    # Sin ID ni título no se puede deduplicar de forma segura.
    return None


def limpiar_datos_para_catalogo(pelicula):
    resultado = dict(pelicula)
    resultado.pop("URLS_DIRECTAS", None)
    resultado.pop("URL_DIRECTA", None)
    return resultado


def leer_entrada():
    if not INPUT_FILE.is_file():
        raise RuntimeError("No se encontró urls.txt.")

    contenido = INPUT_FILE.read_text(
        encoding="utf-8-sig"
    ).strip()

    if not contenido:
        raise RuntimeError(
            "urls.txt está vacío. Se cancela para proteger el catálogo."
        )

    try:
        datos = json.loads(contenido)
    except json.JSONDecodeError as error:
        raise RuntimeError(
            f"JSON inválido en urls.txt, línea {error.lineno}, "
            f"columna {error.colno}: {error.msg}"
        ) from error

    if not isinstance(datos, list):
        raise RuntimeError(
            "urls.txt debe contener una lista JSON de películas."
        )

    if not datos:
        raise RuntimeError(
            "La lista está vacía. Se cancela para proteger el catálogo."
        )

    if any(not isinstance(item, dict) for item in datos):
        raise RuntimeError(
            "Cada registro de urls.txt debe ser un objeto JSON."
        )

    return datos


def guardar_json_atomico(ruta, datos):
    ruta.parent.mkdir(parents=True, exist_ok=True)
    temporal = ruta.with_suffix(ruta.suffix + ".tmp")

    with temporal.open(
        "w",
        encoding="utf-8",
        newline="\n"
    ) as archivo:
        json.dump(
            datos,
            archivo,
            indent=2,
            ensure_ascii=False
        )
        archivo.write("\n")

    temporal.replace(ruta)


def main():
    print("=== ORGANIZADOR DE CATÁLOGO ===")
    print("Fuente: urls.txt")
    print("Extracción de enlaces: desactivada")

    peliculas = leer_entrada()

    agrupadas = {}
    claves_vistas = set()
    duplicados = 0
    sin_clave = 0

    for original in peliculas:
        pelicula = limpiar_datos_para_catalogo(original)

        categoria = normalizar_categoria(
            pelicula.get("CATEGORIA", "GENERAL")
        )
        pelicula["CATEGORIA"] = categoria

        clave = clave_deduplicacion(pelicula)

        if clave is not None:
            if clave in claves_vistas:
                duplicados += 1
                print(
                    f"Duplicado omitido: {clave} "
                    f"(categoría {categoria})"
                )
                continue

            claves_vistas.add(clave)
        else:
            sin_clave += 1

        agrupadas.setdefault(categoria, []).append(pelicula)

    if not agrupadas:
        raise RuntimeError(
            "No se generaron categorías. No se eliminarán archivos."
        )

    # Preparar el catálogo completo antes de retirar categorías antiguas.
    archivos_nuevos = {
        f"{categoria}.json": registros
        for categoria, registros in sorted(agrupadas.items())
    }

    MOVIES_DIR.mkdir(parents=True, exist_ok=True)

    # Escribir los archivos correspondientes a la entrada actual.
    for nombre, registros in archivos_nuevos.items():
        guardar_json_atomico(
            MOVIES_DIR / nombre,
            registros
        )
        print(
            f"Actualizado: peliculas/{nombre} "
            f"({len(registros)} películas)"
        )

    categorias_finales = sorted(agrupadas.keys())

    guardar_json_atomico(
        CATEGORY_LIST_FILE,
        categorias_finales
    )

    # Retirar archivos de categorías antiguas que ya no están en la entrada.
    nombres_vigentes = set(archivos_nuevos)
    eliminados = []

    for ruta in MOVIES_DIR.glob("*.json"):
        if ruta.name in nombres_vigentes:
            continue

        # Solo considerar archivos cuyo nombre representa una categoría
        # normalizada en mayúsculas. No tocar archivos auxiliares arbitrarios.
        if (
            ruta.stem == ruta.stem.upper()
            and normalizar_categoria(ruta.stem) == ruta.stem
        ):
            eliminados.append(ruta)

    for ruta in eliminados:
        ruta.unlink()
        print(f"Categoría obsoleta eliminada: {ruta.name}")

    total = sum(len(registros) for registros in agrupadas.values())

    print("\n=== RESUMEN ===")
    print(f"Películas de entrada: {len(peliculas)}")
    print(f"Películas catalogadas: {total}")
    print(f"Categorías generadas: {len(categorias_finales)}")
    print(f"Duplicados omitidos: {duplicados}")
    print(f"Registros sin identificador deduplicable: {sin_clave}")
    print("urls.txt no fue modificado.")
    print("Proceso terminado.")


if __name__ == "__main__":
    main()
