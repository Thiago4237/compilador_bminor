# grammar.py (versión actualizada para nuevo AST)
import logging
import sly
from rich import print

try:
	from .lexer  import Lexer
	from .errors import error, errors_detected, define_error
	from .model  import *
except ImportError:
	from lexer  import Lexer
	from errors import error, errors_detected, define_error
	from model  import *

def _L(node, lineno):
	node.lineno = lineno
	return node
	
	
class Parser(sly.Parser):
    
	log = logging.getLogger()
	log.setLevel(logging.ERROR)
	expected_shift_reduce = 1
	debugfile='grammar.txt'
	
	tokens = Lexer.tokens
	
	# =================================================
	# PROGRAMA
	# =================================================

	# program ::= decl_list 'EOF' 	
 
	@_("decl_list")
	def prog(self, p):
		return Program(p.decl_list)
	
	# =================================================
	# LISTAS DE DECLARACIONES
	# =================================================
	
	@_("decl decl_list")
	def decl_list(self, p):
		return [p.decl] + p.decl_list
		
	@_("empty")
	def decl_list(self, p):
		return []
		
	# =================================================
	# DECLARACIONES
	# =================================================
	
	@_("ID ':' type_simple ';'")
	def decl(self, p):
		return DeclTyped(p.ID, p.type_simple)
		
	@_("ID ':' type_array_sized ';'")
	def decl(self, p):
		return DeclTyped(p.ID, p.type_array_sized)
		
	@_("ID ':' type_func ';'")
	def decl(self, p):
		return DeclTyped(p.ID, p.type_func)
		
	@_("decl_init")
	def decl(self, p):
		return p.decl_init

	# =================================================
	# DECLARACIONES CLASES
	# =================================================		
	@_("ID ':' CLASS '=' '{' decl_list '}'")
	def decl(self, p):
		return DeclClass(p.ID, None, p.decl_list)

	@_("ID ':' CLASS EXTENDS ID '=' '{' decl_list '}'")
	def decl(self, p):
		return DeclClass(p.ID0, p.ID1, p.decl_list)
	
  
	# === DECLARACIONES con inicialización
	
	@_("ID ':' type_simple '=' expr ';'")
	def decl_init(self, p):
		return DeclInit(p.ID, p.type_simple, p.expr)
		
	@_("ID ':' CONSTANT '=' expr ';'")
	def decl_init(self, p):
		return DeclInit(p.ID, SimpleType("CONSTANT"), p.expr)
		
	@_("ID ':' type_array_sized '=' '{' opt_expr_list '}' ';'")
	def decl_init(self, p):
		return DeclInit(p.ID, p.type_array_sized, p.opt_expr_list)
		
	@_("ID ':' type_func '=' '{' opt_stmt_list '}'")
	def decl_init(self, p):
		return DeclInit(p.ID, p.type_func, p.opt_stmt_list)
		
	# =================================================
	# STATEMENTS
	# =================================================
	
	@_("stmt_list")
	def opt_stmt_list(self, p):
		return p.stmt_list
		
	@_("empty")
	def opt_stmt_list(self, p):
		return []
		
	@_("stmt stmt_list")
	def stmt_list(self, p):
		return [p.stmt] + p.stmt_list
		
	@_("stmt")
	def stmt_list(self, p):
		return [p.stmt]
		
	@_("open_stmt")
	@_("closed_stmt")
	def stmt(self, p):
		return p[0]

	@_("if_stmt_closed")
	@_("for_stmt_closed")
	@_("while_stmt_closed")
	@_("simple_stmt")
	def closed_stmt(self, p):
		return p[0]

	@_("if_stmt_open")
	@_("for_stmt_open")
	@_("while_stmt_open")
	def open_stmt(self, p):
		return p[0]

	# -------------------------------------------------
	# IF
	# -------------------------------------------------
	
	@_("IF '(' opt_expr ')'")
	def if_cond(self, p):
		return p.opt_expr
		
	@_("if_cond closed_stmt ELSE closed_stmt")
	def if_stmt_closed(self, p):
		return If(p.if_cond, p.closed_stmt0, p.closed_stmt1)
		
	@_("if_cond stmt")
	def if_stmt_open(self, p):
		return If(p.if_cond, p.stmt)
		
	@_("if_cond closed_stmt ELSE if_stmt_open")
	def if_stmt_open(self, p):
		return If(p.if_cond, p.closed_stmt, p.if_stmt_open)
		
	# -------------------------------------------------
	# FOR
	# -------------------------------------------------
	
	@_("FOR '(' opt_expr ';' opt_expr ';' opt_expr ')'")
	def for_header(self, p):
		return p.opt_expr0, p.opt_expr1, p.opt_expr2
		
	@_("for_header open_stmt")
	def for_stmt_open(self, p):
		init, cond, step = p.for_header
		return For(init, cond, step, p.open_stmt)
		
	@_("for_header closed_stmt")
	def for_stmt_closed(self, p):
		init, cond, step = p.for_header
		return For(init, cond, step, p.closed_stmt)
		
	# -------------------------------------------------
	# WHILE
	# -------------------------------------------------
	
	@_("WHILE '(' opt_expr ')'")
	def while_cond(self, p):
		return p.opt_expr
		
	@_("while_cond open_stmt")
	def while_stmt_open(self, p):
		return WhileStmt(p.while_cond, p.open_stmt)
		
	@_("while_cond closed_stmt")
	def while_stmt_closed(self, p):
		return WhileStmt(p.while_cond, p.closed_stmt)
		
	# -------------------------------------------------
	# SIMPLE STATEMENTS
	# -------------------------------------------------
	
	@_("print_stmt")
	@_("return_stmt")
	@_("break_stmt")
	@_("continue_stmt")
	@_("block_stmt")
	@_("decl")
	@_("expr ';'")
	def simple_stmt(self, p):
		return p[0]

	# PRINT
	@_("PRINT opt_expr_list ';'")
	def print_stmt(self, p):
		return Print(p.opt_expr_list)
		
	# RETURN
	@_("RETURN opt_expr ';'")
	def return_stmt(self, p):
		return Return(p.opt_expr)

	@_("BREAK ';'")
	def break_stmt(self, p):
		return Break()

	@_("CONTINUE ';'")
	def continue_stmt(self, p):
		return Continue()

	# BLOCK
	@_("'{' stmt_list '}'")
	def block_stmt(self, p):
		return Block(p.stmt_list)
		
	# =================================================
	# EXPRESIONES
	# =================================================
	
	@_("empty")
	def opt_expr_list(self, p):
		return []
		
	@_("expr_list")
	def opt_expr_list(self, p):
		return p.expr_list
		
	@_("expr ',' expr_list")
	def expr_list(self, p):
		return [p.expr] + p.expr_list
		
	@_("expr")
	def expr_list(self, p):
		return [p.expr]
		
	@_("empty")
	def opt_expr(self, p):
		return None
		
	@_("expr")
	def opt_expr(self, p):
		return p.expr
		
	# -------------------------------------------------
	# PRIMARY
	# -------------------------------------------------
	
	@_("expr1")
	def expr(self, p):
		return p.expr1
		
	@_("lval  '='  expr1")
	@_("lval ADDEQ expr1")
	@_("lval SUBEQ expr1")
	@_("lval MULEQ expr1")
	@_("lval DIVEQ expr1")
	@_("lval MODEQ expr1")
	def expr1(self, p):
		return Assign(p.lval, p.expr1)

	@_("postfix '.' ID '='    expr1")
	@_("postfix '.' ID ADDEQ  expr1")
	@_("postfix '.' ID SUBEQ  expr1")
	@_("postfix '.' ID MULEQ  expr1")
	@_("postfix '.' ID DIVEQ  expr1")
	@_("postfix '.' ID MODEQ  expr1")
	def expr1(self, p):
		return Assign(FieldAccess(p.postfix, p.ID), p.expr1)		

	@_("expr2")
	def expr1(self, p):
		return p.expr2
		
	# ----------- LVALUES -------------------
	
	@_("ID")
	def lval(self, p):
		return Name(p.ID)
		
	@_("ID index")
	def lval(self, p):
		return Index(Name(p.ID), [p.index])
 
	# -------------------------------------------------
	# OPERADORES
	# -------------------------------------------------
	
	@_("expr2 LOR expr3")
	def expr2(self, p):
		return BinOp('LOR', p.expr2, p.expr3)
		
	@_("expr3")
	def expr2(self, p):
		return p.expr3
		
	@_("expr3 LAND expr4")
	def expr3(self, p):
		return BinOp('LAND', p.expr3, p.expr4)
		
	@_("expr4")
	def expr3(self, p):
		return p.expr4
		
	@_("expr4 EQ expr5")
	@_("expr4 NE expr5")
	@_("expr4 LT expr5")
	@_("expr4 LE expr5")
	@_("expr4 GT expr5")
	@_("expr4 GE expr5")
	def expr4(self, p):
		return BinOp(p[1], p.expr4, p.expr5)

	@_("expr5")
	def expr4(self, p):
		return p.expr5
		
	@_("expr5 '+' expr6")
	@_("expr5 '-' expr6")
	def expr5(self, p):
		return BinOp(p[1], p.expr5, p.expr6)
		
	@_("expr6")
	def expr5(self, p):
		return p.expr6
		
	@_("expr6 '*' expr7")
	@_("expr6 '/' expr7")
	@_("expr6 '%' expr7")
	def expr6(self, p):
		return BinOp(p[1], p.expr6, p.expr7)
		
	@_("expr7")
	def expr6(self, p):
		return p.expr7
		
	@_("expr7 '^' expr8")
	def expr7(self, p):
		return BinOp('^', p.expr7, p.expr8)
		
	@_("expr8")
	def expr7(self, p):
		return p.expr8
		
	@_("'-' expr8")
	@_("'!' expr8")
	def expr8(self, p):
		return UnaryOp(p[0], p.expr8)

	@_("expr9")
	def expr8(self, p):
		return p.expr9

	@_("postfix")
	def expr9(self, p):
		return p.postfix

	@_("primary")
	def postfix(self, p):
		return p.primary

	@_("postfix INC")
	def postfix(self, p):
		return PostfixOp('INC', p.postfix)

	@_("postfix DEC")
	def postfix(self, p):
		return PostfixOp('DEC', p.postfix)

	@_("postfix '.' ID '(' opt_expr_list ')'")
	def postfix(self, p):
		return Call(p.ID, p.opt_expr_list, obj=FieldAccess(p.postfix, p.ID))

	@_("postfix '.' ID")
	def postfix(self, p):
		return FieldAccess(p.postfix, p.ID)

	@_("prefix")
	def primary(self, p):
		return p.prefix

	@_("INC prefix")
	def prefix(self, p):
		return PrefixOp(p.prefix, 'INC')

	@_("DEC prefix")
	def prefix(self, p):
		return PrefixOp(p.prefix, 'DEC')

	@_("group")
	def prefix(self, p):
		return p.group
		
	@_("'(' expr ')'")
	def group(self, p):
		return p.expr
		
	@_("ID '(' opt_expr_list ')'")
	def group(self, p):
		return Call(p.ID, p.opt_expr_list)
		
	@_("ID index")
	def group(self, p):
		return Index(Name(p.ID), [p.index])
		
	@_("factor")
	def group(self, p):
		return p.factor

	@_("NEW ID '(' opt_expr_list ')'")
	def group(self, p):
		return NewObject(p.ID, p.opt_expr_list)		

	@_("SUPER '(' opt_expr_list ')'")
	def group(self, p):
		return Call('super', p.opt_expr_list)

	# INDICE DE ARREGLO
	@_("'[' expr ']'")
	def index(self, p):
		return p.expr
	
	# -------------------------------------------------
	# FACTORES
	# -------------------------------------------------
	
	@_("ID")
	def factor(self, p):
		return Name(p.ID)
		
	@_("INTEGER_LITERAL")
	def factor(self, p):
		return Literal('int', p.INTEGER_LITERAL)
		
	@_("FLOAT_LITERAL")
	def factor(self, p):
		return Literal('float', p.FLOAT_LITERAL)
		
	@_("CHAR_LITERAL")
	def factor(self, p):
		return Literal('char', p.CHAR_LITERAL)
		
	@_("STRING_LITERAL")
	def factor(self, p):
		return Literal('string', p.STRING_LITERAL)
		
	@_("TRUE", "FALSE")
	def factor(self, p):
		return Literal('bool', p[0] == 'TRUE')
		
	@_("THIS")
	def factor(self, p):
		return Name('this')

	# =================================================
	# TIPOS
	# =================================================
	
	@_("INTEGER")
	@_("FLOAT")
	@_("BOOLEAN")
	@_("CHAR")
	@_("STRING")
	@_("VOID")
	def type_simple(self, p):
		return SimpleType(p[0])
		
	@_("ARRAY '[' ']' type_simple")
	@_("ARRAY '[' ']' type_array")
	def type_array(self, p):
		return ArrayType(p[3])          # ARRAY=0  [=1  ]=2  tipo=3
		
	@_("ARRAY index type_simple")
	@_("ARRAY index type_array_sized")
	def type_array_sized(self, p):
		return ArraySizedType(p[1], p[2])  # ARRAY=0  index=1  tipo=2
		
	@_("FUNCTION type_simple '(' opt_param_list ')'")
	@_("FUNCTION type_array_sized '(' opt_param_list ')'")
	def type_func(self, p):
		return FuncType(p[1], p[3])     # FUNCTION=0  tipo=1  (=2  params=3  )=4
		
	@_("empty")
	def opt_param_list(self, p):
		return []
		
	@_("param_list")
	def opt_param_list(self, p):
		return p.param_list
		
	@_("param_list ',' param")
	def param_list(self, p):
		return  p.param_list + [p.param]
		
	@_("param")
	def param_list(self, p):
		return [p.param]
		
	@_("ID ':' type_simple")
	def param(self, p):
		return Param(p.ID, p.type_simple)
		
	@_("ID ':' type_array")
	def param(self, p):
		return Param(p.ID, p.type_array)
		
	@_("ID ':' type_array_sized")
	def param(self, p):
		return Param(p.ID, p.type_array_sized)
		

	@_("ID")
	def type_class(self, p):
		return ClassType(p.ID)

	# extender las declaraciones para aceptar type_class
	@_("ID ':' type_class ';'")
	def decl(self, p):
		return DeclTyped(p.ID, p.type_class)

	@_("ID ':' type_class '=' expr ';'")
	def decl_init(self, p):
		return DeclInit(p.ID, p.type_class, p.expr)

	# parámetros también pueden ser de tipo clase
	@_("ID ':' type_class")
	def param(self, p):
		return Param(p.ID, p.type_class)

	# =================================================
	# UTILIDAD: EMPTY
	# =================================================
	
	@_("")
	def empty(self, p):
		pass
		
	def error(self, p):
		# llama la funcion que define de forma clara el error
		# info = define_error(p)
		# print(info)
		define_error(p, parser=self)
  
		# lineno = p.lineno if p else 'EOF'
		# value = repr(p.value) if p else 'EOF'
		# print(p)
		# error(f'Syntax error at {value}', lineno)
		
