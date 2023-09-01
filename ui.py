from nicegui import ui
from typing import List
import uuid

class Node:
    def __init__(self, name="", ip="", isPi=False, save_string: str = None) -> None:
        if not save_string:
            self.uuid = uuid.uuid4()
            self.name = name
            self.ip = ip
            self.isPi = isPi
        else:
            strings = save_string[1:-2].split(",")
            self.uuid = uuid.UUID(strings[0])
            self.name = strings[1]
            self.ip = strings[2]
            self.isPi = strings[3] == "True"
    def __str__(self) -> str:
        return f"({self.uuid},{self.name},{self.ip},{self.isPi})"
    def __repr__(self):
        return str(self)

nodes : List[Node] = []

node_string = '''{id}["{name}\nTYPE: {isPi}\nIP: {ip}"]\n'''

def create_node_dialog():
    with ui.dialog() as dialog, ui.card():
        ui.label("Add a new Node")

        nameField = ui.input(label='Name', placeholder='start typing',
                validation={'Input too long': lambda value: len(value) < 20})
        ipField = ui.input(label='IP', placeholder='start typing',
                validation={'Input too long': lambda value: len(value) < 20})
        isPiField = ui.switch("is connected over PI")

        ui.button('Add Node', on_click=lambda: add_node(Node(name=nameField.value, ip=ipField.value, isPi=isPiField.value), dialog))
    return dialog

def create_node_edit_dialog(node: Node):
    with ui.dialog() as dialog, ui.card():
        ui.label("Editing Node")

        nameField = ui.input(label='Name', placeholder='start typing',
                validation={'Input too long': lambda value: len(value) < 20})
        ipField = ui.input(label='IP', placeholder='start typing',
                validation={'Input too long': lambda value: len(value) < 20})
        isPiField = ui.switch("is connected over PI")

        nameField.set_value(node.name)
        ipField.set_value(node.ip)
        isPiField.set_value(node.isPi)

        ui.button('Save', on_click=lambda: update_node(node, nameField.value, ipField.value, isPiField.value, dialog))
    return dialog

def generate_mermaid_string():
    result = '''flowchart LR;\n'''
    for node in nodes:
        result += node_string.format(id=node.uuid, name=node.name, ip=node.ip, isPi=("Pi" if node.isPi else "ESP"))
    for node in nodes:
        for node2 in nodes[nodes.index(node)+1:]:
            result += f'''{node.uuid} <--> {node2.uuid};\n'''
    return result

def update_diagram():
    node_graph.set_content(generate_mermaid_string())

def edit_node(node: Node, card: ui.card):
    create_node_edit_dialog(node).open()

def remove_all_nodes():
    nodes.clear()
    container.clear()

def update_node(node: Node, name: str, ip: str, isPi: bool, dialog: ui.dialog):
    if node.name != name:
        ui.notify(f"Node {node.name} updated to {name}!")
    else:
        ui.notify(f"Node {node.name} updated!")

    node.name = name
    node.ip = ip
    node.isPi = isPi
    dialog.close()
    update_diagram()
    update_nodes()

def add_node_to_container(node: Node):
    with container:
        with ui.card() as tempCard:
            ui.label(node.name)
            ui.label("TYPE: " + ("Pi" if node.isPi else "ESP"))
            ui.label("IP: " + node.ip)
            with ui.row():
                with ui.button(icon='delete', on_click=lambda: remove_node(node, tempCard)):
                    ui.tooltip("Remove this Node")
                with ui.button(icon='edit', on_click=lambda: edit_node(node, tempCard)):
                    ui.tooltip("Edit this Node")

def update_nodes():
    container.clear()
    for node in nodes:
        add_node_to_container(node)

def remove_node(node: Node, card: ui.card):
    ui.notify(f"Node {node.name} removed!")
    nodes.remove(node)
    update_diagram()
    container.remove(list(container).index(card)) if list(container) else None

def add_node(node: Node, dialog: ui.dialog = None):
    if dialog:
        dialog.close()
    nodes.append(node)
    update_diagram()
    add_node_to_container(node)
    ui.notify(f"Node {node.name} added!")

def save_to_file():
    file = open("nodes.save","w")
    for node in nodes:
        file.write(str(node) + "\n")
    file.close()
    ui.notify("Saved to File 'nodes.save'!")

def load_from_file():
    remove_all_nodes()
    container.clear()
    file = open("nodes.save", "r")
    for line in file:
        add_node(Node(save_string=line))
    file.close()
    ui.notify("Loaded from File 'nodes.save'!")

add_dialog = create_node_dialog()

with ui.header():
    ui.label("Testsuit for ESP32 Network")



with ui.splitter().style("position: relative; min-height: 500px; margin: auto;") as splitter:
    with splitter.before:
        container = ui.row()
    with splitter.after:
        node_graph = ui.mermaid(generate_mermaid_string())

ui.separator().style("top: 50px; bottom: 50px;")

with ui.row().style("margin: auto;"):
    with ui.button(icon="add", on_click=add_dialog.open):
        ui.tooltip("Add a new Node")
    with ui.button(icon="save", on_click=save_to_file):
        ui.tooltip("Save to File 'nodes.save'")
    with ui.button(icon="file_open", on_click=load_from_file):
        ui.tooltip("Load from File 'nodes.save'")

ui.run(title="Testsuit")