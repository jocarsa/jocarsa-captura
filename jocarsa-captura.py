#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import datetime
import os
import re
import signal
import subprocess
import sys
import threading
import time
from pathlib import Path

NOMBRE_APP = "jocarsa | captura"

CARPETA_SALIDA = Path.home() / "Videos"
FPS = 30
DISPLAY = os.environ.get("DISPLAY", ":1")
FUENTE_AUDIO = "default"
ARCHIVO_LISTAS = "listas.txt"

PREVISUALIZACION = True
INTERVALO_PREVISUALIZACION_MS = 1000

INTERVALO_RATON_SEGUNDOS = 1.0

AJUSTE_X_PREVIEW = 32
AJUSTE_Y_PREVIEW = 32
AJUSTE_ANCHO_PREVIEW = -64
SEPARACION_PREVIEW = 0


def ejecutar(comando):
    return subprocess.run(comando, text=True, capture_output=True)


def limpiar():
    os.system("clear")


def color(texto, codigo):
    return f"\033[{codigo}m{texto}\033[0m"


def slugificar(texto):
    texto = texto.strip().lower()
    texto = texto.replace("á", "a").replace("é", "e").replace("í", "i")
    texto = texto.replace("ó", "o").replace("ú", "u").replace("ñ", "n")
    texto = re.sub(r"[^a-z0-9]+", "-", texto)
    texto = texto.strip("-")
    return texto or "sin-titulo"


def comprobar_dependencias():
    for programa in ["ffmpeg", "xrandr", "xdotool", "xwininfo"]:
        if ejecutar(["which", programa]).returncode != 0:
            print(f"Falta {programa}")
            print("Instala dependencias con:")
            print(
                "sudo apt install ffmpeg x11-xserver-utils xdotool x11-utils "
                "python3-tk python3-pil python3-pil.imagetk"
            )
            sys.exit(1)

    try:
        import pynput  # noqa
    except Exception:
        print("Falta el módulo Python pynput.")
        print("Instálalo con:")
        print("python3 -m pip install pynput")
        sys.exit(1)


def obtener_pantallas():
    resultado = ejecutar(["xrandr", "--listmonitors"])
    pantallas = []

    for linea in resultado.stdout.splitlines():
        linea = linea.strip()

        m = re.match(
            r"^(\d+):\s+([+*]*)(\S+)\s+(\d+)/\d+x(\d+)/\d+\+(-?\d+)\+(-?\d+)\s+(.+)$",
            linea
        )

        if m:
            pantallas.append({
                "numero": len(pantallas) + 1,
                "marcas": m.group(2),
                "nombre": m.group(3),
                "ancho": int(m.group(4)),
                "alto": int(m.group(5)),
                "x": int(m.group(6)),
                "y": int(m.group(7)),
            })

    return pantallas


def seleccionar_pantalla(pantallas):
    limpiar()
    print(color("jocarsa | captura", "1;36"))
    print(color("selección de pantalla", "2;37"))
    print()

    for p in pantallas:
        principal = " principal" if "*" in p["marcas"] else ""
        print(
            f"{p['numero']}. {p['nombre']} "
            f"{p['ancho']}x{p['alto']} "
            f"+{p['x']}+{p['y']}{principal}"
        )

    print()
    entrada = input("Selecciona pantalla para grabar [1]: ").strip() or "1"

    try:
        numero = int(entrada)
    except ValueError:
        print("Selección no válida.")
        sys.exit(1)

    for p in pantallas:
        if p["numero"] == numero:
            return p

    print("Selección no válida.")
    sys.exit(1)


def leer_listas():
    ruta = Path(__file__).resolve().parent / ARCHIVO_LISTAS

    if not ruta.exists():
        return []

    return [
        linea.strip()
        for linea in ruta.read_text(encoding="utf-8").splitlines()
        if linea.strip()
    ]


