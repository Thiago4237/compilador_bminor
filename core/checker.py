from dataclasses import dataclass
from typing      import Any
from multimethod import multimeta

try:
    from .symtab  import Symtab
    from .model   import *
    from .errors  import error as report_error
    from .typesys import check_binop, check_unaryop, loockup_type
except ImportError:
    from symtab  import Symtab
    from model   import *
    from errors  import error as report_error
    from typesys import check_binop, check_unaryop, loockup_type

# ===================================================
# Símbolo semántico
# ===================================================

@dataclass
class Symbol:
    name: str
    kind: str   # 'variable', 'function', 'parameter', 'constant', 'class'
    type: Any   # nodo Type del model.py
    node: Any   # nodo AST original

    def __repr__(self):
        return f"Symbol(name={self.name!r}, kind={self.kind!r}, type={self.type!r})"

# ===================================================
# Helpers de tipo
# ===================================================

def _type_name(typ) -> str:
    """Convierte un nodo Type a su nombre canónico para typesys."""
    
    if typ is None:
        return None
    
    if isinstance(typ, SimpleType):
        return typ.name.lower()
    
    if isinstance(typ, ArrayType):
        return f'array[] {_type_name(typ.elem)}'
    
    if isinstance(typ, ArraySizedType):
        return f'array[] {_type_name(typ.elem)}'
    
    if isinstance(typ, FuncType):
        return f'function -> {_type_name(typ.ret)}'
    
    if isinstance(typ, ClassType):
        return typ.name
    
    if isinstance(typ, str):
        return typ.lower()
    
    return str(typ)

def _types_compatible(t1, t2) -> bool:
    """Dos tipos son compatibles si sus nombres canónicos son iguales."""
    return _type_name(t1) == _type_name(t2)

def _literal_type(kind: str) -> str:
    """Retorna el nombre de tipo de un literal."""
    mapping = {
        'int':    'integer',
        'float':  'float',
        'bool':   'boolean',
        'char':   'char',
        'string': 'string',
    }
    return mapping.get(kind, kind)

# ===================================================
# Visitor base con multimethod
# ===================================================

class Visitor(metaclass=multimeta):
    pass

# ===================================================
# Checker — Fases 1‒4
# ===================================================

