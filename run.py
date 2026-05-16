import os
import glob
import sys

from graphviz import Digraph
from rich.console import Console

from core.checker import check
from core.irinterp import IRInterpreter
from core.parser import parse
from core.errors import clear_errors, errors_detected, set_console
from core.IRCode import generate_ir
from core.iroptimizer import IROptimizer, parse_opt_level
from ast_tree.rich_tree import build_rich_tree
from ast_tree.dot_graphviz import ast_to_dot, build_graphviz


# ===============================================================
# Extensiones soportadas
# ===============================================================
 
EXTENSIONS = ('*.bminor', '*.bpp')
SEPARADOR = '--' * 50

# ===============================================================
# Ejecutar un archivo individual
# ===============================================================

def ejecutar_archivo(filepath, console, passed, failed, opt_level=0):
 
    # informacion del nombre del archivo
    name = os.path.basename(filepath)
    base = os.path.splitext(name)[0]
 
    console.rule(f'[bold cyan]{name}[/bold cyan]')
    clear_errors()
 
    # Crear subcarpetas de salida
    os.makedirs('output/console_output', exist_ok=True)
    os.makedirs('output/graphviz_tree',  exist_ok=True)
    os.makedirs('output/rich_tree',      exist_ok=True)
 
    # inciar archivo txt para la salida basica de la consola 
    with open(f'output/console_output/salida_{base}.txt', 'w', encoding='utf-8') as f:
 
        # referencia uso txts
        file_console = Console(file=f, highlight=False)
 
        # permitir el uso de "consolas"
        class DualConsole:
            def print(self, *args, **kwargs):
                console.print(*args, **kwargs)
                file_console.print(*args, **kwargs)
 
        set_console(DualConsole())
 
        # leer archivo, aplicar analizis sintáctico y contar errores
        txt   = open(filepath, encoding='utf-8').read()
        ast   = parse(txt)
        count = errors_detected()
 
        # ejecucion segun errores encontrados 
        if count == 0:
 
            # registra la salida en consola y en archivo txt
            # console.print(ast)
            # console.print('[bold green]OK[/bold green]')
            file_console.print(ast)
            
            file_console.print(SEPARADOR)

            # Generar archivo .dot del arbol graphviz
            dot = ast_to_dot(ast)
            dot.save(f'output/graphviz_tree/ast_{base}.dot')
            # console.print(f'[dim] -> output/graphviz_tree/ast_{base}.dot [/dim]')
            
            # Árbol rich en consola y archivo txt
            rich_tree = build_rich_tree(ast)
            # console.print(rich_tree)
            # console.print('[bold green] OK [/bold green]')
            
            # abre un txt para el arbol rich
            with open(f'output/rich_tree/rich_{base}.txt', 'w', encoding='utf-8') as f_rich:
                rich_file_console = Console(file=f_rich, highlight=False)
                rich_file_console.print(rich_tree)
            
            # Análisis semántico
            checker = check(ast)
 
            if checker.errors:
                # console.print(f'[bold red]{len(checker.errors)} error(es) semántico(s)[/bold red]')
                file_console.print(f'{len(checker.errors)} error(es) semántico(s)')
            else:
                # console.print('[bold green]OK semántico[/bold green]')
                file_console.print('OK semántico')
                # imprimir tabla de símbolos en debug si quieres
                # checker.symtab.print()
                
                ir = generate_ir(ast)
                console.print(ir.format())
                
                os.makedirs('output/ir', exist_ok=True)
                
                with open(f'output/ir/ir_{base}.txt', 'w', encoding='utf-8') as f_ir:
                    f_ir.write(ir.format())
                
                level_tag = f'-O{opt_level}'
                console.print(f'[bold yellow]Optimización: {level_tag}[/bold yellow]')
                
                ir = IROptimizer.optimize(ir, level=opt_level)
                console.print(ir.format())
                
                with open(f'output/ir/ir_{base}_{level_tag}.txt', 'w', encoding='utf-8') as f_ir:
                    f_ir.write(ir.format())
                    
                console.print(f'[dim] -> output/ir/ir_{base}_{level_tag}.txt [/dim]')
                
                # Interpretar
                interp = IRInterpreter(ir, trace=False)
                interp.run("main")
                
            file_console.print(SEPARADOR)
 
            passed.append(name)
            
        else:
            console.print(f'[bold red]{count} error(es)[/bold red]')
            file_console.print(f'{count} error(es)')
            failed.append(name)
 
    set_console(Console())

