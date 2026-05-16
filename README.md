# Compilador bminor+

Compilador para el lenguaje **bminor+** construido en Python con `sly`. Realiza análisis léxico, sintáctico y semántico, genera un AST y produce múltiples formatos de salida para visualización y seguimiento.

---

## Integrantes del proyecto 
- Cristhian Loaiza
- Stephania Duque 
- Victor Rosero

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
│   ├── typesys.py              # Sistema de tipos
│   ├── IRCode.py               # Generador de código intermedio (IR)
│   └── iroptimizer.py          # Optimizador de IR (-O0, -O1, -O2)
├── ast_tree/                   # Visualización del AST
│   ├── __init__.py
│   ├── dot_graphviz.py         # Generación de grafos DOT
│   └── rich_tree.py            # Árbol visual con Rich
├── output/                     # Archivos de salida generados
│   ├── console_output/         # AST y errores en texto plano
│   ├── graphviz_tree/          # Grafos AST en formato DOT
│   ├── rich_tree/              # Árboles AST en formato Rich
│   └── ir/                     # IR generada (con nivel de optimización)
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
| `sly`         | Construcción del lexer y parser               |
| `rich`        | Impresión con color en consola                  |
| `graphviz`    | Generación de archivos `.dot` para el AST                  |
| `multimethod` | Patrón Visitor para el analizador semántico                |

---

## Uso

### Ejecutar todos los archivos de prueba

```bash
python run.py
```

Procesa todos los archivos `.bminor` y `.bpp` en `test/`, ejecuta el análisis completo y genera los archivos de salida en `output/`. Por defecto aplica `-O0` (sin optimización).

### Ejecutar un archivo específico

```bash
python run.py test/archivo.bminor
python run.py test/archivo.bpp
```

### Ejecutar con optimización de IR

Se puede indicar el nivel de optimización como argumento adicional:

```bash
python run.py test/archivo.bminor --O0   # sin optimización (por defecto)
python run.py test/archivo.bminor --O1   # optimización local simple
python run.py test/archivo.bminor --O2   # optimización local + eliminación de muertos
```

También se puede aplicar a todos los archivos de la carpeta `test/`:

```bash
python run.py --O1
python run.py --O2
```

La IR resultante se guarda en `output/ir/ir_<nombre>_-O<nivel>.txt`.

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

### 4. Generación de IR
Produce una representación intermedia de tres direcciones a partir del AST verificado. Las instrucciones usan registros temporales (`R1`, `R2`, …) y etiquetas (`Lthen1`, `Lend2`, …).

### 5. Optimización de IR
Aplica transformaciones sobre la IR según el nivel indicado. Ver sección [Optimización de IR](#optimización-de-ir) más abajo.

### 6. Documentacion de ejemplo para simplificacion del patron visitor
- https://refactoring.guru/es/design-patterns/visitor-double-dispatch
- https://coderkarl.wordpress.com/2012/02/29/simplifying-the-visitor-pattern-with-the-dynamic-keyword/

---

## Optimización de IR

El optimizador actúa sobre la IR generada antes de interpretar el programa. Cada nivel incluye todas las transformaciones del nivel anterior.

### -O0 — Sin optimización (por defecto)

La IR se conserva exactamente como la produce el generador. Útil para depuración y como referencia de comparación.

### -O1 — Optimización local simple

Recorre las instrucciones de cada función y aplica las siguientes transformaciones:

**Constant folding** — Evalúa en tiempo de compilación operaciones cuyos dos operandos son literales conocidos, reemplazando la instrucción por un `MOVI` o `MOVF` con el resultado.

```
MOVI 3, R1
MOVI 4, R2
MULI R1, R2, R3   →   MOVI 12, R3
```

Operaciones soportadas: `ADDI`, `SUBI`, `MULI`, `DIVI`, `ADDF`, `SUBF`, `MULF`, `DIVF`, `AND`, `OR`, `XOR`. La división por cero nunca se optimiza.

**Simplificación algebraica** — Aplica identidades matemáticas cuando al menos un operando tiene valor constante conocido:

| Patrón | Resultado |
|--------|-----------|
| `x + 0` | `x` |
| `0 + x` | `x` |
| `x - 0` | `x` |
| `x * 1` | `x` |
| `1 * x` | `x` |
| `x * 0` | `0` |
| `0 * x` | `0` |
| `x / 1` | `x` |

**Comparaciones constantes** — Si ambos operandos de una comparación (`CMPI`, `CMPF`, `CMPB`) son constantes, la reemplaza por `MOVI 1` o `MOVI 0`.

```
MOVI 3, R1
MOVI 10, R2
CMPI <, R1, R2, R3   →   MOVI 1, R3
```

**Simplificación de ramas condicionales** — Si la condición de un `CBRANCH` es un valor constante conocido, lo convierte en un `BRANCH` incondicional hacia la rama correcta.

```
CBRANCH R3, Lthen1, Lelse2   →   BRANCH Lthen1   (si R3 = 1)
```

**Eliminación de código inalcanzable** — Descarta todas las instrucciones que aparecen después de un `BRANCH` o `RET` hasta el siguiente `LABEL`, ya que nunca pueden ejecutarse.

```
BRANCH Lthen1
PRINTI R9          ← eliminado (inalcanzable)
LABEL Lthen1
```

**Eliminación de saltos redundantes** — Si un `BRANCH Lx` va seguido inmediatamente de `LABEL Lx`, el salto no tiene efecto y se elimina.

```
BRANCH Lend3
LABEL Lend3        →   LABEL Lend3
```

### -O2 — Optimización local con eliminación de temporales muertos

Incluye todo lo de `-O1` y agrega:

**Eliminación de temporales muertos** — Recorre las instrucciones en orden inverso. Si una instrucción define un registro temporal `Rk` que nunca se usa en ninguna instrucción posterior, y no tiene efectos laterales, se elimina.

```
MOVI 2, R1         ← eliminado: R1 no se usa después del folding
MOVI 3, R2         ← eliminado: R2 no se usa después del folding
MOVI 4, R3         ← eliminado: R3 no se usa después del folding
MOVI 12, R4        ← eliminado: R4 fue resultado intermedio, ya no se referencia
MOVI 14, R5        ← se conserva: R5 → STOREI R5, a
```

Las instrucciones con efectos laterales (`STORE`, `PRINT`, `CALL`, `BRANCH`, `CBRANCH`, `RET`, `LABEL`) **nunca se eliminan**, independientemente de si su resultado se usa o no.

> **Nota:** El optimizador trabaja localmente dentro de cada función. No realiza análisis entre variables en memoria (`STORE`/`LOAD`), por lo que operaciones como `b = a + 0` donde `a` viene de un `LOADI` no se simplifican aunque el valor de `a` sea conocido en tiempo de compilación. Esa capacidad correspondería a un nivel `-O3` con análisis de flujo de datos.

---

## Archivos de salida

Por cada archivo procesado **sin errores sintácticos** se generan:

| Carpeta | Archivo | Descripción |
|---------|---------|-------------|
| `output/console_output/` | `salida_<nombre>.txt` | AST en texto plano y resultado del análisis semántico |
| `output/graphviz_tree/`  | `ast_<nombre>.dot`    | Grafo AST en formato DOT |
| `output/rich_tree/`      | `rich_<nombre>.txt`   | Árbol AST visual generado con Rich |
| `output/ir/`             | `ir_<nombre>_-O<n>.txt` | IR generada con el nivel de optimización aplicado |

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