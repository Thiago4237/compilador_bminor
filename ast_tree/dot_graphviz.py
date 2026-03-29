from graphviz import Digraph
import uuid

# ===================================================
# AST Graphviz
# ===================================================

def build_graphviz(node, dot, parent_id=None):
    
    node_id = str(uuid.uuid4())
    label = type(node).__name__

    dot.node(node_id, label)

    if parent_id:
        dot.edge(parent_id, node_id)

    for field, value in vars(node).items():
        if isinstance(value, list):
            for item in value:
                build_graphviz(item, dot, node_id)
        elif hasattr(value, "__dict__"):
            build_graphviz(value, dot, node_id)

    return dot

def ast_to_dot(node, dot=None, parent=None, label=''):
    
    if dot is None:
        dot = Digraph(format='png')
        dot.attr(rankdir='TB')

    node_id = str(id(node)) + label

    if isinstance(node, list):
        dot.node(node_id, '[ ]', shape='rectangle', style='dashed')
        if parent:
            dot.edge(parent, node_id, label=label)
        for i, item in enumerate(node):
            ast_to_dot(item, dot, node_id, str(i))
        return dot

    if not hasattr(node, '__dataclass_fields__'):
        dot.node(node_id, repr(node), shape='ellipse', style='filled', fillcolor='lightblue')
        if parent:
            dot.edge(parent, node_id, label=label)
        return dot

    name = type(node).__name__
    dot.node(node_id, name, shape='box', style='filled', fillcolor='lightyellow')
    if parent:
        dot.edge(parent, node_id, label=label)

    for field, value in node.__dict__.items():
        ast_to_dot(value, dot, node_id, field)

    return dot

