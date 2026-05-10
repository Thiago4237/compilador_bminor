# ircode.py — Generador de Código Intermedio (IR)
# Adaptado al modelo AST de compilador_bminor+

from __future__ import annotations
from dataclasses import dataclass, field
from typing      import Optional
from multimethod import multimeta

try:
    from .model import *
except ImportError:
    from model import *

# ===================================================
# IR Model
# ===================================================

Instruction = tuple


@dataclass
class Storage:
    """Describe dónde vive un símbolo durante la generación de IR."""
    name:      str
    ty:        Any        # nodo Type del model.py
    is_global: bool = False
    is_param:  bool = False
    is_const:  bool = False


@dataclass
class IRFunction:
    name:         str
    params:       list[tuple[str, Any]]
    return_type:  Any
    instructions: list[Instruction] = field(default_factory=list)


@dataclass
class IRProgram:
    globals:   list[Instruction] = field(default_factory=list)
    functions: list[IRFunction]  = field(default_factory=list)

    def format(self) -> str:
        out: list[str] = []

        if self.globals:
            out.append("# Globals")
            for inst in self.globals:
                out.append(format_instruction(inst))
            out.append("")

        for fn in self.functions:
            params = ", ".join(f"{name}:{_type_str(ty)}" for name, ty in fn.params)
            out.append(f"function {fn.name}({params}) -> {_type_str(fn.return_type)}")
            for inst in fn.instructions:
                out.append(f"  {format_instruction(inst)}")
            out.append("")

        return "\n".join(out).rstrip()


# ===================================================
# Helpers
# ===================================================

def format_instruction(inst: Instruction) -> str:
    
    if len(inst) == 1 and isinstance(inst[0], tuple):
        inst = inst[0]

    op = inst[0]

    if op == 'LABEL':
        return f"{inst[1]}:"   # Lwhile1:

    if len(inst) == 1:
        return str(op)

    args = ", ".join(str(x) for x in inst[1:])
    return f"{op} {args}"


def _type_str(typ) -> str:
    """Convierte un nodo Type a string legible."""
    if isinstance(typ, SimpleType):
        return typ.name.lower()
    if isinstance(typ, ArrayType):
        return f'array[]{_type_str(typ.elem)}'
    if isinstance(typ, ArraySizedType):
        return f'array[n]{_type_str(typ.elem)}'
    if isinstance(typ, FuncType):
        return f'func->{_type_str(typ.ret)}'
    if isinstance(typ, ClassType):
        return typ.name
    return str(typ)


def _type_suffix(typ) -> str:
    """Sufijo de opcode según tipo."""
    if isinstance(typ, SimpleType):
        name = typ.name.lower()
        if name == 'integer': return 'I'
        if name == 'float':   return 'F'
        if name == 'boolean': return 'I'  # booleanos como enteros
        if name == 'char':    return 'B'
        if name == 'string':  return 'S'
        if name == 'void':    return 'V'
    if isinstance(typ, (ArrayType, ArraySizedType)):
        return 'A'
    return 'I'  # fallback


def _literal_kind_to_type(kind: str) -> SimpleType:
    mapping = {
        'int':    'integer',
        'float':  'float',
        'bool':   'boolean',
        'char':   'char',
        'string': 'string',
    }
    return SimpleType(mapping.get(kind, 'integer'))


# ===================================================
# Visitor base
# ===================================================

class Visitor(metaclass=multimeta):
    pass


# ===================================================
# Generador IR
# ===================================================

