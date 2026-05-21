"""
core/iroptimizer.py — Optimizador de IR para B-Minor+

Niveles:
  -O0  Sin optimización (identidad).
  -O1  Optimización local: constant folding, simplificación algebraica,
       comparaciones constantes, CBRANCH constante, código inalcanzable,
       saltos redundantes.
  -O2  Todo lo anterior + eliminación de temporales muertos.
"""
from __future__ import annotations

from typing import Any, Optional

try:
    from .IRCode import IRProgram, IRFunction, Instruction
except ImportError:
    from IRCode import IRProgram, IRFunction, Instruction  # type: ignore


# ===================================================
# Optimizador principal
# ===================================================

class IROptimizer:

    def __init__(self, level: int = 0):
        self.level = level

    @classmethod
    def optimize(cls, program: IRProgram, level: int = 0) -> IRProgram:
        return cls(level).visit_program(program)

    # -------------------------------------------------
    # Punto de entrada
    # -------------------------------------------------

    def visit_program(self, program: IRProgram) -> IRProgram:
        if self.level <= 0:
            return program

        new_functions: list[IRFunction] = []
        for fn in program.functions:
            new_insts = self._optimize_fn(fn.instructions)
            new_functions.append(
                IRFunction(
                    name=fn.name,
                    params=list(fn.params),
                    return_type=fn.return_type,
                    instructions=new_insts,
                )
            )
        return IRProgram(globals=list(program.globals), functions=new_functions)

    def _optimize_fn(self, instructions: list[Instruction]) -> list[Instruction]:
        insts = list(instructions)

        if self.level >= 1:
            insts = self._constant_fold_and_simplify(insts)
            insts = self._remove_unreachable(insts)
            insts = self._remove_branch_to_next_label(insts)

        if self.level >= 2:
            insts = self._remove_dead_temps(insts)

        return insts

    # ===================================================
    # O1 — Constant folding + simplificación algebraica
    # ===================================================

    def _constant_fold_and_simplify(self, instructions: list[Instruction]) -> list[Instruction]:
        reg_const: dict[str, Any] = {}
        reg_copy: dict[str, str] = {}
        mem_const: dict[str, Any] = {}
        
        out: list[Instruction] = []

        for inst in instructions:
            op = inst[0]

            # LOAD desde memoria
            if op.startswith("LOAD") and len(inst) == 3:
                var, dst = inst[1], inst[2]
                if var in mem_const:
                    # Propagamos el valor constante desde memoria
                    value = mem_const[var]
                    mov_op = "MOVF" if isinstance(value, float) else "MOVI"
                    out.append((mov_op, value, dst))
                    reg_const[dst] = value
                    reg_copy.pop(dst, None)
                    continue


            # MOV literal (MOVI, MOVF, MOVB)
            if op in {"MOVI", "MOVF", "MOVB", "MOV"} and len(inst) == 3:   
                src, dst = inst[1], inst[2]

                if not isinstance(src, str) or not src.startswith("R"):
                    reg_const[dst] = src
                    reg_copy.pop(dst, None)
                    out.append(inst)
                    continue

                # MOV entre registros -> propagación
                if src in reg_const:
                    value = reg_const[src]
                    mov_op = "MOVF" if isinstance(value, float) else "MOVI"
                    out.append((mov_op, value, dst))
                    reg_const[dst] = value
                    reg_copy.pop(dst, None)
                    continue

                elif src in reg_copy:
                    # copia transitiva (R3 -> R1)
                    out.append((op, reg_copy[src], dst))
                    reg_copy[dst] = reg_copy[src]
                    reg_const.pop(dst, None)
                    continue

                else:
                    # Copia simple (sin valor constante conocido)
                    reg_copy[dst] = src
                    reg_const.pop(dst, None)
                    out.append(inst)
                    continue

            # STORE a memoria
            if op.startswith("STORE") and len(inst) == 3:
                src, var = inst[1], inst[2]
                # Si el valor proviene de un registro con valor conocido
                value = reg_const.get(src, None)
                if value is not None:
                    mem_const[var] = value
                else:
                    mem_const.pop(var, None)  # invalidamos si no sabemos el valor
                out.append(inst)
                continue

            # Aritmética binaria
            if op in {"ADDI", "SUBI", "MULI", "DIVI",
                      "ADDF", "SUBF", "MULF", "DIVF",
                      "AND",  "OR",   "XOR"} and len(inst) == 4:
                
                a, b, dst = inst[1], inst[2], inst[3]

                va = reg_const.get(a) if isinstance(a, str) else a
                vb = reg_const.get(b) if isinstance(b, str) else b

                # Constant folding completo
                if va is not None and vb is not None:
                    if op in {"DIVI", "DIVF"} and vb == 0:
                        reg_const.pop(dst, None)
                        out.append(inst)
                        continue
                    result = self._eval_arith(op, va, vb)
                    mov = "MOVF" if isinstance(result, float) else "MOVI"
                    out.append((mov, result, dst))
                    reg_const[dst] = result
                    continue

                # Simplificación algebraica (un operando conocido)
                simplified = self._algebraic_simplify(op, a, b, dst, reg_const)
                if simplified is not None:
                    out.append(simplified)
                    if simplified[0] in {"MOVI", "MOVF"} and len(simplified) == 3:
                        reg_const[dst] = simplified[1]
                        reg_copy.pop(dst, None)
                    else:
                        reg_const.pop(dst, None)
                    continue

                reg_const.pop(dst, None)
                reg_copy.pop(dst, None)
                out.append(inst)
                continue

            # Comparaciones
            if op in {"CMPI", "CMPF", "CMPB"} and len(inst) == 5:
                cmp_op, a, b, dst = inst[1], inst[2], inst[3], inst[4]
                va = reg_const.get(a) if isinstance(a, str) else a
                vb = reg_const.get(b) if isinstance(b, str) else b

                if va is not None and vb is not None:
                    result = 1 if self._eval_cmp(cmp_op, va, vb) else 0
                    out.append(("MOVI", result, dst))
                    reg_const[dst] = result
                    continue

                reg_const.pop(dst, None)
                out.append(inst)
                continue

            # CBRANCH con condición constante → BRANCH directo
            if op == "CBRANCH" and len(inst) == 4:
                test, true_lbl, false_lbl = inst[1], inst[2], inst[3]
                vtest = reg_const.get(test) if isinstance(test, str) else test
                if vtest is not None:
                    out.append(("BRANCH", true_lbl if vtest else false_lbl))
                    continue
                out.append(inst)
                continue

            # Instrucción genérica: invalidar registro destino
            if len(inst) >= 2 and isinstance(inst[-1], str) and inst[-1].startswith("R"):
                reg_const.pop(inst[-1], None)

            out.append(inst)

        return out

    # ===================================================
    # O1 — Eliminación de código inalcanzable
    # ===================================================

    def _remove_unreachable(self, instructions: list[Instruction]) -> list[Instruction]:
        out: list[Instruction] = []
        dead = False

        for inst in instructions:
            op = inst[0]

            if op == "LABEL":
                dead = False
                out.append(inst)
                continue

            if dead:
                continue

            out.append(inst)

            if op in {"BRANCH", "RET", "RETI", "RETF", "RETB", "RETS"}:
                dead = True

        return out

    # ===================================================
    # O1 — Eliminar salto al label inmediatamente siguiente
    # ===================================================

    def _remove_branch_to_next_label(self, instructions: list[Instruction]) -> list[Instruction]:
        out: list[Instruction] = []
        i = 0
        while i < len(instructions):
            inst = instructions[i]
            if (inst[0] == "BRANCH" and len(inst) == 2
                    and i + 1 < len(instructions)
                    and instructions[i + 1][0] == "LABEL"
                    and instructions[i + 1][1] == inst[1]):
                i += 1
                continue
            out.append(inst)
            i += 1
        return out

    # ===================================================
    # O2 — Eliminación de temporales muertos
    # ===================================================

    def _remove_dead_temps(self, instructions: list[Instruction]) -> list[Instruction]:
        used: set[str] = set()
        result: list[Instruction] = []

        for inst in reversed(instructions):
            dst  = self._defined_temp(inst)
            args = self._used_temps(inst)

            if dst is not None and dst not in used and self._is_pure(inst):
                continue

            if dst is not None:
                used.discard(dst)

            used.update(args)
            result.append(inst)

        result.reverse()
        return result

    # ===================================================
    # Helpers: análisis de instrucciones
    # ===================================================

    def _defined_temp(self, inst: Instruction) -> Optional[str]:
        op = inst[0]
        if op in {"MOVI", "MOVF", "MOVB", "MOVS", "ADDR"} and len(inst) == 3:
            t = inst[2]
        elif op in {"ADDI", "SUBI", "MULI", "DIVI",
                    "ADDF", "SUBF", "MULF", "DIVF",
                    "AND", "OR", "XOR"} and len(inst) == 4:
            t = inst[3]
        elif op in {"CMPI", "CMPF", "CMPB"} and len(inst) == 5:
            t = inst[4]
        elif op.startswith("LOAD") and len(inst) == 3:
            t = inst[2]
        else:
            return None
        return t if isinstance(t, str) and t.startswith("R") else None

    def _used_temps(self, inst: Instruction) -> set[str]:
        op = inst[0]
        if op in {"MOVI", "MOVF", "MOVB", "MOVS", "LABEL", "BRANCH", "DATAS", "ADDR"}:
            return set()
        if op.startswith("STORE"):
            return self._regs(inst[1:2])
        if op.startswith("PRINT"):
            return self._regs(inst[1:])
        if op == "CBRANCH":
            return self._regs(inst[1:2])
        if op in {"RET", "RETI", "RETF", "RETB", "RETS"}:
            return self._regs(inst[1:])
        if op in {"ADDI", "SUBI", "MULI", "DIVI",
                  "ADDF", "SUBF", "MULF", "DIVF",
                  "AND", "OR", "XOR"}:
            return self._regs(inst[1:3])
        if op in {"CMPI", "CMPF", "CMPB"}:
            return self._regs(inst[2:4])
        return self._regs(inst[1:])

    def _regs(self, values) -> set[str]:
        return {x for x in values if isinstance(x, str) and x.startswith("R")}

    def _is_pure(self, inst: Instruction) -> bool:
        op = inst[0]
        return (
            op in {"MOVI", "MOVF", "MOVB", "MOVS", "ADDR",
                   "ADDI", "SUBI", "MULI", "DIVI",
                   "ADDF", "SUBF", "MULF", "DIVF",
                   "AND", "OR", "XOR",
                   "CMPI", "CMPF", "CMPB", "PHI"}
            or op.startswith("LOAD")
        )

    # ===================================================
    # Helpers aritméticos / comparación
    # ===================================================

    def _eval_arith(self, op: str, a: Any, b: Any) -> Any:
        if op in {"ADDI", "ADDF"}: return a + b
        if op in {"SUBI", "SUBF"}: return a - b
        if op in {"MULI", "MULF"}: return a * b
        if op == "DIVI":           return int(a) // int(b)
        if op == "DIVF":           return a / b
        if op == "AND":            return int(a) & int(b)
        if op == "OR":             return int(a) | int(b)
        if op == "XOR":            return int(a) ^ int(b)
        raise NotImplementedError(op)

    def _eval_cmp(self, oper: str, a: Any, b: Any) -> bool:
        if oper == "==":  return a == b
        if oper == "!=":  return a != b
        if oper == "<":   return a < b
        if oper == "<=":  return a <= b
        if oper == ">":   return a > b
        if oper == ">=":  return a >= b
        raise NotImplementedError(oper)

    def _algebraic_simplify(
        self, op: str, a: Any, b: Any, dst: str, const: dict[str, Any]
    ) -> Optional[Instruction]:
        va = const.get(a) if isinstance(a, str) else (a if not isinstance(a, str) else None)
        vb = const.get(b) if isinstance(b, str) else (b if not isinstance(b, str) else None)
        mov = "MOVF" if op in {"ADDF", "SUBF", "MULF", "DIVF"} else "MOVI"

        if op in {"ADDI", "ADDF"}:
            if vb == 0 and va is not None: return (mov, va, dst)
            if va == 0 and vb is not None: return (mov, vb, dst)
        if op in {"SUBI", "SUBF"}:
            if vb == 0 and va is not None: return (mov, va, dst)
        if op in {"MULI", "MULF"}:
            if vb == 1 and va is not None: return (mov, va, dst)
            if va == 1 and vb is not None: return (mov, vb, dst)
            if va == 0 or vb == 0:         return (mov, 0, dst)
        if op in {"DIVI", "DIVF"}:
            if vb == 1 and va is not None: return (mov, va, dst)

        return None


# ===================================================
# Utilidad: parsear "--O0" / "--O1" / "--O2"
# ===================================================

def parse_opt_level(token: str) -> int:
    """
    Acepta:  --O0  --O1  --O2  -O0  -O1  -O2  O0  O1  O2  0  1  2
    Retorna: 0, 1 o 2.  Lanza ValueError si no reconoce el token.
    """
    text = token.strip().lstrip("-").lstrip("O")
    if not text.isdigit():
        raise ValueError(f"Nivel de optimización inválido: {token!r}")
    level = int(text)
    if level < 0 or level > 4:
        raise ValueError("El nivel debe estar entre 0 y 4")
    return level