class Checker(Visitor):

    def __init__(self):
        self.symtab       = Symtab('global')
        self.errors       = []
        self.current_func = None   # Symbol de la función actual
        self.in_loop      = False  # para break/continue

    # ---------------------------------------------------
    # Reporte de errores
    # ---------------------------------------------------

    def sem_error(self, msg, node=None):
        lineno = getattr(node, 'lineno', None)
        full   = f"[semántico] {msg}"
        self.errors.append(full)
        report_error(full, lineno)

    # ---------------------------------------------------
    # Helpers de scope
    # ---------------------------------------------------

    def _enter_scope(self, name):
        self.symtab = Symtab(name, parent=self.symtab)

    def _exit_scope(self):
        self.symtab = self.symtab.parent

    def _add_symbol(self, name, kind, typ, node):
        sym = Symbol(name, kind, typ, node)
        try:
            self.symtab.add(name, sym)
        except Symtab.SymbolDefinedError:
            self.sem_error(f"'{name}' ya está declarado en este alcance", node)
        except Symtab.SymbolConflictError:
            self.sem_error(f"'{name}' ya está declarado con un tipo distinto en este alcance", node)
        return sym

    def _check_name(self, name, node):
        sym = self.symtab.get(name)
        if sym is None:
            self.sem_error(f"símbolo '{name}' no definido", node)
        return sym

    def _visit_list(self, nodes):
        for n in nodes:
            if n is not None:
                self.visit(n)

    # ===================================================
    # PROGRAMA
    # ===================================================

    def visit(self, node: Program):
        for decl in node.decls:
            self.visit(decl)

    # ===================================================
    # DECLARACIONES
    # ===================================================

    def visit(self, node: DeclTyped):
        kind = 'function' if isinstance(node.typ, FuncType) else 'variable'
        self._add_symbol(node.name, kind, node.typ, node)

    def visit(self, node: DeclInit):
        if isinstance(node.typ, FuncType):
            self._visit_func_decl(node)
        elif isinstance(node.typ, SimpleType) and node.typ.name == 'CONSTANT':
            self._add_symbol(node.name, 'constant', node.typ, node)
            if node.init is not None:
                self.visit(node.init)
        else:
            self._add_symbol(node.name, 'variable', node.typ, node)
            if node.init is not None:
                # --- Fase 3: validar tipo del inicializador ---
                if isinstance(node.init, list):
                    self._visit_list(node.init)
                else:
                    init_type = self.visit(node.init)
                    decl_type = _type_name(node.typ)
                    if init_type and decl_type and init_type != decl_type:
                        self.sem_error(
                            f"no se puede inicializar '{node.name}' de tipo '{decl_type}' "
                            f"con valor de tipo '{init_type}'",
                            node
                        )

    def _visit_func_decl(self, node: DeclInit):
        func_sym = self._add_symbol(node.name, 'function', node.typ, node)

        prev_func         = self.current_func
        self.current_func = func_sym
        self._enter_scope(f'function:{node.name}')

        for param in node.typ.params:
            self._add_symbol(param.name, 'parameter', param.typ, node)

        if node.init is not None:
            if isinstance(node.init, list):
                self._visit_list(node.init)
            else:
                self.visit(node.init)

        self._exit_scope()
        self.current_func = prev_func

    # ---------------------------------------------------
    # CLASES
    # ---------------------------------------------------

    def visit(self, node: DeclClass):
        self._add_symbol(node.name, 'class', ClassType(node.name), node)
        self._enter_scope(f'class:{node.name}')

        if node.parent is not None:
            parent_sym = self.symtab.get(node.parent)
            if parent_sym is None:
                self.sem_error(f"clase padre '{node.parent}' no definida", node)

        for member in node.members:
            self.visit(member)

        self._exit_scope()

    def visit(self, node: ClassMember):
        self.visit(node.decl)

    def visit(self, node: ConstructorDecl):
        self._enter_scope('constructor')
        for param in node.params:
            self._add_symbol(param.name, 'parameter', param.typ, node)
        self._visit_list(node.body)
        self._exit_scope()

    def visit(self, node: GetterDecl):
        self._add_symbol(node.name, 'getter', node.ret, node)
        self._enter_scope(f'getter:{node.name}')
        self._visit_list(node.body)
        self._exit_scope()

    def visit(self, node: SetterDecl):
        self._add_symbol(node.name, 'setter', SimpleType('void'), node)
        self._enter_scope(f'setter:{node.name}')
        self._add_symbol(node.param.name, 'parameter', node.param.typ, node)
        self._visit_list(node.body)
        self._exit_scope()

    # ===================================================
    # STATEMENTS
    # ===================================================

    def visit(self, node: Block):
        self._enter_scope('block')
        self._visit_list(node.stmts)
        self._exit_scope()

    def visit(self, node: Print):
        self._visit_list(node.values)

    # --- Fase 4: validar tipo de retorno ---
    def visit(self, node: Return):
        ret_type = None
        if node.value is not None:
            ret_type = self.visit(node.value)

        if self.current_func is None:
            self.sem_error("'return' fuera de una función", node)
            return

        func_ret = _type_name(self.current_func.type.ret)

        if func_ret == 'void' and node.value is not None:
            self.sem_error(
                f"la función '{self.current_func.name}' es void y no debe retornar un valor",
                node
            )
        elif func_ret != 'void' and node.value is None:
            self.sem_error(
                f"la función '{self.current_func.name}' debe retornar un valor de tipo '{func_ret}'",
                node
            )
        elif func_ret != 'void' and ret_type and ret_type != func_ret:
            self.sem_error(
                f"la función '{self.current_func.name}' debe retornar '{func_ret}' "
                f"pero se retorna '{ret_type}'",
                node
            )

    # --- Fase 3: condición debe ser boolean ---
    def visit(self, node: If):
        cond_type = None
        if node.cond is not None:
            cond_type = self.visit(node.cond)
        if cond_type and cond_type != 'boolean':
            self.sem_error(
                f"la condición del 'if' debe ser boolean, se recibió '{cond_type}'",
                node
            )
        self.visit(node.then)
        if node.otherwise is not None:
            self.visit(node.otherwise)

    def visit(self, node: For):
        self._enter_scope('for')
        if node.init is not None:
            self.visit(node.init)
        if node.cond is not None:
            cond_type = self.visit(node.cond)
            if cond_type and cond_type != 'boolean':
                self.sem_error(
                    f"la condición del 'for' debe ser boolean, se recibió '{cond_type}'",
                    node
                )
        if node.step is not None:
            self.visit(node.step)

        prev_loop    = self.in_loop
        self.in_loop = True
        self.visit(node.body)
        self.in_loop = prev_loop
        self._exit_scope()

    def visit(self, node: WhileStmt):
        cond_type = None
        if node.cond is not None:
            cond_type = self.visit(node.cond)
        if cond_type and cond_type != 'boolean':
            self.sem_error(
                f"la condición del 'while' debe ser boolean, se recibió '{cond_type}'",
                node
            )
        prev_loop    = self.in_loop
        self.in_loop = True
        self.visit(node.body)
        self.in_loop = prev_loop

    def visit(self, node: Break):
        if not self.in_loop:
            self.sem_error("'break' fuera de un ciclo", node)

    def visit(self, node: Continue):
        if not self.in_loop:
            self.sem_error("'continue' fuera de un ciclo", node)

    # ===================================================
    # EXPRESIONES — retornan el tipo como str o None
    # ===================================================

    def visit(self, node: Literal):
        return _literal_type(node.kind)

    def visit(self, node: Name):
        if node.id == 'this':
            return None  # se manejará con info de clase
        sym = self._check_name(node.id, node)
        if sym is not None:
            return _type_name(sym.type)
        return None

    # --- Fase 3: validar operador binario ---
    def visit(self, node: BinOp):
        left_type  = self.visit(node.left)
        right_type = self.visit(node.right)

        # mapear operadores de token a símbolo
        op_map = {
            'LOR': '||', 'LAND': '&&',
            'EQ': '==',  'NE': '!=',
            'LT': '<',   'LE': '<=',
            'GT': '>',   'GE': '>=',
        }
        op = op_map.get(node.op, node.op)

        if left_type and right_type:
            result = check_binop(op, left_type, right_type)
            if result is None:
                self.sem_error(
                    f"operador '{op}' no aplicable a '{left_type}' y '{right_type}'",
                    node
                )
            return result
        return None

    # --- Fase 3: validar operador unario ---
    def visit(self, node: UnaryOp):
        expr_type = self.visit(node.expr)
        if expr_type:
            result = check_unaryop(node.op, expr_type)
            if result is None:
                self.sem_error(
                    f"operador unario '{node.op}' no aplicable a '{expr_type}'",
                    node
                )
            return result
        return None

    def visit(self, node: PostfixOp):
        return self.visit(node.expr)

    def visit(self, node: PrefixOp):
        return self.visit(node.expr)

    def visit(self, node: TernaryOp):
        cond_type = self.visit(node.cond)
        if cond_type and cond_type != 'boolean':
            self.sem_error(
                f"la condición del operador ternario debe ser boolean, se recibió '{cond_type}'",
                node
            )
        then_type = self.visit(node.then_val)
        else_type = self.visit(node.else_val)
        if then_type and else_type and then_type != else_type:
            self.sem_error(
                f"el operador ternario tiene ramas de tipos distintos: "
                f"'{then_type}' y '{else_type}'",
                node
            )
        return then_type

    # --- Fase 3: validar asignación ---
    def visit(self, node: Assign):
        target_type = self.visit(node.target)
        value_type  = self.visit(node.value)
        if target_type and value_type and target_type != value_type:
            self.sem_error(
                f"no se puede asignar '{value_type}' a una variable de tipo '{target_type}'",
                node
            )
        return target_type

    def visit(self, node: Index):
        base_type = self.visit(node.base)
        for idx in node.indices:
            idx_type = self.visit(idx)
            if idx_type and idx_type != 'integer':
                self.sem_error(
                    f"el índice de un arreglo debe ser integer, se recibió '{idx_type}'",
                    node
                )
        # retornar tipo elemento del arreglo
        if base_type and base_type.startswith('array'):
            # extraer tipo elemento
            sym = self.symtab.get(node.base.id) if isinstance(node.base, Name) else None
            if sym and isinstance(sym.type, (ArrayType, ArraySizedType)):
                return _type_name(sym.type.elem)
        return None

    # --- Fase 4: validar llamada a función ---
    def visit(self, node: Call):
        if node.func == 'super':
            for arg in node.args:
                self.visit(arg)
            return None

        sym = self._check_name(node.func, node)

        # visitar obj si existe (método)
        if node.obj is not None:
            self.visit(node.obj)

        # visitar argumentos y recolectar tipos
        arg_types = [self.visit(arg) for arg in node.args]

        if sym is None:
            return None

        # verificar que sea función
        if not isinstance(sym.type, FuncType):
            self.sem_error(
                f"'{node.func}' no es una función",
                node
            )
            return None

        func_type = sym.type

        # verificar cantidad de argumentos
        expected = len(func_type.params)
        received = len(node.args)
        if expected != received:
            self.sem_error(
                f"la función '{node.func}' espera {expected} argumento(s) "
                f"pero recibió {received}",
                node
            )
        else:
            # verificar tipos de argumentos
            for i, (param, arg_type) in enumerate(zip(func_type.params, arg_types)):
                param_type = _type_name(param.typ)
                if arg_type and param_type and arg_type != param_type:
                    self.sem_error(
                        f"argumento {i+1} de '{node.func}': "
                        f"se esperaba '{param_type}' pero se recibió '{arg_type}'",
                        node
                    )

        return _type_name(func_type.ret)

    def visit(self, node: FieldAccess):
        self.visit(node.obj)
        return None  # tipo de campo se resuelve con info de clase

    def visit(self, node: NewObject):
        sym = self.symtab.get(node.cls)
        if sym is None:
            self.sem_error(f"clase '{node.cls}' no definida", node)
        for arg in node.args:
            self.visit(arg)
        return node.cls  # retorna el nombre de la clase como tipo

    # Primitivos crudos que pueden colarse como índices
    def visit(self, node: int):   return 'integer'
    def visit(self, node: str):   return 'string'
    def visit(self, node: bool):  return 'boolean'
    def visit(self, node: float): return 'float'

# ===================================================
# Función de entrada
# ===================================================

def check(ast):
    """
    Ejecuta el análisis semántico completo (Fases 1‒4) sobre el AST.
    Retorna el Checker con la tabla de símbolos y lista de errores.
    """
    checker = Checker()
    checker.visit(ast)
    return checker