class IRCodeGen(Visitor):

    def __init__(self):
        self.program              = IRProgram()
        self.current_function: Optional[IRFunction] = None
        self.current_return_type  = SimpleType('void')
        self.temp_count           = 0
        self.label_count          = 0
        self.scopes: list[dict[str, Storage]] = []
        # Instrucciones de inicialización de globales que se inyectan
        # al inicio de main (el intérprete no ejecuta MOV*/STORE* en globals).
        self._global_inits: list[Instruction] = []
        self._emitting_global_init: bool = False  # True mientras se genera init de un global

    @classmethod
    def generate(cls, node: Program) -> IRProgram:
        gen = cls()
        gen.visit(node)
        return gen.program

    # -------------------------------------------------
    # Helpers básicos
    # -------------------------------------------------

    def new_temp(self) -> str:
        self.temp_count += 1
        return f"R{self.temp_count}"

    def new_label(self, prefix: str = "L") -> str:
        self.label_count += 1
        return f"{prefix}{self.label_count}"

    def emit(self, *inst) -> None:
        
        if len(inst) == 1 and isinstance(inst[0], tuple):
            inst = inst[0]
            
        inst = tuple(inst)
        
        if self._emitting_global_init:
            self._global_inits.append(inst)
        elif self.current_function is None:
            self.program.globals.append(inst)
        else:
            self.current_function.instructions.append(inst)

    def push_scope(self) -> None:
        self.scopes.append({})

    def pop_scope(self) -> None:
        self.scopes.pop()

    def bind(self, storage: Storage) -> None:
        if not self.scopes:
            self.push_scope()
        self.scopes[-1][storage.name] = storage

    def lookup(self, name: str) -> Optional[Storage]:
        for scope in reversed(self.scopes):
            if name in scope:
                return scope[name]
        return None

    # -------------------------------------------------
    # Opcodes por tipo
    # -------------------------------------------------

    def _sfx(self, typ) -> str:
        # Arrays se tratan como enteros (celdas aplanadas a escalares)
        if isinstance(typ, (ArrayType, ArraySizedType)):
            return 'I'
        return _type_suffix(typ)

    def mov_op(self, typ)   -> str: return f"MOV{self._sfx(typ)}"
    def load_op(self, typ)  -> str: return f"LOAD{self._sfx(typ)}"
    def store_op(self, typ) -> str: return f"STORE{self._sfx(typ)}"
    def alloc_op(self, typ) -> str: return f"ALLOC{self._sfx(typ)}"
    def var_op(self, typ)   -> str: return f"VAR{self._sfx(typ)}"
    def print_op(self, typ) -> str: return f"PRINT{self._sfx(typ)}"
    def cmp_op(self, typ)   -> str: return f"CMP{self._sfx(typ)}"
    
    def ret_op(self, typ)   -> str:
        sfx = self._sfx(typ)
        return "RET" if sfx == 'V' else f"RET{sfx}"

    def arith_op(self, op: str, typ) -> str:
        sfx = self._sfx(typ)
        table = {'+': f'ADD{sfx}', '-': f'SUB{sfx}',
                 '*': f'MUL{sfx}', '/': f'DIV{sfx}',
                 '%': f'MOD{sfx}', '^': f'POW{sfx}'}
        return table.get(op, f'OP{sfx}')

    def cmp_branch_op(self, op: str) -> tuple[str, str]:
        """Retorna (opcode_cmp, opcode_branch_si_falso)."""
        table = {
            '==': 'CMPEQ', '!=': 'CMPNE',
            '<':  'CMPLT', '<=': 'CMPLE',
            '>':  'CMPGT', '>=': 'CMPGE',
            'EQ': 'CMPEQ', 'NE': 'CMPNE',
            'LT': 'CMPLT', 'LE': 'CMPLE',
            'GT': 'CMPGT', 'GE': 'CMPGE',
        }
        return table.get(op, 'CMPEQ'), 'CBRANCH'

    # -------------------------------------------------
    # PROGRAMA
    # -------------------------------------------------

    def visit(self, node: Program):
        self.push_scope()

        # Primera pasada — registrar globals
        for decl in node.decls:
            if isinstance(decl, DeclTyped):
                self.bind(Storage(decl.name, decl.typ, is_global=True))
            elif isinstance(decl, DeclInit):
                is_const = isinstance(decl.typ, SimpleType) and decl.typ.name == 'CONSTANT'
                self.bind(Storage(decl.name, decl.typ, is_global=True, is_const=is_const))
            elif isinstance(decl, DeclClass):
                self.bind(Storage(decl.name, ClassType(decl.name), is_global=True))

        # Segunda pasada — generar IR
        for decl in node.decls:
            self.visit(decl)

        # Generar stubs vacíos para funciones declaradas sin cuerpo (forward declarations).
        # El intérprete necesita encontrar la función en self.functions al hacer CALL.
        defined_fns = {fn.name for fn in self.program.functions}
        for decl in node.decls:
            if (isinstance(decl, DeclTyped)
                    and isinstance(decl.typ, FuncType)
                    and decl.name not in defined_fns):
                stub = IRFunction(
                    name=decl.name,
                    params=[(p.name, p.typ) for p in decl.typ.params],
                    return_type=decl.typ.ret,
                )
                stub.instructions.append(("RET",))
                self.program.functions.append(stub)
                defined_fns.add(decl.name)

        # Si no hay función main, generarla (con las inits de globals si las hay).
        # El intérprete siempre llama main como punto de entrada.
        main_names = {fn.name for fn in self.program.functions}
        if "main" not in main_names:
            fn = IRFunction(
                name="main",
                params=[],
                return_type=SimpleType("void"),
            )
            for inst in self._global_inits:
                fn.instructions.append(inst)
            fn.instructions.append(("RET",))
            self.program.functions.append(fn)
            self._global_inits.clear()

        self.pop_scope()
        return self.program

    # -------------------------------------------------
    # DECLARACIONES
    # -------------------------------------------------

    def visit(self, node: DeclTyped):
        # Declaración sin inicialización — solo reservar espacio
        if self.current_function is None:
            # Funciones sin cuerpo y arrays no generan instrucción global
            if isinstance(node.typ, FuncType):
                return
            if not isinstance(node.typ, (ArrayType, ArraySizedType)):
                self.emit(self.var_op(node.typ), node.name)
        else:
            self.bind(Storage(node.name, node.typ))
            self.emit(self.alloc_op(node.typ), node.name)

    def visit(self, node: DeclInit):
        typ      = node.typ
        is_const = isinstance(typ, SimpleType) and typ.name == 'CONSTANT'
        is_func  = isinstance(typ, FuncType)

        if is_func:
            self._visit_func(node)
            return

        # Variable o constante
        if self.current_function is None:
            # Global: solo declarar la variable en program.globals
            # Arrays: el intérprete no soporta VARA; se omite la declaración
            if not isinstance(typ, (ArrayType, ArraySizedType)):
                self.emit(self.var_op(typ), node.name)
            if node.init is not None:
                # La inicialización se desvía al buffer _global_inits
                self._emitting_global_init = True
                try:
                    if isinstance(node.init, list):
                        self._init_array_global(node)
                    else:
                        src = self.visit(node.init)
                        self._global_inits.append(tuple([self.store_op(typ), src, node.name]))
                finally:
                    self._emitting_global_init = False
        else:
            # Local
            self.bind(Storage(node.name, typ, is_const=is_const))
            self.emit(self.alloc_op(typ), node.name)
            if node.init is not None:
                if isinstance(node.init, list):
                    self._init_array_local(node)
                else:
                    src = self.visit(node.init)
                    self.emit(self.store_op(typ), src, node.name)

    def _array_cell_name(self, arr_name: str, index) -> str:
        """Nombre de la variable escalar que representa arr_name[index]."""
        return f"{arr_name}_{index}"

    def _array_cell_store_op(self, elem_typ) -> str:
        """STORE* apropiado para el tipo de elemento del array."""
        if isinstance(elem_typ, (ArrayType, ArraySizedType)):
            return 'STOREI'  # puntero/referencia como entero
        return self.store_op(elem_typ)

    def _array_cell_load_op(self, elem_typ) -> str:
        """LOAD* apropiado para el tipo de elemento del array."""
        if isinstance(elem_typ, (ArrayType, ArraySizedType)):
            return 'LOADI'
        return self.load_op(elem_typ)

    def _array_cell_alloc_op(self, elem_typ) -> str:
        """ALLOC* apropiado para el tipo de elemento del array."""
        if isinstance(elem_typ, (ArrayType, ArraySizedType)):
            return 'ALLOCI'
        return self.alloc_op(elem_typ)

    def _array_cell_var_op(self, elem_typ) -> str:
        """VAR* apropiado para el tipo de elemento del array."""
        if isinstance(elem_typ, (ArrayType, ArraySizedType)):
            return 'VARI'
        return self.var_op(elem_typ)

    def _init_array_global(self, node: DeclInit):
        """Inicializa un arreglo global como variables escalares arr_0, arr_1…"""
        typ = node.typ
        elem_typ = typ.elem if isinstance(typ, (ArrayType, ArraySizedType)) else typ
        for i, elem in enumerate(node.init):
            cell = self._array_cell_name(node.name, i)
            # Declarar la celda en globals (fuera del buffer de inits)
            self._emitting_global_init = False
            self.emit(self._array_cell_var_op(elem_typ), cell)
            self._emitting_global_init = True
            src = self.visit(elem)
            self.emit(self._array_cell_store_op(elem_typ), src, cell)

    def _init_array_local(self, node: DeclInit):
        """Inicializa un arreglo local como variables escalares arr_0, arr_1…"""
        typ = node.typ
        elem_typ = typ.elem if isinstance(typ, (ArrayType, ArraySizedType)) else typ
        for i, elem in enumerate(node.init):
            cell = self._array_cell_name(node.name, i)
            self.emit(self._array_cell_alloc_op(elem_typ), cell)
            src = self.visit(elem)
            self.emit(self._array_cell_store_op(elem_typ), src, cell)

    def _visit_func(self, node: DeclInit):
        """Genera IR para una función."""
        prev_fn  = self.current_function
        prev_ret = self.current_return_type

        fn = IRFunction(
            name=node.name,
            params=[(p.name, p.typ) for p in node.typ.params],
            return_type=node.typ.ret,
        )
        self.program.functions.append(fn)
        self.current_function    = fn
        self.current_return_type = node.typ.ret

        self.push_scope()

        # Registrar parámetros
        for param in node.typ.params:
            self.bind(Storage(param.name, param.typ, is_param=True))
            self.emit(self.alloc_op(param.typ), param.name)

        # Inyectar inicializaciones de globales al inicio de main
        if node.name == "main" and self._global_inits:
            for init_inst in self._global_inits:
                fn.instructions.append(init_inst)
            self._global_inits.clear()

        # Generar cuerpo
        if node.init is not None:
            if isinstance(node.init, list):
                for stmt in node.init:
                    self.visit(stmt)
            else:
                self.visit(node.init)

        # RET implícito para funciones void
        ret_name = node.typ.ret.name.lower() if isinstance(node.typ.ret, SimpleType) else ''
        if ret_name == 'void':
            if not fn.instructions or fn.instructions[-1][0] not in ('RET', 'RETV'):
                self.emit('RET')

        self.pop_scope()
        self.current_function    = prev_fn
        self.current_return_type = prev_ret

    def visit(self, node: DeclClass):
        # Clases — generar métodos como funciones prefijadas
        for member in node.members:
            self.visit(member)

    def visit(self, node: ClassMember):
        self.visit(node.decl)

    def visit(self, node: ConstructorDecl):
        pass  # se implementa en extensión OOP

    def visit(self, node: GetterDecl):
        pass

    def visit(self, node: SetterDecl):
        pass

    # -------------------------------------------------
    # STATEMENTS
    # -------------------------------------------------

    def visit(self, node: Block):
        self.push_scope()
        for stmt in node.stmts:
            self.visit(stmt)
        self.pop_scope()

    def visit(self, node: Print):
        for val in node.values:
            reg = self.visit(val)
            # inferir tipo del valor
            typ = self._infer_type(val)
            self.emit(self.print_op(typ), reg)

    def visit(self, node: Return):
        if node.value is None:
            self.emit('RET')
            return
        reg = self.visit(node.value)
        sfx = self._sfx(self.current_return_type)
        self.emit(f'RET{sfx}', reg)

    def visit(self, node: If):
        
        l_then = self.new_label('Lthen')
        l_else = self.new_label('Lelse')
        l_end  = self.new_label('Lend')

        cond_reg = self.visit(node.cond)
        self.emit('CBRANCH', cond_reg, l_then, l_else)

        self.emit('LABEL', l_then)
        self.visit(node.then)
        self.emit('BRANCH', l_end)

        self.emit('LABEL', l_else)
        if node.otherwise is not None:
            self.visit(node.otherwise)

        self.emit('LABEL', l_end)
        
    def visit(self, node: WhileStmt):
        l_start = self.new_label('Lwhile')
        l_body  = self.new_label('Lbody')
        l_end   = self.new_label('Lend')

        self.emit('LABEL', l_start)
        cond_reg = self.visit(node.cond)
        self.emit('CBRANCH', cond_reg, l_body, l_end)  # true→body, false→end

        self.emit('LABEL', l_body)
        self.visit(node.body)
        self.emit('BRANCH', l_start)

        self.emit('LABEL', l_end)

    def visit(self, node: For):
        
        l_start = self.new_label('Lfor')
        l_body  = self.new_label('Lbody')
        l_end   = self.new_label('Lend')

        self.push_scope()

        if node.init is not None:
            self.visit(node.init)

        self.emit('LABEL', l_start)

        if node.cond is not None:
            cond_reg = self.visit(node.cond)
            self.emit('CBRANCH', cond_reg, l_body, l_end)

        self.emit('LABEL', l_body)
        self.visit(node.body)

        if node.step is not None:
            self.visit(node.step)

        self.emit('BRANCH', l_start)
        self.emit('LABEL', l_end)

        self.pop_scope()

    def visit(self, node: Break):
        # En una implementación completa se necesita la label del loop actual
        self.emit('BREAK')

    def visit(self, node: Continue):
        self.emit('CONTINUE')

    # -------------------------------------------------
    # EXPRESIONES — retornan registro con el resultado
    # -------------------------------------------------

    def visit(self, node: Literal):
        tmp  = self.new_temp()
        kind = node.kind
        if kind == 'int':
            self.emit('MOVI', int(node.value), tmp)
        elif kind == 'float':
            self.emit('MOVF', float(node.value), tmp)
        elif kind == 'bool':
            val = 1 if node.value is True or node.value == 'true' or node.value == '1' else 0
            self.emit('MOVI', val, tmp)
        elif kind == 'char':
            # extraer el carácter entre comillas simples
            raw = node.value.strip("'")
            val = ord(raw[0]) if raw else 0
            self.emit('MOVB', val, tmp)
        elif kind == 'string':
            self.emit('MOVS', node.value, tmp)
        return tmp

    def visit(self, node: Name):
        if node.id == 'this':
            return 'this'
        storage = self.lookup(node.id)
        if storage is None:
            return self.new_temp()  # fallback
        tmp = self.new_temp()
        self.emit(self.load_op(storage.ty), storage.name, tmp)
        return tmp

    def visit(self, node: BinOp):
        left_reg  = self.visit(node.left)
        right_reg = self.visit(node.right)
        left_typ  = self._infer_type(node.left)
        out       = self.new_temp()

        # Aritmética
        if node.op in {'+', '-', '*', '/', '%', '^'}:
            opcode = self.arith_op(node.op, left_typ)
            self.emit(opcode, left_reg, right_reg, out)
            return out

        # Comparaciones
        op_map = {
            'EQ': '==', 'NE': '!=',
            'LT': '<',  'LE': '<=',
            'GT': '>',  'GE': '>=',
        }
        op = op_map.get(node.op, node.op)

        if op in {'==', '!=', '<', '<=', '>', '>='}:
            op_map_interp = {
                '==': '==', '!=': '!=',
                '<':  '<',  '<=': '<=',
                '>':  '>',  '>=': '>=',
            }
            self.emit(self.cmp_op(left_typ), op_map_interp[op], left_reg, right_reg, out)
            return out

        # Lógicos — cortocircuito
        # LOR
        if node.op in ('LOR', '||'):
            l_true  = self.new_label('Lor_true')
            l_check = self.new_label('Lor_check')
            l_end   = self.new_label('Lor_end')
            self.emit('CBRANCH', left_reg, l_true, l_check)
            self.emit('LABEL', l_check)
            right2 = self.visit(node.right)
            self.emit('PHI', right2, out)
            self.emit('BRANCH', l_end)
            self.emit('LABEL', l_true)
            self.emit('MOVI', 1, out)
            self.emit('LABEL', l_end)
            return out

        # LAND
        if node.op in ('LAND', '&&'):
            l_check = self.new_label('Land_check')
            l_false = self.new_label('Land_false')
            l_end   = self.new_label('Land_end')
            self.emit('CBRANCH', left_reg, l_check, l_false)
            self.emit('LABEL', l_check)
            right2 = self.visit(node.right)
            self.emit('PHI', right2, out)
            self.emit('BRANCH', l_end)
            self.emit('LABEL', l_false)
            self.emit('MOVI', 0, out)
            self.emit('LABEL', l_end)
            return out

        # Fallback
        self.emit(f'OP_{node.op}', left_reg, right_reg, out)
        return out

    def visit(self, node: UnaryOp):
        typ = self._infer_type(node.expr)
        out = self.new_temp()

        if node.op == '-':
            # Optimización: literal negativo → MOV directo, sin SUBI
            if isinstance(node.expr, Literal):
                if node.expr.kind == 'int':
                    self.emit('MOVI', -int(node.expr.value), out)
                    return out
                if node.expr.kind == 'float':
                    self.emit('MOVF', -float(node.expr.value), out)
                    return out
            reg  = self.visit(node.expr)
            zero = self.new_temp()
            self.emit(self.mov_op(typ), 0, zero)
            self.emit(self.arith_op('-', typ), zero, reg, out)
            return out

        if node.op == '!':
            self.emit('NOT', reg, out)
            return out

        if node.op == '+':
            return reg  # no-op

        self.emit(f'UNARY_{node.op}', reg, out)
        return out

    def visit(self, node: PostfixOp):
        """x++ / x-- — carga valor, opera, guarda."""
        if not isinstance(node.expr, Name):
            return self.new_temp()

        storage = self.lookup(node.expr.id)
        if storage is None:
            return self.new_temp()

        tmp = self.new_temp()
        self.emit(self.load_op(storage.ty), storage.name, tmp)

        one = self.new_temp()
        self.emit('MOVI', 1, one)
        result = self.new_temp()

        op = '+' if node.op == 'INC' else '-'
        self.emit(self.arith_op(op, storage.ty), tmp, one, result)
        self.emit(self.store_op(storage.ty), result, storage.name)

        return tmp  # retorna valor ANTES de la operación

    def visit(self, node: PrefixOp):
        """++x / --x — opera primero, luego retorna nuevo valor."""
        if not isinstance(node.expr, Name):
            return self.new_temp()

        storage = self.lookup(node.expr.id)
        if storage is None:
            return self.new_temp()

        tmp = self.new_temp()
        self.emit(self.load_op(storage.ty), storage.name, tmp)

        one = self.new_temp()
        self.emit('MOVI', 1, one)
        result = self.new_temp()

        op = '+' if node.op == 'INC' else '-'
        self.emit(self.arith_op(op, storage.ty), tmp, one, result)
        self.emit(self.store_op(storage.ty), result, storage.name)

        return result  # retorna valor DESPUÉS de la operación

    def visit(self, node: TernaryOp):
        l_then = self.new_label('Ltern_then')
        l_else = self.new_label('Ltern_else')
        l_end  = self.new_label('Ltern_end')
        out    = self.new_temp()

        cond_reg = self.visit(node.cond)
        self.emit('CBRANCH', cond_reg, l_then, l_else)

        self.emit('LABEL', l_then)
        then_reg = self.visit(node.then_val)
        typ      = self._infer_type(node.then_val)
        self.emit(self.mov_op(typ), then_reg, out)
        self.emit('BRANCH', l_end)

        self.emit('LABEL', l_else)
        else_reg = self.visit(node.else_val)
        self.emit(self.mov_op(typ), else_reg, out)

        self.emit('LABEL', l_end)
        return out

    def visit(self, node: Assign):
        """Asignación simple y compuesta."""
        src = self.visit(node.value)

        # Asignación a variable simple
        if isinstance(node.target, Name):
            storage = self.lookup(node.target.id)
            if storage:
                self.emit(self.store_op(storage.ty), src, storage.name)
            return src

        # Asignación a campo de objeto
        if isinstance(node.target, FieldAccess):
            obj_reg = self.visit(node.target.obj)
            self.emit('STOREFIELD', src, obj_reg, node.target.field)
            return src

        # Asignación a índice de arreglo
        if isinstance(node.target, Index):
            if isinstance(node.target.base, Name):
                arr_name = node.target.base.id
                storage  = self.lookup(arr_name)
                arr_typ  = storage.ty if storage else None
                elem_typ = arr_typ.elem if isinstance(arr_typ, (ArrayType, ArraySizedType)) else None

                if isinstance(node.target.indices[0], Literal) and node.target.indices[0].kind == 'int':
                    idx  = int(node.target.indices[0].value)
                    cell = self._array_cell_name(arr_name, idx)
                    sop  = self._array_cell_store_op(elem_typ) if elem_typ else 'STOREI'
                    self.emit(sop, src, cell)
                    return src

            # Fallback genérico (índice dinámico)
            base_reg = self.visit(node.target.base)
            idx_reg  = self.visit(node.target.indices[0])
            self.emit('STOREA', src, base_reg, idx_reg)
            return src

        return src

    def visit(self, node: Index):
        """Acceso a elemento de arreglo — aplanado a variable escalar arr_N."""
        # Solo soportamos índice literal o nombre de variable con valor constante conocido.
        # Para índices literales enteros usamos la celda arr_N directamente.
        if isinstance(node.base, Name):
            arr_name = node.base.id
            storage  = self.lookup(arr_name)
            arr_typ  = storage.ty if storage else None
            elem_typ = arr_typ.elem if isinstance(arr_typ, (ArrayType, ArraySizedType)) else None

            if isinstance(node.indices[0], Literal) and node.indices[0].kind == 'int':
                idx  = int(node.indices[0].value)
                cell = self._array_cell_name(arr_name, idx)
                out  = self.new_temp()
                lop  = self._array_cell_load_op(elem_typ) if elem_typ else 'LOADI'
                self.emit(lop, cell, out)
                return out

        # Fallback genérico (índice dinámico) — emite LOADA igual que antes
        base_reg = self.visit(node.base)
        idx_reg  = self.visit(node.indices[0])
        out      = self.new_temp()
        self.emit('LOADA', base_reg, idx_reg, out)
        return out

    def visit(self, node: Call):
        """Llamada a función."""
        # Evaluar argumentos
        arg_regs = [self.visit(arg) for arg in node.args]

        # Llamada a método de objeto
        if node.obj is not None:
            obj_reg = self.visit(node.obj)
            out     = self.new_temp()
            self.emit('CALLMETHOD', obj_reg, node.func, *arg_regs, out)
            return out

        # Llamada a función global
        out = self.new_temp()
        self.emit('CALL', node.func, *arg_regs, out)
        return out

    def visit(self, node: FieldAccess):
        """Acceso a campo de objeto."""
        obj_reg = self.visit(node.obj)
        out     = self.new_temp()
        self.emit('LOADFIELD', obj_reg, node.field, out)
        return out

    def visit(self, node: NewObject):
        """Instanciación de objeto."""
        arg_regs = [self.visit(arg) for arg in node.args]
        out      = self.new_temp()
        self.emit('NEW', node.cls, *arg_regs, out)
        return out

    # -------------------------------------------------
    # Inferencia de tipo para opcodes
    # -------------------------------------------------

    def _infer_type(self, node) -> Any:
        """Infiere el tipo de un nodo expresión para elegir el opcode correcto."""
        if isinstance(node, Literal):
            return _literal_kind_to_type(node.kind)
        if isinstance(node, Name):
            s = self.lookup(node.id)
            return s.ty if s else SimpleType('integer')
        if isinstance(node, BinOp):
            return self._infer_type(node.left)
        if isinstance(node, Assign):
            return self._infer_type(node.target)
        if isinstance(node, Index):
            base_typ = self._infer_type(node.base)
            if isinstance(base_typ, (ArrayType, ArraySizedType)):
                return base_typ.elem
        if isinstance(node, Call):
            s = self.lookup(node.func)
            if s and isinstance(s.ty, FuncType):
                return s.ty.ret
        return SimpleType('integer')

    # Primitivos que pueden colarse
    def visit(self, node: int):
        tmp = self.new_temp()
        self.emit('MOVI', node, tmp)
        return tmp

    def visit(self, node: float):
        tmp = self.new_temp()
        self.emit('MOVF', node, tmp)
        return tmp

    def visit(self, node: bool):
        tmp = self.new_temp()
        self.emit('MOVI', 1 if node else 0, tmp)
        return tmp

    def visit(self, node: str):
        tmp = self.new_temp()
        self.emit('MOVS', node, tmp)
        return tmp


# ===================================================
# Función de entrada
# ===================================================

def generate_ir(ast: Program) -> IRProgram:
    
    """Genera el IR a partir del AST ya verificado semánticamente."""
    return IRCodeGen.generate(ast)