# errors.py
'''
Gestión de errores del compilador.
'''
from rich.console import Console

_errors_detected = 0
_console = Console()

def set_console(console):
    global _console
    _console = console

def error(message, lineno=None):
    global _errors_detected
    if lineno:
        _console.print(f'la linea {lineno} tiene el siguiente error: [red]{message}[/red]')
    else:
        _console.print(f'[red]{message}[/red]')
    _errors_detected += 1

def errors_detected():
    return _errors_detected

def clear_errors():
    global _errors_detected
    _errors_detected = 0

# ===================================================
# Clasificación de tokens
# ===================================================

def _token_category(tok_type, tok_value=''):
    if tok_type.endswith('_LITERAL'):
        kind = tok_type.replace('_LITERAL', '').lower()
        return 'literal', kind

    if tok_type == 'ID':
        return 'id', tok_value

    if tok_type == 'ARRAY_SIZED':
        return 'array', tok_value

    if tok_type == 'ARRAY':
        return 'array_key', tok_value

    if tok_type.isupper():
        if tok_value.isalpha():
            return 'keyword', tok_value
        else:
            return 'operator', tok_value

    return 'punct', tok_type

# ===================================================
# Inferencia de contexto desde la pila
# ===================================================

def _stack_context(parser):
    try:
        
        stack_types = [
            getattr(sym, 'type', None)
            for sym in parser.symstack
            if getattr(sym, 'type', None) not in (None, '$end')
        ]
        
        stack_values = [
            str(getattr(sym, 'value', ''))
            for sym in parser.symstack
            if getattr(sym, 'type', None) not in (None, '$end')
        ]
        
        print(f"  STACK types={stack_types}")
        print(f"  STACK values={stack_values}")

        if not stack_types or stack_types == ['ID']:
            return 'declaración incompleta'

        if 'CLASS' in stack_types:
            return 'declaración de clase'

        if 'FOR' in stack_types:
            return 'encabezado for'

        if 'WHILE' in stack_types:
            return 'condición while'

        if 'IF' in stack_types:
            return 'condición if'

        if 'FUNCTION' in stack_types:
            if ')' in stack_values:
                return 'función sin igual'
            if 'ARRAY' in stack_types and 'expr' in stack_types:
                return 'array de retorno sin tipo'
            if '(' not in stack_values and 'ARRAY' not in stack_types:
                return 'función sin tipo retorno'
            if '(' in stack_values:
                return 'lista de parámetros'
            return 'tipo función'

        if '{' in stack_values:
            if 'type_func' in stack_types:
                return 'cuerpo de función'
            if ':' in stack_values:
                return 'inicialización de array'
            return 'cuerpo de función'

        if 'decl' in stack_types:
            if 'ARRAY' in stack_types:
                return 'declaración sin nombre'
            if 'ID' in stack_types:
                return 'nivel global'

        if ':' in stack_values:
            if stack_types.count('ARRAY') >= 1 and any(
                t in stack_types for t in ('INTEGER', 'FLOAT', 'BOOLEAN', 'CHAR', 'STRING', 'VOID')
            ):
                return 'declaración con tipo array'
            if any(t in stack_types for t in ('INTEGER', 'FLOAT', 'BOOLEAN', 'CHAR', 'STRING', 'VOID')):
                return 'declaración con tipo'
            if 'ARRAY' in stack_types:
                return 'declaración con inicialización'
            if stack_types.count('ID') >= 2:
                return 'tipo de declaración'
            return 'declaración'

        if ';' in stack_values:
            semi_idx = stack_values.index(';')
            ids_after_semi = [
                stack_types[i] for i in range(semi_idx + 1, len(stack_types))
                if stack_types[i] == 'ID'
            ]
            if ids_after_semi:
                return 'declaración sin dos puntos'
            return 'declaración sin nombre'
        
        if '(' in stack_values:
            return 'lista de parámetros'
        
    except Exception:
        pass
    return None

# ===================================================
# Hint para corchete ']'
# ===================================================

def _hint_bracket(ctx):
    if ctx == 'tipo función':
        return (
            "array sin tamaño no es válido como tipo de retorno — "
            "use 'array \\[n] tipo' (ej: 'function array \\[5] integer ()')"
        )
    elif ctx in ('lista de parámetros', 'inicialización de array'):
        return (
            "array sin tamaño en parámetro requiere el tipo elemento — "
            "use 'array \\[] tipo' (ej: 'array \\[] integer')"
        )
    else:
        return (
            "array sin tamaño no es válido aquí — "
            "use 'array \\[n] tipo' en declaraciones, "
            "'array \\[] tipo' solo es válido en parámetros"
        )

# ===================================================
# Definición del mensaje de error
# ===================================================

