# Analizador Sintáctico — bminor

Parser para el lenguaje **bminor** construido con `sly`. Genera un AST (Árbol de Sintaxis Abstracta) a partir de archivos `.bminor` y produce salidas en texto, árbol Rich y formato DOT para visualización.

---

## Estructura del proyecto

```
analizador_sintactico/
├── core/                       # Núcleo del compilador
│   ├── __init__.py
│   ├── errors.py               # Gestión de errores
│   ├── lexer.py                # Analizador léxico
│   ├── model.py                # Nodos del AST (dataclasses)
│   └── parser.py               # Analizador sintáctico (LALR)
├── ast_tree/                   # Visualización del AST
│   ├── __init__.py
│   ├── dot_graphviz.py         # Generación de grafos DOT
│   └── rich_tree.py            # Árbol visual con Rich
├── output/                     # Archivos de salida generados
│   ├── console_output/         # AST en texto plano por archivo
│   ├── graphviz_tree/          # Grafos AST en formato DOT
│   └── rich_tree/              # Árboles AST en formato Rich
├── test/                       # Archivos de prueba .bminor
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
```

| Librería    | Uso                                               |
|-------------|---------------------------------------------------|
| `sly`       | Construcción del lexer y parser (AFD/LALR)        |
| `rich`      | Impresión con color en consola y archivos         |
| `graphviz`  | Generación de archivos `.dot` para el AST         |

---

## Uso

### Ejecutar los archivos de prueba

```bash
python run.py
```

Procesa todos los `.bminor` en `test/`, imprime el resultado en consola y genera los archivos de salida en `output/`.

---

## Archivos de salida

| Carpeta | Archivo | Descripción |
|---------|---------|-------------|
| `output/console_output/` | `salida_<nombre>.txt` | AST en texto plano, o mensaje de error si el archivo es inválido |
| `output/graphviz_tree/`  | `ast_<nombre>.dot`    | Grafo AST en formato DOT (solo archivos sin errores) |
| `output/rich_tree/`      | `rich_<nombre>.txt`   | Árbol AST visual generado con Rich (solo archivos sin errores) |

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