def seleccionar_lista(listas):
    if not listas:
        return None

    limpiar()
    print(color("jocarsa | captura", "1;36"))
    print(color("selección de lista", "2;37"))
    print()

    for i, linea in enumerate(listas, start=1):
        print(f"{i}. {linea}")

    print()
    print("Enter = sin lista")
    entrada = input("Selecciona lista para esta grabación: ").strip()

    if entrada == "":
        return None

    try:
        numero = int(entrada)
    except ValueError:
        print("Selección no válida.")
        sys.exit(1)

    if 1 <= numero <= len(listas):
        return listas[numero - 1]

    print("Selección no válida.")
    sys.exit(1)


def formatear_tiempo(segundos):
    segundos = int(segundos)
    h = segundos // 3600
    m = (segundos % 3600) // 60
    s = segundos % 60
    return f"{h:02d}:{m:02d}:{s:02d}"


def tamano_archivo(ruta):
    try:
        mb = ruta.stat().st_size / 1024 / 1024
    except FileNotFoundError:
        return "0 MB"

    if mb < 1024:
        return f"{mb:.1f} MB"

    return f"{mb / 1024:.2f} GB"


def obtener_ventana_terminal():
    if "WINDOWID" in os.environ:
        return os.environ["WINDOWID"]

    resultado = ejecutar(["xdotool", "getactivewindow"])

    if resultado.returncode == 0 and resultado.stdout.strip():
        return resultado.stdout.strip()

    return None


def obtener_geometria_ventana(window_id):
    resultado = ejecutar(["xwininfo", "-id", str(window_id)])

    if resultado.returncode != 0:
        return None

    datos = {}

    patrones = {
        "x": r"Absolute upper-left X:\s+(-?\d+)",
        "y": r"Absolute upper-left Y:\s+(-?\d+)",
        "ancho": r"Width:\s+(\d+)",
        "alto": r"Height:\s+(\d+)",
    }

    for clave, patron in patrones.items():
        m = re.search(patron, resultado.stdout)
        if m:
            datos[clave] = int(m.group(1))

    if not all(k in datos for k in ["x", "y", "ancho", "alto"]):
        return None

    return datos


def obtener_posicion_raton():
    resultado = ejecutar(["xdotool", "getmouselocation", "--shell"])

    if resultado.returncode != 0:
        return None

    datos = {}

    for linea in resultado.stdout.splitlines():
        if "=" in linea:
            clave, valor = linea.split("=", 1)
            datos[clave.strip()] = valor.strip()

    try:
        return int(datos["X"]), int(datos["Y"])
    except Exception:
        return None


def nombre_boton_raton(button):
    texto = str(button)

    if "left" in texto:
        return "left"
    if "right" in texto:
        return "right"
    if "middle" in texto:
        return "middle"

    return texto.replace("Button.", "")


def nombre_tecla(key):
    try:
        if hasattr(key, "char") and key.char is not None:
            return key.char
    except Exception:
        pass

    texto = str(key)

    if texto.startswith("Key."):
        return texto.replace("Key.", "")

    return texto


def escribir_csv_seguro(lock, fichero, linea):
    with lock:
        fichero.write(linea)
        fichero.flush()


def iniciar_registro_raton(archivo_csv, inicio, evento_parada):
    def hilo():
        from pynput import mouse

        lock = threading.Lock()

        with archivo_csv.open("w", encoding="utf-8") as f:
            f.write("t,event,x,y,button\n")
            f.flush()

            def t():
                return time.time() - inicio

            def on_click(x, y, button, pressed):
                evento = "down" if pressed else "up"
                boton = nombre_boton_raton(button)
                escribir_csv_seguro(
                    lock,
                    f,
                    f"{t():.3f},{evento},{int(x)},{int(y)},{boton}\n"
                )

            listener = mouse.Listener(on_click=on_click)
            listener.start()

            ultimo_segundo = -1

            while not evento_parada.is_set():
                segundos = int(time.time() - inicio)

                if segundos != ultimo_segundo:
                    posicion = obtener_posicion_raton()

                    if posicion:
                        x, y = posicion
                        escribir_csv_seguro(
                            lock,
                            f,
                            f"{time.time() - inicio:.3f},move,{x},{y},\n"
                        )

                    ultimo_segundo = segundos

                time.sleep(0.1)

            listener.stop()

    threading.Thread(target=hilo, daemon=True).start()


