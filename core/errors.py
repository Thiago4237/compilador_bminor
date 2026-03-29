# errors.py
'''
Gestión de errores del compilador.

Una de las partes más importantes (y molestas) de escribir un compilador
es la notificación fiable de mensajes de error al usuario. Este archivo
debería consolidar algunas funciones básicas de gestión de errores en un solo lugar.
Facilitar la notificación de errores. Facilitar la detección de errores.

Podría ampliarse para que sea más potente posteriormente.

Variable global que indica si se ha producido algún error. El compilador puede 
consultar esto posteriormente para decidir si debe detenerse.
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
    
def _token_category(tok_type, tok_value=''):
    """Clasifica un token solo por su nombre, sin listas previas."""
    
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
    
    # Carácter literal de puntuación
    return 'punct', tok_type

_STACK_CONTEXT = {
    'decl':            'declaración',
    'decl_init':       'declaración con inicialización',
    'type_simple':     'tipo simple',
    'type_array':      'tipo arreglo',
    'type_array_sized':'tipo arreglo con tamaño',
    'type_func':       'tipo función',
    'expr':            'expresión',
    'expr1':           'expresión',
    'expr2':           'expresión',
    'lval':            'lado izquierdo de asignación',
    'param':           'parámetro',
    'param_list':      'lista de parámetros',
    'stmt':            'sentencia',
    'stmt_list':       'cuerpo de función',
    'block_stmt':      'bloque',
    'if_cond':         'condición if',
    'for_header':      'encabezado for',
    'while_cond':      'condición while',
    'opt_expr_list':   'lista de expresiones',
    'member_list':   'cuerpo de clase',
    'decl_class':    'declaración de clase',
}

def _stack_context(parser):
    """Lee los símbolos en la pila del parser y devuelve el contexto más relevante."""
    try:
        for sym in reversed(parser.symstack):
            name = getattr(sym, 'type', None)
            if name and name in _STACK_CONTEXT:
                return _STACK_CONTEXT[name]
    except Exception:
        pass
    return None


def define_error(p, parser=None):
    
    if p is None:
        error("fin de archivo inesperado — ¿falta cerrar un bloque o ';'?")
        return

    category, detail = _token_category(p.type, str(p.value))
    
    v, ln = str(p.value), p.lineno
    ctx = _stack_context(parser) if parser else None
    ctx_str = f" dentro de {ctx}" if ctx else ""

    if category == 'literal':
        msg = f"literal {detail} '{v}' inesperado{ctx_str} — ¿falta el tipo o un operador antes?"

    elif category == 'keyword':
        msg = f"palabra reservada '{v}'{ctx_str} en posición incorrecta — ¿falta '}}' o ';' antes?"

    elif category == 'array':
        msg = f"'{v}' inesperado{ctx_str} — ¿falta el tamaño entre '[' y ']'?"
    
    elif category == 'array_key':
        
        inner_context = ('cuerpo de función', 'bloque', 'sentencia')    
        outer_context = ('declaración', 'declaración con inicialización')

        if ctx in inner_context:
            msg = f"'{v}' inesperada{ctx_str} — ¿falta el tamaño del array entre '[' y ']'?"
        elif ctx in outer_context:
            msg = f"'{v}' inesperada{ctx_str} — ¿falta el nombre del array después de 'array'?"
        else:
            msg = f"'{v}' inesperada{ctx_str} — ¿falta el tamaño del array entre '[' y ']'?"

    elif category == 'operator':

        assing_op = {'=', '+=', '-=', '*=', '/=', '%='}

        if v in assing_op and ctx in ('declaración', 'declaración con inicialización'):
            msg = f"operador'{v}' inesperado{ctx_str} — ¿Olvidaste escribirlo dentro de una funcion?"

        else:
            msg = f"operador '{v}' inesperado{ctx_str} — ¿falta el operando izquierdo?"

    elif category == 'id':
        msg = f"identificador '{v}' inesperado{ctx_str} — ¿falta ':', '(' o ';'?"
    


    else:  # puntuación
        punct_hints = {
            ']': "¿corchete sin abrir o tamaño de arreglo mal formado?",
            ')': "¿paréntesis sin abrir?",
            '}': "¿llave sin abrir?",
            ';': "¿punto y coma sobrante o declaración incompleta?",
            ':': "¿falta el tipo después de ':'?",
            ',': "¿coma extra o argumento faltante?",
            '.': "'.' inesperado — ¿acceso a campo mal formado?",
        }
        hint = punct_hints.get(v, "revisa la estructura")
        msg = f"'{v}' inesperado{ctx_str} — {hint}"

    error(msg, ln)