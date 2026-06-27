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

import tkinter as tk
from tkinter import messagebox

import ttkbootstrap as ttk
from ttkbootstrap.constants import *

NOMBRE_APP = "jocarsa | captura"

CARPETA_SALIDA = Path.home() / "Videos"
FPS = 30
DISPLAY = os.environ.get("DISPLAY", ":1")
FUENTE_AUDIO = "default"
ARCHIVO_LISTAS = "listas.txt"
LOG_BOTONES = "registro_pulsaciones.txt"

INTERVALO_PREVISUALIZACION_MS = 1000


def ejecutar(comando):
    return subprocess.run(comando, text=True, capture_output=True)


def ahora_txt():
    return datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def slugificar(texto):
    texto = texto.strip().lower()
    texto = texto.replace("á", "a").replace("é", "e").replace("í", "i")
    texto = texto.replace("ó", "o").replace("ú", "u").replace("ñ", "n")
    texto = re.sub(r"[^a-z0-9]+", "-", texto)
    texto = texto.strip("-")
    return texto or "sin-titulo"


def comprobar_dependencias():
    for programa in ["ffmpeg", "xrandr", "xdotool"]:
        if ejecutar(["which", programa]).returncode != 0:
            messagebox.showerror(
                NOMBRE_APP,
                "Falta " + programa + "\n\n"
                "sudo apt install ffmpeg x11-xserver-utils xdotool "
                "python3-tk python3-pil python3-pil.imagetk"
            )
            sys.exit(1)

    try:
        import pynput  # noqa
        import PIL  # noqa
    except Exception:
        messagebox.showerror(
            NOMBRE_APP,
            "Faltan módulos Python.\n\npython3 -m pip install pynput pillow ttkbootstrap"
        )
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


def leer_listas():
    ruta = Path(__file__).resolve().parent / ARCHIVO_LISTAS

    if not ruta.exists():
        ruta.write_text(
            "TAME2627-DAM1-Programación\n"
            "TAME2627-DAM1-Bases de datos\n"
            "TAME2627-DAM1-Lenguajes de marcas y sistemas de gestión de información\n",
            encoding="utf-8"
        )

    return [
        linea.strip()
        for linea in ruta.read_text(encoding="utf-8").splitlines()
        if linea.strip()
    ]


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


class RelojGrabacion:
    def __init__(self):
        self.inicio_real = time.time()
        self.pausa_inicio = None
        self.total_pausado = 0.0
        self.pausado = False
        self.lock = threading.Lock()

    def pausar(self):
        with self.lock:
            if not self.pausado:
                self.pausado = True
                self.pausa_inicio = time.time()

    def reanudar(self):
        with self.lock:
            if self.pausado:
                self.total_pausado += time.time() - self.pausa_inicio
                self.pausa_inicio = None
                self.pausado = False

    def segundos(self):
        with self.lock:
            ahora = time.time()
            if self.pausado:
                ahora = self.pausa_inicio
            return ahora - self.inicio_real - self.total_pausado

    def esta_pausado(self):
        with self.lock:
            return self.pausado


def escribir_csv_seguro(lock, fichero, linea):
    with lock:
        fichero.write(linea)
        fichero.flush()


def iniciar_registro_raton(archivo_csv, reloj, evento_parada):
    def hilo():
        from pynput import mouse

        lock = threading.Lock()

        with archivo_csv.open("w", encoding="utf-8") as f:
            f.write("t,event,x,y,button\n")
            f.flush()

            def on_click(x, y, button, pressed):
                if reloj.esta_pausado():
                    return

                evento = "down" if pressed else "up"
                boton = nombre_boton_raton(button)

                escribir_csv_seguro(
                    lock,
                    f,
                    f"{reloj.segundos():.3f},{evento},{int(x)},{int(y)},{boton}\n"
                )

            listener = mouse.Listener(on_click=on_click)
            listener.start()

            ultimo_segundo = -1

            while not evento_parada.is_set():
                if not reloj.esta_pausado():
                    segundos = int(reloj.segundos())

                    if segundos != ultimo_segundo:
                        posicion = obtener_posicion_raton()

                        if posicion:
                            x, y = posicion
                            escribir_csv_seguro(
                                lock,
                                f,
                                f"{reloj.segundos():.3f},move,{x},{y},\n"
                            )

                        ultimo_segundo = segundos

                time.sleep(0.1)

            listener.stop()

    threading.Thread(target=hilo, daemon=True).start()


