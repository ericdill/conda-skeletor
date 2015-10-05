import ast


def parse(path_to_setuppy):
    """Helper function to gather information from setup.py

    Parameters
    ----------
    path_to_setuppy : list
        Path to setup.py file.
        e.g. '/home/edill/dev/conda/conda-skeletor/setup.py'

    Returns
    -------
    dict
        Dictionary keyed on the kwargs that get passed to the setup() function
        inside of setup.py
    """
    with open(path_to_setuppy, 'r') as f:
        code = f.read()
    tree = ast.parse(code)
    scraper = SetupScraper()
    try:
        scraper.visit(tree)
    except IndexError:
        print('setup.py scaping failed')
        raise
    # info = {v[0]: v[1:] if len(v) == 2 else v[1]
    #         for v in scraper.setup_info}
    info = {}
    for line in scraper.setup_info:
        value = line[1:]
        if len(line) == 2:
            value = line[1]
        info[line[0]] = value

    # TODO correctly parse the entry_points argument
    # this will break as soon as the setup.py does not look like:
    # entry_points={
    #     'console_scripts': [
    #         'replay = replay.replay:main']},
    entry_points = info.get('entry_points')
    if entry_points:
        info['entry_points'] = {entry_points[0]: entry_points[1]}
    return info



class SetupScraper(ast.NodeVisitor):
    def __init__(self):
        self.in_setup = False
        self.setup_info = []

    def visit_keyword(self, node):
        if self.in_setup:
            self.setup_info.append([node.arg])
        self.visit(node.value)

    def visit_Call(self, node):
        if self.in_setup:
            self.setup_info[-1].append(node)
        if isinstance(node.func, ast.Name) and node.func.id == 'setup':
            self.in_setup = True
        self.generic_visit(node)
        if isinstance(node.func, ast.Name) and node.func.id == 'setup':
            self.in_setup = False
    def visit_Name(self, node):
        if node.id == 'setup':
            return
        if self.in_setup:
            self.setup_info[-1].append(node.id)
    def visit_Str(self, node):
        if self.in_setup:
            self.setup_info[-1].append(node.s)

    def generic_visit(self, node):
        """Called if no explicit visitor function exists for a node.

        Overridden from the ast.NodeVisitor base class so that I can add some
        local state to keep track of whether or not my node visitor is inside
        a try/except block.  When a try block is encountered, the node is added
        to the `trys` instance attribute and then the try block is recursed in
        to.  Once the recursion has exited, the node is removed from the `trys`
        instance attribute
        """
        for field, value in ast.iter_fields(node):
            if isinstance(value, list):
                for item in value:
                    if isinstance(item, ast.AST):
                        self.visit(item)
            elif isinstance(value, ast.AST):
                self.visit(value)