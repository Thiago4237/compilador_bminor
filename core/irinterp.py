from __future__ import annotations

from dataclasses import dataclass, field
from os import name
from typing import Any, Optional


class IRRuntimeError(RuntimeError):
	pass
	
	
@dataclass
class Frame:
	name: str
	instructions: list[tuple]
	params: list[tuple[str, Any]] = field(default_factory=list)
	locals: dict[str, Any] = field(default_factory=dict)
	regs: dict[str, Any] = field(default_factory=dict)
	labels: dict[str, int] = field(default_factory=dict)
	pc: int = 0
	
	def __post_init__(self):
		self.labels = {
			inst[1]: i
			for i, inst in enumerate(self.instructions)
			if inst and inst[0] == "LABEL"
		}
		
		
class IRInterpreter:
	'''
	Intérprete para el IR generado por ircode_strings_bytes.py.
	
	Soporta:
	- enteros, flotantes, bytes/chars y booleanos como enteros 0/1
	- variables globales y locales
	- funciones, CALL y RET
	- flujo de control: LABEL, BRANCH, CBRANCH
	- strings como arreglos globales de bytes: DATAS + ADDR + PRINTS
	- PHI simple: toma el primer registro existente entre sus entradas
	'''
	
	def __init__(self, program, trace: bool = False):
		self.program = program
		self.trace = trace
		self.globals: dict[str, Any] = {}
		self.data: dict[str, list[int]] = {}
		self.functions = {fn.name: fn for fn in getattr(program, "functions", [])}
		self.output: list[str] = []
		self._load_globals()
		
	# -------------------------------------------------
	# API pública
	# -------------------------------------------------
	
	def run(self, name: str = "main", *args):
		return self.call(name, list(args))
		
	def call(self, name: str, args: list[Any]):
		if name not in self.functions:
			raise IRRuntimeError(f"Función no encontrada: {name}")
			
		fn = self.functions[name]
		params = getattr(fn, "params", [])
		if len(args) != len(params):
			raise IRRuntimeError(
				f"La función {name} espera {len(params)} argumento(s), recibió {len(args)}"
			)
			
		frame = Frame(
			name=name,
			instructions=list(getattr(fn, "instructions", [])),
			params=list(params),
		)
		
		# Los parámetros se modelan como variables locales ya inicializadas.
		for (pname, _pty), value in zip(params, args):
			frame.locals[pname] = value
			
		return self._execute_frame(frame)
		
	# -------------------------------------------------
	# Carga de datos globales
	# -------------------------------------------------
	
	def _load_globals(self):
		for inst in getattr(self.program, "globals", []):
			self._exec_global(inst)
			
	def _exec_global(self, inst: tuple):
		op = inst[0]
		
		if op == "DATAS":
			_, name, *values = inst
			self.data[name] = [int(v) for v in values]
			return
			
		if op in {"VARI", "VARF", "VARB", "VARS"}:
			_, name = inst
			self.globals.setdefault(name, self._default_for_op(op))
			return
			
		if op.startswith("MOV"):
			# Normalmente MOV no aparece en globals, pero lo soportamos
			# por compatibilidad si el generador lo emite allí.
			return
			
		if op.startswith("STORE"):
			# En globals, STORE solo funcionaría si antes hubo registros.
			# Esta versión no mantiene registros globales. Para inicialización
			# global compleja se recomienda moverla a main o extender esta fase.
			raise IRRuntimeError(
				f"Inicialización global con {op} no soportada directamente: {inst}"
			)
			
		raise IRRuntimeError(f"Instrucción global no soportada: {inst}")
		
	def _default_for_op(self, op: str):
		if op.endswith("F"):
			return 0.0
		if op.endswith("S"):
			return None
		return 0
		
	# -------------------------------------------------
	# Ejecución
	# -------------------------------------------------
	
	def _execute_frame(self, frame: Frame):
		insts = frame.instructions
		
		while frame.pc < len(insts):
			inst = insts[frame.pc]
			current_pc = frame.pc
			frame.pc += 1
			
			if self.trace:
				print(f"[TRACE] {frame.name}:{current_pc:04d} {inst}")
				
			try:
				result = self._dispatch(frame, inst)
			except IRRuntimeError as exc:
				raise IRRuntimeError(
					f"{exc}\n"
					f"  función: {frame.name}\n"
					f"  pc: {current_pc}\n"
					f"  instrucción: {inst}\n"
					f"  locals: {frame.locals}\n"
					f"  regs: {frame.regs}"
				) from None
			if isinstance(result, _Return):
				return result.value
				
		return None
		
	def _dispatch(self, frame: Frame, inst: tuple):
		if not inst:
			return None
			
		op = inst[0]
		
		# -------------------------
		# Datos y direcciones
		# -------------------------
		if op == "DATAS":
			_, name, *values = inst
			self.data[name] = [int(v) for v in values]
			return None
			
		if op == "ADDR":
			_, name, target = inst
			if name not in self.data:
				raise IRRuntimeError(f"Bloque de datos no encontrado: {name}")
			frame.regs[target] = name
			return None
			
		# -------------------------
		# Variables locales/globales
		# -------------------------
		if op in {"ALLOCI", "ALLOCF", "ALLOCB", "ALLOCS", "ALLOCA"}:
			_, name = inst
			if op == "ALLOCA":
				frame.locals.setdefault(name, {})
			else:
				# No borrar parámetros ya inicializados.
				frame.locals.setdefault(name, self._default_for_op(op))
			return None
			
		if op in {"VARI", "VARF", "VARB", "VARS"}:
			_, name = inst
			self.globals.setdefault(name, self._default_for_op(op))
			return None
			
		if op in {"LOADI", "LOADF", "LOADB", "LOADS"}:
			_, name, target = inst
			frame.regs[target] = self._load_var(frame, name)
			return None
			
		if op in {"STOREI", "STOREF", "STOREB", "STORES"}:
			_, source, name = inst
			self._store_var(frame, name, self._value(frame, source))
			return None

					# STOREA src, name, index
		if op == "STOREA":
			_, src, name, idx = inst
			value = self._value(frame, src)
			index = self._value(frame, idx) if isinstance(idx, str) else int(idx)
			arr = self._load_var(frame, name)
			if not isinstance(arr, dict):
				arr = {}
				self._store_var(frame, name, arr)
			arr[index] = value
			return None

		if op == "LOADA":
			_, base, idx, target = inst
			arr_val = self._value(frame, base)
			index = self._value(frame, idx)
			index = int(index) if not isinstance(index, int) else index

			# Caso 1: el registro ya contiene el dict reconstruido
			if isinstance(arr_val, dict):
				frame.regs[target] = arr_val.get(index, 0)
				return None

			# Caso 2: arr_val es un string con el nombre base del arreglo
			# → buscar celda aplanada: name_0, name_1, etc.
			name = arr_val
			cell = f"{name}_{index}"
			if cell in frame.locals:
				frame.regs[target] = frame.locals[cell]
			elif cell in self.globals:
				frame.regs[target] = self.globals[cell]
			else:
				frame.regs[target] = 0
			return None

		if op == "STOREA":
			_, src, name, idx = inst
			value = self._value(frame, src)
			arr_name = self._value(frame, name) if isinstance(name, str) and name.startswith('R') else name
			index = self._value(frame, idx)
			index = int(index) if not isinstance(index, int) else index
			
			# Guardar en celda aplanada
			cell = f"{arr_name}_{index}"
			if cell in frame.locals:
				frame.locals[cell] = value
			elif cell in self.globals:
				self.globals[cell] = value
			else:
				frame.locals[cell] = value  # crear local si no existe
			return None
		
		# -------------------------
		#Literales
		# -------------------------

		if op in {"MOVI", "MOVF", "MOVB", "MOVS"}:
			_, value, target = inst
			if op == "MOVF":
				value = float(value)
			elif op in ("MOVI", "MOVB"):
				value = int(value)
			elif op == "MOVS":
				if isinstance(value, str) and value.startswith('"') and value.endswith('"'):
					value = value[1:-1]  # quitar comillas si es literal directo
			frame.regs[target] = value
			return None
			
		# -------------------------
		# Aritmética
		# -------------------------
		if op in {"ADDI", "SUBI", "MULI", "DIVI", "MODI", "ADDF", "SUBF", "MULF", "DIVF"}:
			_, r1, r2, target = inst
			a = self._value(frame, r1)
			b = self._value(frame, r2)
			if op.startswith("ADD"):
				out = a + b
			elif op.startswith("SUB"):
				out = a - b

			elif op.startswith("MUL"):
				out = a * b
			elif op.startswith("MOD"):
				if b == 0:
					raise IRRuntimeError(
						f"Modulo por cero: {r2}=0")
				out = int(a) % int(b)
			elif op.startswith("DIV"):
				if b == 0:
					raise IRRuntimeError(
						f"División por cero en {op}: divisor {r2} vale 0; "
						f"dividendo {r1} vale {a}"
					)
				if op.endswith("I"):
					out = int(a / b)   # truncamiento hacia cero
				else:
					out = a / b
			frame.regs[target] = out
			return None
			
		# -------------------------
		# Bitwise / booleanos 0-1
		# -------------------------
		if op in {"AND", "OR", "XOR"}:
			_, r1, r2, target = inst
			a = int(self._value(frame, r1))
			b = int(self._value(frame, r2))
			if op == "AND":
				out = a & b
			elif op == "OR":
				out = a | b
			else:
				out = a ^ b
			frame.regs[target] = out
			return None
			
		# -------------------------
		# Comparaciones
		# -------------------------
		if op in {"CMPI", "CMPF", "CMPB", "CMPS"}:
			_, cmp_op, r1, r2, target = inst
			a = self._value(frame, r1)
			b = self._value(frame, r2)
			frame.regs[target] = 1 if self._compare(cmp_op, a, b) else 0
			return None
			
		# -------------------------
		# Conversiones
		# -------------------------
		if op == "ITOF":
			_, r1, target = inst
			frame.regs[target] = float(self._value(frame, r1))
			return None
			
		if op == "FTOI":
			_, r1, target = inst
			frame.regs[target] = int(self._value(frame, r1))
			return None
			
		if op == "BTOI":
			_, r1, target = inst
			frame.regs[target] = int(self._value(frame, r1))
			return None
			
		if op == "ITOB":
			_, r1, target = inst
			frame.regs[target] = int(self._value(frame, r1)) & 0xFF
			return None
			
		# -------------------------
		# Print
		# -------------------------
		if op in {"PRINTI", "PRINTF", "PRINTB", "PRINTS"}:
			_, source = inst
			value = self._value(frame, source)
			if op == "PRINTB":
				text = chr(value) if isinstance(value, int) else str(value)
			elif op == "PRINTS":
				# Si ya es string Python (MOVS literal), imprimir directo
				if isinstance(value, str):
					text = value
				else:
					text = self._read_c_string(value)  # fallback para bloques DATAS
			else:
				text = str(value)
			print(text)
			self.output.append(text)
			return None
			
		# -------------------------
		# Control de flujo
		# -------------------------
		if op == "LABEL":
			return None
			
		if op == "BRANCH":
			_, label = inst
			frame.pc = self._label_pc(frame, label)
			return None
			
		if op == "CBRANCH":
			_, test, label_true, label_false = inst
			value = self._value(frame, test)
			frame.pc = self._label_pc(frame, label_true if value != 0 else label_false)
			return None
			
		# PHI simple: útil para expresiones ternarias.
		# Como solo se ejecuta una rama, normalmente solo uno de los registros existe.
		if op == "PHI":
			*sources, target = inst[1:]
			for src in sources:
				if isinstance(src, str) and src in frame.regs:
					frame.regs[target] = frame.regs[src]
					return None
			# Fallback: evaluar el primer operando si existe.
			if sources:
				frame.regs[target] = self._value(frame, sources[0])
			else:
				frame.regs[target] = None
			return None
			
		# -------------------------
		# Funciones
		# -------------------------
		if op == "CALL":
			_, fname, *rest = inst
			if fname not in self.functions:
				raise IRRuntimeError(f"Función no encontrada: {fname}")
				
			expected = len(getattr(self.functions[fname], "params", []))
			arg_regs = rest[:expected]
			target = rest[expected] if len(rest) > expected else None
			arg_values = [self._value(frame, r) for r in arg_regs]
			ret = self.call(fname, arg_values)
			if target is not None:
				frame.regs[target] = ret
			return None
			
		if op == "RET" or op in {"RETI", "RETF", "RETB", "RETS"}:
			if len(inst) == 1:
				return _Return(None)
			_, source = inst
			return _Return(self._value(frame, source))
			
		raise IRRuntimeError(f"Instrucción no soportada: {inst}")
		
	# ------------------------------------------------------------
	# Helpers
	# ------------------------------------------------------------
	
	def _value(self, frame: Frame, operand):
		if isinstance(operand, str):
			if operand in frame.regs:
				return frame.regs[operand]
			if operand in frame.locals:
				return frame.locals[operand]
			if operand in self.globals:
				return self.globals[operand]
			if operand in self.data:
				return operand
		return operand
		
	def _load_var(self, frame: Frame, name: str):
		if name in frame.locals:
			val = frame.locals[name]
			if isinstance(val, str):
				return self._reconstruct_array(val, frame)
			return val
		if name in self.globals:
			return self.globals[name]

		# Patrón base_N: el nombre tiene forma "arr_0", "arr_1", etc.
		# Si "arr" ya es un dict (parámetro reconstruido), devolver dict[N].
		if '_' in name:
			sep = name.rfind('_')
			base = name[:sep]
			suffix = name[sep+1:]
			if suffix.lstrip('-').isdigit():
				index = int(suffix)
				# Buscar base como dict en locals
				base_val = frame.locals.get(base) or self.globals.get(base)
				if isinstance(base_val, dict):
					if index in base_val:
						return base_val[index]
					raise IRRuntimeError(
						f"Índice {index} fuera de rango en arreglo '{base}'"
					)

		# Último recurso: puede ser un arreglo aplanado en globals/locals
		# (e.g. numbers_0, numbers_1, ...) sin declaración ALLOCI previa.
		try:
			return self._reconstruct_array(name, frame)
		except IRRuntimeError:
			pass
		raise IRRuntimeError(f"Variable no definida: {name}")
	
	def _reconstruct_array(self, name: str, frame: Frame) -> dict:
		"""Reconstruye arreglo desde variables aplanadas en globals o locals."""
		
		# Buscar en locals primero
		if frame is not None:
			flat_keys = sorted(
				[k for k in frame.locals if k.startswith(name + '_')],
				key=lambda k: int(k[len(name)+1:])
			)
			if flat_keys:
				return {int(k[len(name)+1:]): frame.locals[k] for k in flat_keys}
		
		# Buscar en globals
		flat_keys = sorted(
			[k for k in self.globals if k.startswith(name + '_')],
			key=lambda k: int(k[len(name)+1:])
		)
		if flat_keys:
			return {int(k[len(name)+1:]): self.globals[k] for k in flat_keys}
		
		raise IRRuntimeError(f"Variable no definida: {name}")
	
	def _store_var(self, frame: Frame, name: str, value):
		if name in frame.locals:
			frame.locals[name] = value
		elif name in self.globals:
			self.globals[name] = value
		else:
			# Si no existe, asumimos local para tolerar IR sencillo.
			frame.locals[name] = value

	
			
	def _label_pc(self, frame: Frame, label: str) -> int:
		if label not in frame.labels:
			raise IRRuntimeError(f"Label no encontrado en {frame.name}: {label}")
		return frame.labels[label]
		
	def _compare(self, op: str, a, b) -> bool:
		if op == "==":
			return a == b
		if op == "!=":
			return a != b
		if op == "<":
			return a < b
		if op == "<=":
			return a <= b
		if op == ">":
			return a > b
		if op == ">=":
			return a >= b
		raise IRRuntimeError(f"Comparador no soportado: {op}")
		
	def _read_c_string(self, name_or_values) -> str:
		if isinstance(name_or_values, str):
			if name_or_values not in self.data:
				raise IRRuntimeError(f"Cadena no encontrada: {name_or_values}")
			values = self.data[name_or_values]
		else:
			values = name_or_values
			
		chars: list[str] = []
		for b in values:
			b = int(b)
			if b == 0:
				break
			chars.append(chr(b))
		return bytes("".join(chars), "latin1").decode("utf-8", errors="replace")
		
		
@dataclass
class _Return:
	value: Any = None
	
	
# Alias corto opcional
IRInterp = IRInterpreter


if __name__ == "__main__":
	import sys
	
	from parser  import parse
	from checker import Checker
	from errors  import errors_detected
	from ircode  import IRCodeGen
	
	if sys.platform != 'ios':
		if len(sys.argv) != 2:
			raise SystemExit("Usage: python parser_v2.py <filename>")
		filename = sys.argv[1]
	else:
		from file_picker import file_picker_dialog
		filename = file_picker_dialog(
			title='Seleccionar un archivo',
			root_dir='./test/',
			file_pattern='^.*[.](bpp|bminor)'
		)
		
	if filename:
		txt = open(filename, encoding="utf-8").read()
		ast = parse(txt)
	
		if errors_detected():
			raise SystemExit("Hay errores de análisis; no se ejecuta IR.")
		
		c = Checker.check(ast)
		if not c.ok():
			raise SystemExit("El checker reportó errores; no se ejecuta IR.")
		
		ir = IRCodeGen.generate(ast)
		interp = IRInterpreter(ir, trace=True)
		interp.run("main")