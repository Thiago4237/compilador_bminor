from __future__ import annotations
from dataclasses import dataclass
from typing import Any, Optional, List, Union

# ===================================================
# AST (dataclasses)
# ===================================================

# ---------- Types ----------
class Type: ...

@dataclass(frozen=True)
class SimpleType(Type):
	name: str  # INTEGER, FLOAT, BOOLEAN, CHAR, STRING, VOID
	
@dataclass(frozen=True)
class ArrayType(Type):
	# type_array ::= ARRAY [ ] type_simple | ARRAY [ ] type_array
	elem: Type
	
@dataclass(frozen=True)
class ArraySizedType(Type):
	# type_array_sized ::= ARRAY index type_simple | ARRAY index type_array_sized
	size_expr: "Expr"
	elem: Type  # SimpleType o ArraySizedType (recursivo)
	
@dataclass(frozen=True)
class FuncType(Type):
	# type_func ::= FUNCTION type_simple '(' opt_param_list ')'
	#           |  FUNCTION type_array_sized '(' opt_param_list ')'
	ret: Type
	params: List["Param"]

@dataclass(frozen=True)
class ClassType(Type):
	name: str

@dataclass(frozen=True)
class Param:
	name: str
	typ: Type
	
# ---------- Program / Decl ----------
class Decl: ...

@dataclass
class Program:
	decls: List[Decl]
	
@dataclass
class DeclTyped(Decl):
	# decl ::= ID ':' type_simple ';' | ID ':' type_array_sized ';' | ID ':' type_func ';'
	name: str
	typ: Type
	
@dataclass
class DeclInit(Decl):
	# decl_init ::= ID ':' type_simple '=' expr ';'
	#            |  ID ':' type_array_sized '=' '{' opt_expr_list '}' ';'
	#            |  ID ':' type_func '=' '{' opt_stmt_list '}'
	name: str
	typ: Type
	init: Any  # Expr | List[Expr] | List[Stmt]

@dataclass
class DeclClass(Decl):
	name:    str
	parent:  Optional[str]
	members: List["ClassMember"]

# ---------- OOP ----------
 
@dataclass
class AccessModifier:
	kind: str  # 'public', 'private', 'protected'
 
@dataclass
class ClassMember:
	modifier: Optional[AccessModifier]
	decl:     Any
 
@dataclass
class ConstructorDecl(Decl):
	params: List[Param]
	body:   List
 
@dataclass
class GetterDecl(Decl):
	name: str
	ret:  Type
	body: List
 
@dataclass
class SetterDecl(Decl):
	name:  str
	param: Param
	body:  List

# ---------- Stmt ----------
class Stmt: ...

@dataclass
class Print(Stmt):
	values: List["Expr"]
	
@dataclass
class Return(Stmt):
	value: Optional["Expr"]
	
@dataclass
class Block(Stmt):
	stmts: List[Union[Stmt, Decl]]  # en tu gramática: stmt puede ser decl (simple_stmt)
	
@dataclass
class ExprStmt(Stmt):
	expr: "Expr"
	
@dataclass
class If(Stmt):
	cond: Optional["Expr"]     # if_cond usa opt_expr
	then: Stmt
	otherwise: Optional[Stmt] = None
	
@dataclass
class For(Stmt):
	init: Optional["Expr"]
	cond: Optional["Expr"]
	step: Optional["Expr"]
	body: Stmt

@dataclass
class WhileStmt(Stmt):
	cond: Optional["Expr"]
	body: Stmt

@dataclass
class Break(Stmt):
	pass
 
@dataclass
class Continue(Stmt):
	pass

# ---------- Expr ----------
class Expr: ...

@dataclass
class Name(Expr):
	id: str
	
@dataclass
class Literal(Expr):
	kind: str
	value: Any
	
@dataclass
class Index(Expr):
	base: Expr         # típicamente Name(...)
	indices: List[Expr]  # index_list
	
@dataclass
class Call(Expr):
	func: str          # grammar: ID '(' opt_expr_list ')'
	args: List[Expr]
	obj:  Optional[Expr] = None
	
@dataclass
class Assign(Expr):
	target: Expr       # lval
	value: Expr
	
@dataclass
class BinOp(Expr):
	op: str
	left: Expr
	right: Expr
	
@dataclass
class UnaryOp(Expr):
	op: str
	expr: Expr
	
@dataclass
class PostfixOp(Expr):
	op: str  # INC/DEC
	expr: Expr
	
@dataclass
class PrefixOp(Expr):
	expr: Expr
	op: str  # INC/DEC
 
# Operador ternario
@dataclass
class TernaryOp(Expr):
    cond:      Expr
    then_val:  Expr
    else_val:  Expr

@dataclass
class FieldAccess(Expr):
    # expr '.' ID   →  a.run()  se parsea como Call sobre FieldAccess
    obj:   Expr
    field: str

@dataclass
class NewObject(Expr):
    # NEW ID '(' opt_expr_list ')'
    cls:  str
    args: List[Expr]
