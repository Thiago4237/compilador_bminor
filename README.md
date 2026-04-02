# Compilador bminor+

Compilador para el lenguaje **bminor+** construido en Python con `sly`. Realiza análisis léxico, sintáctico y semántico, genera un AST y produce múltiples formatos de salida para visualización y seguimiento.

---

## Estructura del proyecto

```
compilador_bminor/
├── core/                       # Núcleo del compilador
│   ├── __init__.py
│   ├── errors.py               # Gestión de errores léxicos y sintácticos
│   ├── lexer.py                # Analizador léxico
│   ├── model.py                # Nodos del AST (dataclasses)
│   ├── parser.py               # Analizador sintáctico (LALR)
│   ├── checker.py              # Analizador semántico (Visitor)
│   ├── symtab.py               # Tabla de símbolos (ChainMap)
│   └── typesys.py              # Sistema de tipos
├── ast_tree/                   # Visualización del AST
│   ├── __init__.py
│   ├── dot_graphviz.py         # Generación de grafos DOT
│   └── rich_tree.py            # Árbol visual con Rich
├── output/                     # Archivos de salida generados
│   ├── console_output/         # AST y errores en texto plano
│   ├── graphviz_tree/          # Grafos AST en formato DOT
│   └── rich_tree/              # Árboles AST en formato Rich
├── test/                       # Archivos de prueba .bminor / .bpp
├── grammar.txt                 # Tablas LALR generadas por sly
├── run.py                      # Ejecutor principal
└── README.md
```

---

## Instalación de dependencias

Versión requerida: **Python 3.10+**

```bash
pip install sly
pip install rich
pip install graphviz
pip install multimethod
```

| Librería      | Uso                                                        |
|---------------|------------------------------------------------------------|
| `sly`         | Construcción del lexer y parser (AFD/LALR)                 |
| `rich`        | Impresión con color en consola y archivos                  |
| `graphviz`    | Generación de archivos `.dot` para el AST                  |
| `multimethod` | Patrón Visitor para el analizador semántico                |

---

## Uso

### Ejecutar todos los archivos de prueba

```bash
python run.py
```

Procesa todos los archivos `.bminor` y `.bpp` en `test/`, ejecuta el análisis completo y genera los archivos de salida en `output/`.

### Ejecutar un archivo específico

```bash
python run.py test/archivo.bminor
python run.py test/archivo.bpp
```

Procesa únicamente el archivo indicado y genera sus salidas correspondientes.

---

## Fases del compilador

Para cada archivo procesado se ejecutan las siguientes fases en orden:

### 1. Análisis léxico
Tokeniza el código fuente. Si hay errores léxicos (caracteres ilegales, literales mal formados) se reportan y el proceso continúa.

### 2. Análisis sintáctico
Construye el AST a partir de los tokens. Si hay errores sintácticos se reportan con mensajes descriptivos que indican la línea, el token problemático y una sugerencia de corrección. Si hay errores sintácticos **no se ejecutan las fases siguientes**.

### 3. Análisis semántico
Recorre el AST con el patrón Visitor e implementa cuatro fases:

| Fase | Descripción |
|------|-------------|
| **Fase 1** | Tabla de símbolos global, registro de declaraciones, identificadores no definidos |
| **Fase 2** | Scopes anidados, parámetros de funciones, redeclaraciones por alcance |
| **Fase 3** | Anotación de tipos, validación de operadores y asignaciones |
| **Fase 4** | Validación de llamadas a funciones, retornos, break y continue |

---

## Archivos de salida

Por cada archivo procesado **sin errores sintácticos** se generan:

| Carpeta | Archivo | Descripción |
|---------|---------|-------------|
| `output/console_output/` | `salida_<nombre>.txt` | AST en texto plano y resultado del análisis semántico |
| `output/graphviz_tree/`  | `ast_<nombre>.dot`    | Grafo AST en formato DOT |
| `output/rich_tree/`      | `rich_<nombre>.txt`   | Árbol AST visual generado con Rich |

Los archivos con errores sintácticos solo generan `salida_<nombre>.txt` con el mensaje de error.

---

## Visualizar el grafo DOT

Los archivos `.dot` en `output/graphviz_tree/` se pueden visualizar sin instalar nada adicional:

1. Abre el archivo `.dot` con cualquier editor de texto
2. Copia el contenido
3. Pégalo en cualquiera de estos sitios:

| Sitio | URL |
|-------|-----|
| Graphviz Online | https://dreampuf.github.io/GraphvizOnline |
| Edotor | https://edotor.net |
| Viz.js | https://viz-js.com |

---

## Extensiones soportadas

| Extensión | Descripción |
|-----------|-------------|
| `.bminor` | Lenguaje bminor estándar |
| `.bpp`    | Lenguaje bminor+ con extensiones OOP |

---

## Ejemplos de errores detectados

### Sintácticos
```
linea 2: literal integer '10' inesperado dentro de declaración — falta el tipo (ej: 'a : integer = 10;')
linea 3: operador '+=' inesperado en nivel global — las asignaciones solo son válidas dentro de funciones
linea 2: 'func' no es un tipo válido, ¿quisiste escribir 'function'?
```

### Semánticos
```
[semántico] símbolo 'x' no definido
[semántico] 'x' ya está declarado en este alcance
[semántico] no se puede asignar 'boolean' a una variable de tipo 'integer'
[semántico] la función 'f' espera 2 argumento(s) pero recibió 3
[semántico] la función 'f' debe retornar 'integer' pero se retorna 'boolean'
[semántico] la condición del 'if' debe ser boolean, se recibió 'integer'
```