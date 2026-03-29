import sly

from rich import print
from rich.table   import Table
from rich.console import Console

try:
    from .errors import error, errors_detected
except ImportError:
    from errors import error, errors_detected

class Lexer(sly.Lexer):
    
    tokens = {
        # PALABRAS RESERVADAS
        ARRAY, AUTO, BOOLEAN, CHAR, ELSE, FALSE, FLOAT, 
        FOR, FUNCTION, IF, INTEGER, PRINT, RETURN, STRING, 
        TRUE, VOID, WHILE, CLASS, THIS, SUPER, EXTENDS, NEW,
        
        CONSTANT, BREAK, CONTINUE,
        
        # OPERADORES DE RELACION 
        LT, LE, GT, GE, EQ, NE, LAND, LOR, LNOT,
        # OPERADORES DE ASIGNACION 
        ADDEQ, SUBEQ, MULEQ, DIVEQ, MODEQ, POWEQ, INC, DEC, 
        DOT,
        # LITERALES
        CHAR_LITERAL, FLOAT_LITERAL, INTEGER_LITERAL, STRING_LITERAL,
        # IDENTIFICADOR
        ID
    }
    
    literals = '+-*/%^=;,:()[]{}?'
    
    #simbolos que se deben ignorar
    ignore = ' \t\r'
    ignore_cppcomment = r'//[^\n]*'
    
    # operadores de relacion
    LE = r'<='
    GE = r'>='
    EQ = r'=='
    NE = r'!='
    LAND = r'&&'
    LOR = r'\|\|'
    
    # operadores de asignacion
    ADDEQ = r'\+='
    SUBEQ = r'-='
    MULEQ = r'\*='
    DIVEQ = r'/='
    MODEQ = r'%='
    POWEQ = r'\^='
    
    INC = r'\+\+'
    DEC = r'--'
    
    # operadores de relacion simples
    LT = r'<'
    GT = r'>'
    LNOT = r'!'
    
    
    # literales numéricos
    FLOAT_LITERAL  = r'\d*\.\d+([eE][+-]?\d+)?|\d+[eE][+-]?\d+'
    INTEGER_LITERAL = r"[1-9]\d*|0"

    # strings y chars (versión simple pero funcional)
    CHAR_LITERAL   = r"""'([\x20-\x26\x28-\x5B\x5D-\x7E]|\\([abefnrtv\\'"]|0x[0-9A-Fa-f]{2}))'"""
    STRING_LITERAL = r'''"([\x20-\x21\x23-\x5B\x5D-\x7E]|\\([abefnrtv\\'"]|0x[0-9A-Fa-f]{2}))*"'''

    # punto 
    DOT     = r'\.'
    
    # expresiones regulares para tokens
    ID = r'[a-zA-Z_][a-zA-Z0-9_]*'
    
    #palabras reservadas (terminar de agregar)
    ID['array'] = ARRAY
    ID['auto'] = AUTO
    ID['boolean'] = BOOLEAN
    ID['char'] = CHAR
    ID['else'] = ELSE
    ID['false'] = FALSE
    ID['float'] = FLOAT
    ID['for'] = FOR
    ID['function'] = FUNCTION
    #ID['func'] = FUNCTION
    ID['if'] = IF
    ID['integer'] = INTEGER
    ID['print'] = PRINT
    ID['return'] = RETURN
    ID['string'] = STRING
    ID['true'] = TRUE
    ID['void'] = VOID
    ID['while'] = WHILE
    ID['class'] = CLASS
    ID['this'] = THIS
    ID['super'] = SUPER
    ID['extends'] = EXTENDS
    ID['new'] = NEW
    ID['constant'] = CONSTANT
    ID['break']    = BREAK
    ID['continue'] = CONTINUE
    

    def error(self, t):
        print(f"Caracter ilegal '{t.value[0]}' en la linea {self.lineno}")
        self.index += 1
    
    # El `@_()` es un decorador que le dice a sly 
    # "usa esta regex para matchear, y cuando encuentres algo ejecuta esta función". 
    
    @_(r'\n+')
    def newline(self, t):
        self.lineno += t.value.count('\n')
        
    @_(r'/\*(.|\n)*?\*/')
    def ignore_comment(self, t):
        self.lineno += t.value.count('\n')
    
    @_(r"/\*(.|\n)*?")
    def malformed_comment(self, t):
        error("Comentario mal formado, sin cerrar", t.lineno)
    
    @_(r"'.")
    def malformed_char(self, t):
        error(f"malformado CHAR", t.lineno)
    
    @_(r'(0\d+)((\.\d+(e[-+]?\d+)?)|(e[-+]?\d+))')
    def malformed_float(self, t):
        error(f"Literal de punto flotante '{t.value}' no sportado", t.lineno)
    
    @_(r'0\d+')
    def malformed_integer(self, t):
        error(f"Literal entera '{t.value}' no sportado", t.lineno)
    
def tokenize(filename:str):

    txt = open(filename, encoding='utf-8').read()
    lex = Lexer()
	
    table = Table(title='Análisis Léxico')
    table.add_column('type')
    table.add_column('value')
    table.add_column('lineno', justify='right')
	
    for tok in lex.tokenize(txt):
        value = tok.value if isinstance(tok.value, str) else str(tok.value)
        table.add_row(tok.type, value, str(tok.lineno))

    if not errors_detected():
        console = Console()
        console.print(table)

        
if __name__ == '__main__':
    import sys

    if len(sys.argv) != 2:
        print(f'usage: python lexer.py <filename>')
        raise SyntaxError()

    txt = open(sys.argv[1], encoding='utf-8').read()
    tokenize(txt)
    