def define_error(p, parser=None):

    if p is None:
        error("fin de archivo inesperado — ¿falta cerrar un bloque o ';'?")
        return

    category, detail = _token_category(p.type, str(p.value))
    v, ln = str(p.value), p.lineno
    ctx = _stack_context(parser) if parser else None
    ctx_str = f" dentro de {ctx}" if ctx else ""

    # -----------------------------------------------
    # LITERAL — falta el tipo en la declaración
    # -----------------------------------------------
    if category == 'literal':
        if ctx == 'declaración con tipo':
            msg = (
                f"literal {detail} '{v}' inesperado{ctx_str} — "
                f"falta '=' antes del valor "
                f"(ej: 'a : {detail} = {v};')"
            )
        elif ctx in ('declaración', 'tipo de declaración'):
            msg = (
                f"literal {detail} '{v}' inesperado{ctx_str} — "
                f"falta el tipo en la declaración "
                f"(ej: 'a : {detail} = {v};')"
            )
        else:
            msg = (
                f"literal {detail} '{v}' inesperado{ctx_str} — "
                f"¿falta el tipo o un operador antes?"
            )

    # -----------------------------------------------
    # OPERADOR
    # -----------------------------------------------
    elif category == 'operator':
        assing_op = {'=', '+=', '-=', '*=', '/=', '%='}
        if v in assing_op and ctx in ('nivel global', 'declaración', 'declaración con inicialización'):
            msg = (
                f"operador '{v}' inesperado en nivel global — "
                f"las asignaciones solo son válidas dentro de funciones"
            )
        else:
            msg = f"operador '{v}' inesperado{ctx_str} — ¿falta el operando izquierdo?"

    # -----------------------------------------------
    # KEYWORD
    # -----------------------------------------------
    elif category == 'keyword':
        prev_ids = []
        if parser:
            prev_ids = [
                str(getattr(sym, 'value', ''))
                for sym in parser.symstack
                if getattr(sym, 'type', None) == 'ID'
                and str(getattr(sym, 'value', '')) not in ('true', 'false', 'this')
            ]

        reserved_as_name = {'new', 'class', 'this', 'super', 'extends'}
        if v.lower() in reserved_as_name:
            msg = (
                f"'{v}' es una palabra reservada y no puede usarse como nombre de variable — "
                f"elija un nombre diferente"
            )
        elif ctx == 'declaración incompleta' and prev_ids:
            bad_name = prev_ids[-1]
            msg = (
                f"'{v}' inesperado después de '{bad_name}' — "
                f"falta ':' entre el nombre y el tipo "
                f"(ej: '{bad_name} : {v.lower()} = ...;')"
            )
        elif ctx in ('declaración', 'tipo de declaración') and prev_ids:
            bad_token = prev_ids[-1]
            msg = (
                f"'{v}' inesperado después de '{bad_token}'{ctx_str} — "
                f"'{bad_token}' no es un tipo válido, "
                f"¿quisiste escribir 'function' en lugar de '{bad_token}'?"
            )
        elif ctx and 'función' in ctx:
            msg = (
                f"'{v}' en posición incorrecta{ctx_str} — "
                f"verifique que usó 'function' (minúsculas) antes del tipo de retorno"
            )
        else:
            msg = f"'{v}' en posición incorrecta{ctx_str} — ¿falta '}}' o ';' antes?"

    # -----------------------------------------------
    # ARRAY (ARRAY_SIZED)
    # -----------------------------------------------
    elif category == 'array':
        msg = f"'{v}' inesperado{ctx_str} — ¿falta el tamaño entre '[' y ']'?"

    # -----------------------------------------------
    # ARRAY KEY (palabra reservada 'array')
    # -----------------------------------------------
    elif category == 'array_key':
        inner_context = ('cuerpo de función', 'bloque', 'sentencia')
        outer_context = ('declaración', 'declaración con inicialización')

        if ctx == 'declaración sin nombre':
            msg = (
                f"'array' inesperado — "
                f"falta el nombre y ':' antes del tipo "
                f"(ej: 'nombre : array \\[n] integer;')"
            )
        elif ctx == 'declaración incompleta':
            msg = (
                f"'array' inesperado — "
                f"falta ':' entre el nombre y el tipo "
                f"(ej: 'nombre : array \\[n] integer;')"
            )
        elif ctx == 'declaración sin dos puntos':
            msg = (
                f"'array' inesperado — "
                f"falta ':' entre el nombre y el tipo "
                f"(ej: 'nombre : array \\[n] integer;')"
            )            
        elif ctx == 'declaración con tipo array':
            msg = (
                f"'array' inesperado{ctx_str} — "
                f"hay dos tipos encadenados, un array ya fue declarado antes — "
                f"¿falta ';' para terminar la declaración? "
                f"Además 'array []' sin tamaño no es válido en declaraciones, "
                f"use 'array \\[n] tipo' (ej: 'array \\[5] float')"
            )
        elif ctx in ('nivel global', None):
            msg = (
                f"'array' inesperado en nivel global — "
                f"falta el nombre de la variable antes del tipo "
                f"(ej: 'nombre : array \\[n] integer;')"
            )
        elif ctx in outer_context:
            msg = (
                f"'array' inesperado{ctx_str} — "
                f"hay dos tipos seguidos, ¿falta ';' para terminar la declaración anterior?"
            )
        elif ctx in inner_context:
            msg = (
                f"'array' inesperado{ctx_str} — "
                f"falta el tamaño entre '[' y ']' (ej: 'array \\[10] integer')"
            )
        else:
            msg = f"'array' inesperado{ctx_str} — falta el tamaño entre '[' y ']'"
    # -----------------------------------------------
    # IDENTIFICADOR
    # -----------------------------------------------
    elif category == 'id':
        if ctx and 'función' in ctx:
            msg = (
                f"identificador '{v}' inesperado{ctx_str} — "
                f"'{v}' no es un tipo válido, "
                f"¿quisiste escribir 'function' en lugar de '{v}'?"
            )
        else:
            msg = f"identificador '{v}' inesperado{ctx_str} — ¿falta ':', '(' o ';'?"

    # -----------------------------------------------
    # PUNTUACIÓN
    # -----------------------------------------------
    else:
        # '(' requiere lógica especial según contexto
        if v == '(':
            if ctx == 'array de retorno sin tipo':
                hint = (
                    "falta el tipo elemento del array de retorno — "
                    "use 'function array \\[n] tipo (params)' "
                    "(ej: 'function array \\[3] integer ()')"
                )
            elif ctx == 'tipo función' and 'ARRAY' not in [getattr(sym, 'type', None) for sym in parser.symstack]:
                hint = "falta el tipo de retorno antes de '(' (ej: 'main : function integer () = { ... }')"
            elif ctx == 'tipo función':
                stack_t = [getattr(sym, 'type', None) for sym in parser.symstack] if parser else []
                if 'ARRAY' not in stack_t:
                    hint = "falta el tipo de retorno antes de '(' (ej: 'main : function integer () = { ... }')"
                else:
                    hint = (
                        "¿falta el tipo elemento del array de retorno? "
                        "Use 'function array \\[n] tipo (params)'"
                    )
            else:
                hint = "¿paréntesis inesperado?"
            msg = f"'{v}' inesperado{ctx_str} — {hint}"

        elif v == ';':
            if ctx == 'inicialización de array':
                hint = "los elementos se separan con ',' no con ';' (ej: '{ 1, 2, 3 }')"
            elif ctx == 'cuerpo de función':
                hint = "';' después de '}' no es válido al cerrar una función — elimine el ';' final"
            else:
                hint = "¿punto y coma sobrante o declaración incompleta?"
            msg = f"'{v}' inesperado{ctx_str} — {hint}"

        elif v == '{':
            if ctx == 'función sin igual':
                hint = "falta '=' antes del cuerpo de la función (ej: 'main : function integer () = { ... }')"
            elif ctx in ('declaración con tipo array', 'declaración con tipo'):
                hint = "falta '=' antes de '{' (ej: 'a : array [3] integer = { 1, 2, 3 };')"
            else:
                hint = "¿llave inesperada?"
            msg = f"'{v}' inesperado{ctx_str} — {hint}"

        elif v == ':':
            # revisar si el token anterior en la pila es una palabra reservada
            reserved_in_stack = {'NEW', 'CLASS', 'SUPER', 'EXTENDS', 'THIS',
                                'IF', 'FOR', 'WHILE', 'RETURN', 'PRINT',
                                'FUNCTION', 'ARRAY', 'INTEGER', 'FLOAT',
                                'BOOLEAN', 'CHAR', 'STRING', 'VOID'}
            
            last_reserved = None
            if parser:
                for sym in reversed(parser.symstack):
                    t = getattr(sym, 'type', None)
                    if t in reserved_in_stack:
                        last_reserved = str(getattr(sym, 'value', t.lower()))
                        break
            
            if last_reserved:
                msg = (
                    f"':' inesperado después de '{last_reserved}'{ctx_str} — "
                    f"'{last_reserved}' es una palabra reservada y no puede usarse como nombre de variable, "
                    f"elija un nombre diferente"
                )
            else:
                msg = f"':' inesperado{ctx_str} — ¿falta el tipo después de ':'?"

        else:
            punct_hints = {
                ']': _hint_bracket(ctx),
                ')': "¿paréntesis sin abrir?",
                '}': "¿llave sin abrir? — verifique que la función no termine con ';' después de '}'",
                ';': "¿punto y coma sobrante o declaración incompleta?",
                ',': "¿coma extra o argumento faltante?",
                '.': "'.' inesperado — ¿acceso a campo mal formado?",
            }
            hint = punct_hints.get(v, "revisa la estructura")
            msg = f"'{v}' inesperado{ctx_str} — {hint}"

    error(msg, ln)