def iniciar_registro_teclado(archivo_csv, reloj, evento_parada):
    def hilo():
        from pynput import keyboard

        lock = threading.Lock()

        with archivo_csv.open("w", encoding="utf-8") as f:
            f.write("t,event,key\n")
            f.flush()

            def on_press(key):
                if reloj.esta_pausado():
                    return

                tecla = nombre_tecla(key)
                escribir_csv_seguro(lock, f, f"{reloj.segundos():.3f},down,{tecla}\n")

            def on_release(key):
                if reloj.esta_pausado():
                    return

                tecla = nombre_tecla(key)
                escribir_csv_seguro(lock, f, f"{reloj.segundos():.3f},up,{tecla}\n")

            listener = keyboard.Listener(on_press=on_press, on_release=on_release)
            listener.start()

            while not evento_parada.is_set():
                time.sleep(0.1)

            listener.stop()

    threading.Thread(target=hilo, daemon=True).start()


class Grabacion:
    def __init__(self, pantalla, lista):
        self.pantalla = pantalla
        self.lista = lista
        self.proceso = None
        self.evento_parada = threading.Event()
        self.reloj = RelojGrabacion()
        self.pausado = False

    def iniciar(self):
        CARPETA_SALIDA.mkdir(parents=True, exist_ok=True)

        marca = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        nombre_archivo = f"{marca}-{slugificar(self.lista)}.mp4"

        self.archivo = CARPETA_SALIDA / nombre_archivo
        self.archivo_raton = self.archivo.with_suffix(".mouse.csv")
        self.archivo_teclado = self.archivo.with_suffix(".keys.csv")

        resolucion = f"{self.pantalla['ancho']}x{self.pantalla['alto']}"
        entrada_video = f"{DISPLAY}+{self.pantalla['x']},{self.pantalla['y']}"

        comando = [
            "ffmpeg", "-y",
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

            str(self.archivo)
        ]

        self.proceso = subprocess.Popen(
            comando,
            stdin=subprocess.PIPE,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            text=True
        )

        iniciar_registro_raton(self.archivo_raton, self.reloj, self.evento_parada)
        iniciar_registro_teclado(self.archivo_teclado, self.reloj, self.evento_parada)

    def pausar(self):
        if not self.proceso or self.proceso.poll() is not None or self.pausado:
            return

        self.proceso.send_signal(signal.SIGSTOP)
        self.reloj.pausar()
        self.pausado = True

    def reanudar(self):
        if not self.proceso or self.proceso.poll() is not None or not self.pausado:
            return

        self.reloj.reanudar()
        self.proceso.send_signal(signal.SIGCONT)
        self.pausado = False

    def alternar_pausa(self):
        if self.pausado:
            self.reanudar()
        else:
            self.pausar()

    def segundos(self):
        return self.reloj.segundos()

    def esta_grabando(self):
        return self.proceso is not None and self.proceso.poll() is None and not self.pausado

    def detener(self):
        if not self.proceso:
            return

        if self.pausado:
            self.reanudar()

        self.evento_parada.set()

        if self.proceso.poll() is None:
            try:
                self.proceso.stdin.write("q\n")
                self.proceso.stdin.flush()
                self.proceso.wait(timeout=10)
            except Exception:
                try:
                    self.proceso.send_signal(signal.SIGINT)
                    self.proceso.wait(timeout=10)
                except Exception:
                    self.proceso.kill()

        time.sleep(0.3)


