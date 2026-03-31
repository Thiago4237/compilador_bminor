# checker.py — Fase 1
# Tabla de símbolos + declaraciones globales + identificadores no definidos

from dataclasses import dataclass
from typing      import Any
from multimethod import multimeta

try:
    from .symtab import Symtab
    from .model  import *
    from .errors import error as report_error
except ImportError:
    from symtab import Symtab
    from model  import *
    from errors import error as report_error

# ===================================================
# Símbolo semántico
# ===================================================

@dataclass
class Symbol:
    name: str
    kind: str   # 'variable', 'function', 'parameter', 'class'
    type: Any   # nodo Type del model.py
    node: Any   # nodo AST original

    def __repr__(self):
        return f"Symbol(name={self.name!r}, kind={self.kind!r}, type={self.type!r})"

# ===================================================
# Visitor base con multimethod
# ===================================================

class Visitor(metaclass=multimeta):
    pass

# ===================================================
# Checker — Fase 1
# ===================================================

class Checker(Visitor):

    def __init__(self):
        self.symtab  = Symtab('global')
        self.errors  = []

    # ---------------------------------------------------
    # Reporte de errores semánticos
    # ---------------------------------------------------

    def sem_error(self, msg, node=None):
        lineno = getattr(node, 'lineno', None)
        full   = f"[semántico] {msg}"
        self.errors.append(full)
        report_error(full, lineno)

    # ---------------------------------------------------
    # Helpers
    # ---------------------------------------------------

    def _add_symbol(self, name, kind, typ, node):
        """Registra un símbolo en el scope actual, reportando redefinición."""
        sym = Symbol(name, kind, typ, node)
        try:
            self.symtab.add(name, sym)
        except Symtab.SymbolDefinedError:
            self.sem_error(
                f"'{name}' ya está declarado en este alcance",
                node
            )
        except Symtab.SymbolConflictError:
            self.sem_error(
                f"'{name}' ya está declarado con un tipo distinto en este alcance",
                node
            )
        return sym

    def _check_name(self, name, node):
        """Verifica que un identificador esté definido."""
        sym = self.symtab.get(name)
        if sym is None:
            self.sem_error(f"símbolo '{name}' no definido", node)
        return sym

    def _visit_list(self, nodes):
        """Visita una lista de nodos."""
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
        # Determinar kind
        if isinstance(node.typ, FuncType):
            kind = 'function'
        elif isinstance(node.typ, SimpleType) and node.typ.name == 'CONSTANT':
            kind = 'constant'
        else:
            kind = 'variable'

        # Registrar símbolo ANTES de visitar el init
        # (permite recursión y forward references en funciones)
        self._add_symbol(node.name, kind, node.typ, node)

        # Visitar inicializador
        if node.init is not None:
            if isinstance(node.init, list):
                self._visit_list(node.init)
            else:
                self.visit(node.init)

    def visit(self, node: DeclClass):
        self._add_symbol(node.name, 'class', ClassType(node.name), node)
        # Los miembros se visitarán en Fase 2 con su propio scope

    # ===================================================
    # STATEMENTS
    # ===================================================

    def visit(self, node: Block):
        self._visit_list(node.stmts)

    def visit(self, node: Print):
        self._visit_list(node.values)

    def visit(self, node: Return):
        if node.value is not None:
            self.visit(node.value)

    def visit(self, node: If):
        if node.cond is not None:
            self.visit(node.cond)
        self.visit(node.then)
        if node.otherwise is not None:
            self.visit(node.otherwise)

    def visit(self, node: For):
        if node.init is not None:
            self.visit(node.init)
        if node.cond is not None:
            self.visit(node.cond)
        if node.step is not None:
            self.visit(node.step)
        self.visit(node.body)

    def visit(self, node: WhileStmt):
        if node.cond is not None:
            self.visit(node.cond)
        self.visit(node.body)

    def visit(self, node: Break):
        pass

    def visit(self, node: Continue):
        pass

    # ===================================================
    # EXPRESIONES
    # ===================================================

    def visit(self, node: Literal):
        pass  # los literales no tienen IDs

    def visit(self, node: Name):
        # 'this' es válido dentro de clases — se manejará en Fase 2
        if node.id == 'this':
            return
        return self._check_name(node.id, node)

    def visit(self, node: BinOp):
        self.visit(node.left)
        self.visit(node.right)

    def visit(self, node: UnaryOp):
        self.visit(node.expr)

    def visit(self, node: PostfixOp):
        self.visit(node.expr)

    def visit(self, node: PrefixOp):
        self.visit(node.expr)

    def visit(self, node: TernaryOp):
        self.visit(node.cond)
        self.visit(node.then_val)
        self.visit(node.else_val)

    def visit(self, node: Assign):
        self.visit(node.target)
        self.visit(node.value)

    def visit(self, node: Index):
        self.visit(node.base)
        for idx in node.indices:
            self.visit(idx)

    def visit(self, node: Call):
        # 'super' es especial — se maneja en Fase 2
        if node.func != 'super':
            self._check_name(node.func, node)
        for arg in node.args:
            self.visit(arg)
        if node.obj is not None:
            self.visit(node.obj)

    def visit(self, node: FieldAccess):
        self.visit(node.obj)
        # el campo se verificará en Fase 2 cuando tengamos info de clases

    def visit(self, node: NewObject):
        # verificar que la clase exista
        sym = self.symtab.get(node.cls)
        if sym is None:
            self.sem_error(f"clase '{node.cls}' no definida", node)
        for arg in node.args:
            self.visit(arg)

    def visit(self, node: int):
        pass  # índice numérico crudo, ignorar

    def visit(self, node: str):
        pass  # string crudo, ignorar

    def visit(self, node: bool):
        pass  # bool crudo, ignorar

    def visit(self, node: float):
        pass  # float crudo, ignorar

# ===================================================
# Función de entrada
# ===================================================

def check(ast):
    """
    Ejecuta el análisis semántico Fase 1 sobre el AST.
    Retorna el Checker con la tabla de símbolos y lista de errores.
    """
    checker = Checker()
    checker.visit(ast)
    return checker