def iniciar_registro_teclado(archivo_csv, inicio, evento_parada):
    def hilo():
        from pynput import keyboard

        lock = threading.Lock()

        with archivo_csv.open("w", encoding="utf-8") as f:
            f.write("t,event,key\n")
            f.flush()

            def t():
                return time.time() - inicio

            def on_press(key):
                tecla = nombre_tecla(key)
                escribir_csv_seguro(lock, f, f"{t():.3f},down,{tecla}\n")

            def on_release(key):
                tecla = nombre_tecla(key)
                escribir_csv_seguro(lock, f, f"{t():.3f},up,{tecla}\n")

            listener = keyboard.Listener(
                on_press=on_press,
                on_release=on_release
            )
            listener.start()

            while not evento_parada.is_set():
                time.sleep(0.1)

            listener.stop()

    threading.Thread(target=hilo, daemon=True).start()


def iniciar_previsualizacion(pantalla, evento_parada):
    def hilo():
        try:
            import tkinter as tk
            from PIL import ImageGrab, ImageTk
        except Exception:
            return

        ventana_terminal = obtener_ventana_terminal()

        raiz = tk.Tk()
        raiz.title("jocarsa | captura - preview")
        raiz.overrideredirect(True)
        raiz.attributes("-topmost", True)
        raiz.resizable(False, False)

        etiqueta = tk.Label(raiz, bg="black", bd=0, highlightthickness=0)
        etiqueta.pack(fill="both", expand=True)

        bbox = (
            pantalla["x"],
            pantalla["y"],
            pantalla["x"] + pantalla["ancho"],
            pantalla["y"] + pantalla["alto"],
        )

        def actualizar():
            if evento_parada.is_set():
                try:
                    raiz.destroy()
                except Exception:
                    pass
                return

            geometria = obtener_geometria_ventana(ventana_terminal) if ventana_terminal else None

            if geometria:
                ancho_preview = geometria["ancho"] + AJUSTE_ANCHO_PREVIEW
                alto_preview = int(ancho_preview * pantalla["alto"] / pantalla["ancho"])

                x_preview = geometria["x"] + AJUSTE_X_PREVIEW
                y_preview = geometria["y"] - alto_preview - SEPARACION_PREVIEW + AJUSTE_Y_PREVIEW

                if y_preview < 0:
                    y_preview = geometria["y"] + geometria["alto"] + SEPARACION_PREVIEW + AJUSTE_Y_PREVIEW
            else:
                ancho_preview = 800
                alto_preview = int(ancho_preview * pantalla["alto"] / pantalla["ancho"])
                x_preview = 40
                y_preview = 40

            try:
                raiz.geometry(f"{ancho_preview}x{alto_preview}+{x_preview}+{y_preview}")

                imagen = ImageGrab.grab(bbox=bbox)
                imagen = imagen.resize((ancho_preview, alto_preview))
                foto = ImageTk.PhotoImage(imagen)

                etiqueta.configure(image=foto)
                etiqueta.image = foto

            except Exception:
                pass

            raiz.after(INTERVALO_PREVISUALIZACION_MS, actualizar)

        actualizar()
        raiz.mainloop()

    threading.Thread(target=hilo, daemon=True).start()


