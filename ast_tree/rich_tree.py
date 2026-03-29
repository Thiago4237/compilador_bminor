from rich.tree import Tree

def build_rich_tree(node, field_name=''):
    
     # Valor simple (hoja del árbol)
    if not hasattr(node, '__dataclass_fields__'):
        label = f'{field_name}: {repr(node)}' if field_name else repr(node)
        return Tree(label)
    
    # Nodo AST
    label = f'[bold yellow]{type(node).__name__}[/bold yellow]'
    
    if field_name:
        label = f'[dim]{field_name}[/dim] {label}'
    
    tree = Tree(label)

    for field, value in vars(node).items():
        if isinstance(value, list):
            for item in value:
                tree.add(build_rich_tree(item))
        elif hasattr(value, "__dict__"):
            tree.add(build_rich_tree(value))
        elif hasattr(value, "__dataclass_fields__"):
            tree.add(build_rich_tree(value))
        else:
            # tree.add(f"{field}: {value}")
            tree.add(f'[dim]{field}[/dim]: [green]{repr(value)}[/green]')

    return tree
