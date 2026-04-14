import os
import glob
import sys
from graphviz import Digraph
from rich.console import Console

from core.checker import check
from core.parser import parse
from core.errors import clear_errors, errors_detected, set_console
from ast_tree.rich_tree import build_rich_tree
from ast_tree.dot_graphviz import ast_to_dot, build_graphviz

# ===============================================================
# Extensiones soportadas
# ===============================================================
 
EXTENSIONS = ('*.bminor', '*.bpp')
SEPARADOR = '--'*50

# ===============================================================
# Ejecutar un archivo individual
# ===============================================================

def ejecutar_archivo(filepath, console, passed, failed):
 
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
            console.print(ast)
            console.print('[bold green]OK[/bold green]')
            file_console.print(ast)
            
            file_console.print(SEPARADOR)

            # Generar archivo .dot del arbol graphviz
            dot = ast_to_dot(ast)
            dot.save(f'output/graphviz_tree/ast_{base}.dot')
            console.print(f'[dim] -> output/graphviz_tree/ast_{base}.dot [/dim]')
            
            # Árbol rich en consola y archivo txt
            rich_tree = build_rich_tree(ast)
            console.print(rich_tree)
            console.print('[bold green] OK [/bold green]')
            
            # abre un txt para el arbol rich
            with open(f'output/rich_tree/rich_{base}.txt', 'w', encoding='utf-8') as f_rich:
                rich_file_console = Console(file=f_rich, highlight=False)
                rich_file_console.print(rich_tree)
            
            # Análisis semántico
            checker = check(ast)
 
            if checker.errors:
                console.print(f'[bold red]{len(checker.errors)} error(es) semántico(s)[/bold red]')
                file_console.print(f'{len(checker.errors)} error(es) semántico(s)')
            else:
                console.print('[bold green]OK semántico[/bold green]')
                file_console.print('OK semántico')
                # imprimir tabla de símbolos en debug si quieres
                checker.symtab.print()
                
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
 
def ejecutar(folder='test'):
 
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
        ejecutar_archivo(filepath, console, passed, failed)
 
    # resumen
    console.rule('[bold] Resumen [/bold]')
    console.print(f'[bold green] Sin errores ({len(passed)}): [/bold green] {", ".join(passed) or "ninguno"}')
    console.print(f'[bold red] Con errores ({len(failed)}): [/bold red] {", ".join(failed) or "ninguno"}')
    console.print(f'[bold]Total: {len(passed)}/{len(test_files)} archivos correctos[/bold]')

# ===============================================================
# main
# ===============================================================

if __name__ == '__main__':
 
    if len(sys.argv) == 2:
        # archivo específico
        filepath = sys.argv[1]
        if not os.path.isfile(filepath):
            print(f'Archivo no encontrado: {filepath}')
            sys.exit(1)
        ext = os.path.splitext(filepath)[1].lower()
        if ext not in ('.bminor', '.bpp'):
            print(f'Extensión no soportada: {ext} — use .bminor o .bpp')
            sys.exit(1)
        console = Console()
        passed, failed = [], []
        ejecutar_archivo(filepath, console, passed, failed)
 
    elif len(sys.argv) == 1:
        # sin argumentos → ejecutar carpeta test/
        ejecutar()
 
    else:
        print('Uso:')
        print('  python run.py                  # ejecuta todos los archivos en test/')
        print('  python run.py test/archivo.bminor  # ejecuta un archivo específico')
        sys.exit(1)