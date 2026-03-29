import os
import glob
from graphviz import Digraph
from rich.console import Console

from core.parser import parse
from core.errors import clear_errors, errors_detected, set_console
from ast_tree.rich_tree import build_rich_tree
from ast_tree.dot_graphviz import ast_to_dot, build_graphviz

# ===============================================================
# ejecutar usando los archivos bminor en la carpeta test
# ===============================================================

def ejecutar(folder='test'):
    
    # referencia de los archivos a usar
    test_files = sorted(glob.glob(f'{folder}/*.bminor'))

    # validacion de informacion
    if not test_files:
        print(f'No se encontraron archivos en {folder}/')
        return

    # Crear subcarpetas de salida
    os.makedirs('output/console_output', exist_ok=True)
    os.makedirs('output/graphviz_tree', exist_ok=True)
    os.makedirs('output/rich_tree', exist_ok=True)

    console = Console()
    passed  = []
    failed  = []

    # ejecutar pruebas en cada archivo
    for filepath in test_files:
        
        # informacion del nombre del archivo
        name = os.path.basename(filepath)
        base = os.path.splitext(name)[0]

        console.rule(f'[bold cyan]{name}[/bold cyan]')
        clear_errors()

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

                # Generar archivo .dot del arbol graphviz
                dot = ast_to_dot(ast)
                dot.save(f'output/graphviz_tree/ast_{base}.dot')
                console.print(f'[dim] -> output/graphviz_tree/ast_{base}.dot [/dim]')
                
                # generar imagen graphviz
                # dot = Digraph()
                # build_graphviz(ast, dot)
                # dot.render("ast", format="png")
                
                # Árbol rich en consola y archivo txt
                rich_tree = build_rich_tree(ast)
                console.print(rich_tree)
                console.print('[bold green] OK [/bold green]')
                
                # abre un txt para el arbol rich
                with open(f'output/rich_tree/rich_{base}.txt', 'w', encoding='utf-8') as f_rich:
                    rich_file_console = Console(file=f_rich, highlight=False)
                    rich_file_console.print(rich_tree)
                
                passed.append(name)
                
            # codigo con errores al analizar
            else:
                console.print(f'[bold red] {count} error(es)[/bold red]')
                file_console.print(f' {count} error(es)')
                failed.append(name)

    set_console(Console())

    # resumen de resultados en consola
    console.rule('[bold] Resumen [/bold]')
    console.print(f'[bold green] Sin errores ({len(passed)}): [/bold green] {", ".join(passed) or "ninguno"}')
    console.print(f'[bold red] Con errores ({len(failed)}): [/bold red] {", ".join(failed) or "ninguno"}')
    console.print(f'[bold]Total: {len(passed)}/{len(test_files)} archivos correctos[/bold]')


# main :)
if __name__ == '__main__':
    ejecutar()