class App:
    def __init__(self, root):
        self.root = root
        self.root.title(NOMBRE_APP)
        self.root.geometry("620x620")

        self.cambiando_lista = False

        self.pantallas = obtener_pantallas()
        self.listas = leer_listas()

        if not self.pantallas:
            messagebox.showerror(NOMBRE_APP, "No se han detectado pantallas.")
            self.root.destroy()
            return

        self.pantalla = self.pantallas[0]
        self.nombre_activo = None
        self.inicio_activo = None
        self.grabacion = None

        self.crear_interfaz()
        self.root.after(300, self.actualizar_preview_integrado)
        self.root.protocol("WM_DELETE_WINDOW", self.cerrar)

    def crear_interfaz(self):
        contenedor = ttk.Frame(self.root, padding=14)
        contenedor.pack(fill=BOTH, expand=True)

        titulo = ttk.Label(
            contenedor,
            text=NOMBRE_APP,
            font=("Arial", 18, "bold"),
            bootstyle="info"
        )
        titulo.pack(fill=X, pady=(0, 10))

        self.preview_label = tk.Label(
            contenedor,
            bg="black",
            bd=0,
            highlightthickness=0
        )
        self.preview_label.pack(fill=X, pady=(0, 12))

        ttk.Label(contenedor, text="Pantalla", font=("Arial", 10, "bold")).pack(fill=X)

        self.var_pantalla = tk.StringVar(value=self.texto_pantalla(self.pantalla))

        self.combo_pantalla = ttk.Combobox(
            contenedor,
            textvariable=self.var_pantalla,
            values=[self.texto_pantalla(p) for p in self.pantallas],
            state="readonly"
        )
        self.combo_pantalla.pack(fill=X, pady=(0, 12))
        self.combo_pantalla.bind("<<ComboboxSelected>>", self.cambiar_pantalla)

        ttk.Label(contenedor, text="Lista / asignatura", font=("Arial", 10, "bold")).pack(fill=X)

        self.opcion_sin_grabar = "— sin grabación —"
        self.var_lista = tk.StringVar(value=self.opcion_sin_grabar)

        self.combo_lista = ttk.Combobox(
            contenedor,
            textvariable=self.var_lista,
            values=[self.opcion_sin_grabar] + self.listas,
            state="readonly"
        )
        self.combo_lista.pack(fill=X, pady=(0, 12))
        self.combo_lista.bind("<<ComboboxSelected>>", self.cambiar_lista)

        self.estado = ttk.Label(
            contenedor,
            text="Sin grabación activa",
            padding=8,
            bootstyle="secondary"
        )
        self.estado.pack(fill=X, pady=(0, 12))

        barra = ttk.Frame(contenedor)
        barra.pack(fill=X)

        self.boton_pausa = ttk.Button(
            barra,
            text="Pausar",
            bootstyle="warning",
            command=self.alternar_pausa
        )
        self.boton_pausa.pack(side=LEFT, fill=X, expand=True, padx=(0, 5))

        self.boton_stop = ttk.Button(
            barra,
            text="Detener grabación",
            bootstyle="danger",
            command=self.detener_actual
        )
        self.boton_stop.pack(side=LEFT, fill=X, expand=True, padx=(5, 0))

    def actualizar_preview_integrado(self):
        try:
            from PIL import ImageGrab, ImageTk, ImageDraw

            bbox = (
                self.pantalla["x"],
                self.pantalla["y"],
                self.pantalla["x"] + self.pantalla["ancho"],
                self.pantalla["y"] + self.pantalla["alto"],
            )

            ancho = max(self.preview_label.winfo_width(), 320)
            alto = int(ancho * self.pantalla["alto"] / self.pantalla["ancho"])

            imagen = ImageGrab.grab(bbox=bbox)
            imagen = imagen.resize((ancho, alto))

            if self.esta_grabando():
                draw = ImageDraw.Draw(imagen)
                r = max(16, min(ancho, alto) // 18)
                m = max(12, r // 2)

                draw.ellipse(
                    (ancho - r - m - 3, m - 3, ancho - m + 3, m + r + 3),
                    fill="black"
                )
                draw.ellipse(
                    (ancho - r - m, m, ancho - m, m + r),
                    fill="red"
                )

            foto = ImageTk.PhotoImage(imagen)
            self.preview_label.configure(image=foto)
            self.preview_label.image = foto

        except Exception:
            pass

        self.root.after(INTERVALO_PREVISUALIZACION_MS, self.actualizar_preview_integrado)

    def texto_pantalla(self, p):
        principal = " principal" if "*" in p["marcas"] else ""
        return f"{p['nombre']} {p['ancho']}x{p['alto']} +{p['x']}+{p['y']}{principal}"

    def esta_grabando(self):
        return self.grabacion is not None and self.grabacion.esta_grabando()

    def cambiar_pantalla(self, event=None):
        valor = self.var_pantalla.get()

        for p in self.pantallas:
            if self.texto_pantalla(p) == valor:
                self.pantalla = p
                break

        if self.nombre_activo:
            actual = self.nombre_activo
            self.detener_actual(actualizar_combo=False)
            self.iniciar_lista(actual)

    def cambiar_lista(self, event=None):
        if self.cambiando_lista:
            return

        nueva = self.var_lista.get()

        if nueva == self.nombre_activo:
            return

        if nueva == self.opcion_sin_grabar:
            self.detener_actual(actualizar_combo=False)
            return

        self.iniciar_lista(nueva)

    def escribir_historial(self, inicio, fin, nombre):
        ruta = Path(__file__).resolve().parent / LOG_BOTONES
        with ruta.open("a", encoding="utf-8") as f:
            f.write(f"{inicio} -> {fin} - {nombre}\n")

    def iniciar_lista(self, nombre):
        fin = ahora_txt()

        if self.nombre_activo is not None:
            self.escribir_historial(self.inicio_activo, fin, self.nombre_activo)
            self.parar_grabacion_sin_historial()

        self.nombre_activo = nombre
        self.inicio_activo = fin

        self.grabacion = Grabacion(self.pantalla, nombre)
        self.grabacion.iniciar()

        self.boton_pausa.config(text="Pausar", bootstyle="warning")
        self.actualizar_estado()

    def alternar_pausa(self):
        if not self.grabacion:
            return

        self.grabacion.alternar_pausa()

        if self.grabacion.pausado:
            self.boton_pausa.config(text="Reanudar", bootstyle="success")
        else:
            self.boton_pausa.config(text="Pausar", bootstyle="warning")

        self.actualizar_estado()

    def actualizar_estado(self):
        if not self.grabacion or not self.nombre_activo:
            self.estado.config(text="Sin grabación activa")
            return

        segundos = int(self.grabacion.segundos())
        h = segundos // 3600
        m = (segundos % 3600) // 60
        s = segundos % 60

        modo = "PAUSA" if self.grabacion.pausado else "REC"

        self.estado.config(
            text=f"{modo} {h:02d}:{m:02d}:{s:02d} · {self.nombre_activo} · {self.grabacion.archivo}"
        )

        self.root.after(500, self.actualizar_estado)

    def parar_grabacion_sin_historial(self):
        if self.grabacion:
            self.grabacion.detener()
            self.grabacion = None

        self.boton_pausa.config(text="Pausar", bootstyle="warning")

    def detener_actual(self, actualizar_combo=True):
        if self.nombre_activo is None:
            return

        fin = ahora_txt()
        self.escribir_historial(self.inicio_activo, fin, self.nombre_activo)

        self.parar_grabacion_sin_historial()

        self.nombre_activo = None
        self.inicio_activo = None
        self.estado.config(text="Sin grabación activa")

        if actualizar_combo:
            self.cambiando_lista = True
            self.var_lista.set(self.opcion_sin_grabar)
            self.cambiando_lista = False

    def cerrar(self):
        self.detener_actual(actualizar_combo=False)
        self.root.destroy()


def main():
    comprobar_dependencias()
    root = ttk.Window(themename="darkly")
    App(root)
    root.mainloop()


if __name__ == "__main__":
    main()