# ===============================================================
# Ejecutar todos los archivos de una carpeta
# ===============================================================
 
def ejecutar(folder='test', opt_level=0):
 
    # recolectar archivos de todas las extensiones soportadas
    test_files = []
    
    for ext in EXTENSIONS:
        test_files.extend(glob.glob(os.path.join(folder, ext)))
    
    test_files = sorted(set(test_files))
 
    if not test_files:
        print(f'No se encontraron archivos .bminor o .bpp en {folder}/')
        return
 
    console = Console()
    passed  = []
    failed  = []
 
    for filepath in test_files:
        ejecutar_archivo(filepath, console, passed, failed, opt_level)
 
    # resumen
    console.rule('[bold] Resumen [/bold]')
    console.print(f'[bold green] Sin errores ({len(passed)}): [/bold green] {", ".join(passed) or "ninguno"}')
    console.print(f'[bold red] Con errores ({len(failed)}): [/bold red] {", ".join(failed) or "ninguno"}')
    console.print(f'[bold]Total: {len(passed)}/{len(test_files)} archivos correctos[/bold]')

# ===============================================================
# Parsear argumentos de línea de comandos
# ===============================================================

def _parse_args(argv: list[str]):
    """
    Formas válidas:
      python run.py                          → carpeta test/, -O0
      python run.py --O1                     → carpeta test/, -O1
      python run.py test/archivo.bminor      → archivo, -O0
      python run.py test/archivo.bminor --O1 → archivo, -O1
      python run.py test/archivo.bminor --O2 → archivo, -O2
    """
    filepath  = None
    opt_level = 0

    for token in argv:
        # Detectar token de optimización: --O0, --O1, -O1, O1, 0, 1, 2 …
        stripped = token.lstrip('-')
        if stripped.upper().startswith('O') or (stripped.isdigit()):
            try:
                opt_level = parse_opt_level(token)
                continue
            except ValueError:
                pass

        # Si no es opción de optimización, es la ruta del archivo
        if filepath is None:
            filepath = token
        else:
            # Argumento desconocido
            print(f'Argumento no reconocido: {token!r}')
            _print_uso()
            sys.exit(1)

    return filepath, opt_level

def _print_uso():
    print('Uso:')
    print('  python run.py                              # todos los archivos en test/ con -O0')
    print('  python run.py test/archivo.bminor          # archivo específico con -O0')
    print('  python run.py test/archivo.bminor --O1     # archivo con optimización -O1')
    print('  python run.py test/archivo.bminor --O2     # archivo con optimización -O2')
    print('  python run.py --O1                         # todos los archivos en test/ con -O1')

# ===============================================================
# main
# ===============================================================

if __name__ == '__main__':
 
    filepath, opt_level = _parse_args(sys.argv[1:])
    
    if filepath is not None:
        # Archivo específico
        if not os.path.isfile(filepath):
            print(f'Archivo no encontrado: {filepath}')
            sys.exit(1)
            
        ext = os.path.splitext(filepath)[1].lower()
        
        if ext not in ('.bminor', '.bpp'):
            print(f'Extensión no soportada: {ext} — use .bminor o .bpp')
            sys.exit(1)
            
        console = Console()
        ejecutar_archivo(filepath, console, [], [], opt_level)
        
    else:
        # Sin archivo → carpeta test/
        ejecutar(opt_level=opt_level)
        