# jocarsa | captura

**jocarsa | captura** es una herramienta de grabación de escritorio para Linux orientada a docentes, desarrolladores y creadores de conjuntos de datos para Inteligencia Artificial.

A diferencia de un grabador tradicional, además del vídeo genera información estructurada sobre la interacción del usuario con el ordenador, permitiendo reconstruir posteriormente la sesión o utilizarla para entrenar agentes capaces de aprender el uso de aplicaciones gráficas.

---

# Características

- Grabación de pantalla completa.
- Grabación de micrófono.
- Selección de monitor.
- Vista previa flotante.
- Nombres automáticos de las grabaciones.
- Listas de grabación mediante `listas.txt`.
- Registro de posición del ratón.
- Registro de clics.
- Registro de teclado.
- Salida en formatos abiertos.

---

# Archivos generados

Cada grabación produce un conjunto de archivos sincronizados.

```
2026-06-26_21-13-40-programacion.mp4
2026-06-26_21-13-40-programacion.mouse.csv
2026-06-26_21-13-40-programacion.keys.csv
```

Todos utilizan la misma referencia temporal.

---

# Registro del ratón

El ratón se almacena en formato CSV.

```csv
t,event,x,y,button
0.000,move,812,443,
1.000,move,818,447,
1.243,down,820,450,1
1.328,up,820,450,1
```

Se registran:

- posición periódica
- pulsaciones
- liberaciones

Este formato ocupa muy poco espacio y permite reconstruir posteriormente la actividad del usuario.

---

# Registro del teclado

Cada pulsación queda almacenada como evento.

```csv
t,event,key
0.512,down,Control_L
0.621,down,S
0.700,up,S
0.712,up,Control_L
```

Esto permite reconstruir:

- atajos de teclado
- escritura
- combinaciones de teclas
- velocidad de escritura

---

# ¿Por qué registrar metadatos?

Un vídeo únicamente almacena píxeles.

Los metadatos almacenan el comportamiento.

Esto permite:

- entrenar agentes de IA
- generar tutoriales automáticos
- estudiar interacción humano-computadora
- crear mapas de calor
- detectar zonas de atención
- reconstruir exactamente una sesión
- analizar productividad
- generar documentación automáticamente

---

# Filosofía

El vídeo responde a la pregunta:

> ¿Qué ocurrió?

Los metadatos responden a la pregunta:

> ¿Cómo ocurrió?

La combinación de ambos convierte una simple grabación en un conjunto de datos de enorme valor.

---

# Casos de uso

- Formación.
- Cursos online.
- Programación.
- Investigación.
- UX.
- Ingeniería de software.
- Captura de demostraciones.
- Entrenamiento de agentes gráficos.
- Aprendizaje por imitación.
- Generación de datasets para IA.

---

# Tecnologías

- Python
- FFmpeg
- X11
- xdotool
- Tkinter
- Pillow

---

# Licencia

MIT