# ===================================================
# Utilidad: convertir algo en bloque si no lo es
# ===================================================
def as_block(x):
	if isinstance(x, Block):
		return x
	if isinstance(x, list):
		return Block(x)
	return Block([x])
	
	
# Convertir AST a diccionario
def ast_to_dict(node):
	if isinstance(node, list):
		return [ast_to_dict(item) for item in node]
	elif hasattr(node, "__dict__"):
		return {key: ast_to_dict(value) for key, value in node.__dict__.items()}
	else:
		return node

# ===================================================
# test
# ===================================================
def parse(txt):
    
	l = Lexer()
	p = Parser()
	return p.parse(l.tokenize(txt))
	
	
if __name__ == '__main__':
	
	import sys, os

	sys.path.insert(0, os.path.dirname(__file__))	
 
	if sys.platform != 'ios':
	
		if len(sys.argv) != 2:
			raise SystemExit("Usage: python parser.py test/<filename>")
			
		filename = sys.argv[1]
		
	else:
		from file_picker import file_picker_dialog
		
		filename = file_picker_dialog(
			title='Seleccionar una archivo',
			root_dir='./test/',
			file_pattern='^.*[.]bpp'
		)
		
	if filename:
		
		# --- salida ---
		os.makedirs('output', exist_ok=True)
		base = os.path.splitext(os.path.basename(filename))[0]
		Parser.debugfile = f'output/salida_{base}.txt'
		# --------------
		
		txt = open(filename, encoding='utf-8').read()
		ast = parse(txt)
		
		if not errors_detected():
			print(ast)