def pintar_estado(inicio, pantalla, archivo, lista):
    tiempo = formatear_tiempo(time.time() - inicio)
    tamano = tamano_archivo(archivo)

    etiqueta = f"  {color(lista, '1;35')}" if lista else ""

    texto = (
        f"{color('jocarsa | captura', '1;36')}  "
        f"{color(tiempo, '1;33')}  "
        f"{pantalla['nombre']}  "
        f"{color('REC', '1;31')}  "
        f"{color('micrófono', '1;32')}  "
        f"{color('ratón', '1;34')}  "
        f"{color('teclado', '1;35')}  "
        f"{color(tamano, '2;37')}"
        f"{etiqueta}"
    )

    try:
        ancho = os.get_terminal_size().columns
    except OSError:
        ancho = 120

    print("\r" + texto[:ancho - 1].ljust(ancho - 1), end="", flush=True)


def main():
    comprobar_dependencias()

    listas = leer_listas()
    lista = seleccionar_lista(listas)

    pantallas = obtener_pantallas()

    if not pantallas:
        print("No se han detectado pantallas.")
        sys.exit(1)

    pantalla = seleccionar_pantalla(pantallas)

    resolucion = f"{pantalla['ancho']}x{pantalla['alto']}"
    entrada_video = f"{DISPLAY}+{pantalla['x']},{pantalla['y']}"

    CARPETA_SALIDA.mkdir(parents=True, exist_ok=True)

    marca = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")

    if lista:
        nombre_archivo = f"{marca}-{slugificar(lista)}.mp4"
    else:
        nombre_archivo = f"jocarsa-captura_{marca}.mp4"

    archivo = CARPETA_SALIDA / nombre_archivo
    archivo_raton = archivo.with_suffix(".mouse.csv")
    archivo_teclado = archivo.with_suffix(".keys.csv")

    comando = [
        "ffmpeg",
        "-y",
        "-hide_banner",
        "-loglevel", "error",
        "-nostats",

        "-f", "x11grab",
        "-video_size", resolucion,
        "-framerate", str(FPS),
        "-i", entrada_video,

        "-f", "pulse",
        "-i", FUENTE_AUDIO,

        "-c:v", "libx264",
        "-preset", "veryfast",
        "-crf", "23",

        "-c:a", "aac",
        "-b:a", "128k",

        "-pix_fmt", "yuv420p",
        "-movflags", "+faststart",

        str(archivo)
    ]

    limpiar()
    print(color("jocarsa | captura", "1;36"))
    print()
    print(f"Pantalla: {pantalla['nombre']} {resolucion}")
    print(f"Entrada:   {entrada_video}")

    if lista:
        print(f"Lista:     {lista}")

    print(f"Vídeo:     {archivo}")
    print(f"Ratón:     {archivo_raton}")
    print(f"Teclado:   {archivo_teclado}")
    print()
    print("Grabando. Pulsa Ctrl+C para detener.")
    print()

    evento_parada = threading.Event()

    if PREVISUALIZACION:
        iniciar_previsualizacion(pantalla, evento_parada)

    proceso = subprocess.Popen(
        comando,
        stdin=subprocess.PIPE,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        text=True
    )

    inicio = time.time()

    iniciar_registro_raton(archivo_raton, inicio, evento_parada)
    iniciar_registro_teclado(archivo_teclado, inicio, evento_parada)

    try:
        while proceso.poll() is None:
            pintar_estado(inicio, pantalla, archivo, lista)
            time.sleep(0.25)

    except KeyboardInterrupt:
        print()
        print(color("Deteniendo grabación correctamente...", "1;33"))
        evento_parada.set()

        try:
            proceso.stdin.write("q\n")
            proceso.stdin.flush()
            proceso.wait(timeout=10)
        except Exception:
            try:
                proceso.send_signal(signal.SIGINT)
                proceso.wait(timeout=10)
            except Exception:
                proceso.kill()

    evento_parada.set()
    time.sleep(0.5)

    print()
    print()
    print(color("Grabación guardada:", "1;32"))
    print(archivo)

    print(color("Ratón guardado:", "1;32"))
    print(archivo_raton)

    print(color("Teclado guardado:", "1;32"))
    print(archivo_teclado)


if __name__ == "__main__":
    main()
