from nicegui import ui
from typing import List
import uuid
from websockets import client
import json
from matplotlib import pyplot as plt
import plotly.express as px
import pandas as pd
import configparser
import helper
from contextlib import contextmanager

class Node:
    def __init__(self, name="", ip="", isPi=False, save_string: str = None, logger_version_to_flash = "latest") -> None:
        if not save_string:
            self.uuid = uuid.uuid4()
            self.name = name
            self.ip = ip
            self.isPi = isPi
            self.is_connected = False
            self.logger_version_to_flash = logger_version_to_flash
            self.averages = []
            self.data_samples = []
        else:
            strings = save_string[1:-2].split(",")
            self.uuid = uuid.UUID(strings[0])
            self.name = strings[1]
            self.ip = strings[2]
            self.isPi = strings[3] == "True"
            self.is_connected = False
            self.logger_version_to_flash = strings[4]
            self.averages = []
            self.data_samples = []
    def __str__(self) -> str:
        return f"({self.uuid},{self.name},{self.ip},{self.isPi},{self.logger_version_to_flash})"
    def __repr__(self):
        return str(self)
    async def connect_to_device(self):
        ui.notify(f"Node {self.name} trying to connect to device with ip {self.ip} ...")
        result = await send_json_data(f"ws://{self.ip}:{config['general']['WebsocketPort']}", {"type": "connection_test"})
        if result == "OK":
            self.is_connected = True
            update_diagram()
            update_nodes()
            ui.notify(f"Node {self.name} successfully connected to device with ip {self.ip} ...", type='positive')
        else:
            ui.notify(f"Node {self.name} could not connect to device with ip {self.ip} ...", type='negative')
    async def start_test(self, button: ui.button):
        with disable(button):
            result = json.loads(await send_json_data(f"ws://{self.ip}:{config['general']['WebsocketPort']}", {"type": "start_test", "version": self.logger_version_to_flash}))
            if result["status"] == "OK":
                self.averages = result["power_samples"]
                self.data_samples = result["data_samples"]
                ui.notify(f"Node {self.name} returned status of '{result['status']}' -> please update plots", type='positive')
            else:
                ui.notify(f"Node {self.name} returned status of '{result['status']}' -> no data available", type='negative', timeout=0, close_button="Dismiss")
    async def flash(self, button: ui.button):
        with disable(button):
            ui.notify(f"Node {self.name} trying to flash device with logger version {self.logger_version_to_flash} ...")
            result = await send_json_data(f"ws://{self.ip}:{config['general']['WebsocketPort']}", {"type": "flash", "version": self.logger_version_to_flash})
            if result == "OK":
                ui.notify(f"Node {self.name} successfully flashed device ...", type='positive')
            else:
                ui.notify(f"Node {self.name} could not flash ...", type='negative')

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
            result += f'''{node.uuid}{":::connected" if node.is_connected else ":::unconnected"} <--> {node2.uuid}{":::connected" if node2.is_connected else ":::unconnected"};\n'''
    result += "classDef connected fill:#0f0\n"
    result += "classDef unconnected fill:#f00\n"
    return result

def update_diagram():
    node_graph_container.clear()
    new_node_graph = ui.mermaid(generate_mermaid_string())
    new_node_graph.move(node_graph_container)

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
    node.is_connected = False
    dialog.close()
    update_diagram()
    update_nodes()

def version_select(node: Node, version_name):
    node.logger_version_to_flash = version_name
    return version_name

@contextmanager
def disable(button: ui.button) -> None:
    button.disable()
    with ui.row().classes("w-56") as row:
        ui.label("Running Test").classes("w-22 animate-pulse")
        ui.spinner(type="dots").classes("w-24")
        try:
            yield
        finally:
            row.delete()
            button.enable()

def add_node_to_container(node: Node):
    with container:
        with ui.card().classes('w-64') as tempCard:
            ui.label(node.name)
            ui.label("TYPE: " + ("Pi" if node.isPi else "ESP"))
            ui.label("IP: " + node.ip)
            with ui.row():
                ui.select(available_logger_versions, value=(node.logger_version_to_flash if node.logger_version_to_flash in available_logger_versions else version_select(node, available_logger_versions[0])), label="Flash Logger Version", on_change=lambda e: version_select(node, e.value)).classes('w-36')
                with ui.button(icon='play_arrow', on_click=lambda e: node.flash(e.sender)).classes('w-12'):
                    ui.tooltip("Start flashing logger version onto connected ESP32")
            with ui.row():
                with ui.button(icon='delete', on_click=lambda: remove_node(node, tempCard, container)):
                    ui.tooltip("Remove this Node")
                with ui.button(icon='edit', on_click=lambda: edit_node(node, tempCard)):
                    ui.tooltip("Edit this Node")
                if node.is_connected:
                    with ui.button(icon='play_arrow', on_click=lambda e: node.start_test(e.sender)):
                        ui.tooltip("Run test")
                if not node.is_connected:
                    with ui.button(icon='link', on_click=node.connect_to_device):
                        ui.tooltip("Connect Node to Device")

def update_nodes():
    container.clear()
    for node in nodes:
        add_node_to_container(node)

def remove_node(node: Node, card: ui.card, container):
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
        print(str(node))
        file.write(str(node) + "\n")
    file.close()
    ui.notify("Saved to File 'nodes.save'!")

def load_from_file(container):
    remove_all_nodes()
    container.clear()
    file = open("nodes.save", "r")
    for line in file:
        add_node(Node(save_string=line))
    file.close()
    ui.notify("Loaded from File 'nodes.save'!")

async def send_json_data(uri, data) -> str:
    message = json.dumps(data)
    try:
        async with client.connect(uri) as websocket:
            await websocket.send(message)
            print("outgoing message")# print(f">>> {message}")

            response = await websocket.recv()
            print("incoming message")# print(f"<<< {response}")
            return response
    except OSError as error:
        print(error)
        return "OSERR"
    except Exception as error:
        print(error)
        return "ERR"
    
async def update_plots():
    container_plots.clear()
    for node in nodes:
        with container_plots:
            with ui.card() as tempCard:
                ui.label(node.name)
                df = pd.DataFrame(dict(
                    x = [x[0] for x in node.averages],
                    y = [x[1] for x in node.averages],
                ))
                fig = px.line(
                    data_frame = df,
                    x = "x",
                    y = "y",
                    title = node.name,
                    labels=dict(x="Time [ms]", y="Power [uA]"))
                for data in node.data_samples:
                    fig.add_vline(
                        x=data[0], line_width=3, line_dash="dash", 
                        line_color="green",
                        annotation=dict(
                            text=data[1],
                            textangle=-90)
                        )
                ui.plotly(fig)

config = configparser.ConfigParser()
config.read("config.toml")

available_logger_versions = ["latest"] + [version["name"] for version in helper.get_suitable_releases_with_asset("sender.bin")]

add_dialog = create_node_dialog()

with ui.header():
    ui.label("Testsuit for Sensor Network")

with ui.splitter().style("position: relative; min-height: 500px; margin: auto;") as splitter:
    with splitter.before:
        container = ui.row()
    with splitter.after:
        node_graph_container = ui.row()
ui.separator().style("top: 50px; bottom: 50px;")

with ui.row().style("margin: auto;"):
    with ui.button(icon="add", on_click=add_dialog.open):
        ui.tooltip("Add a new Node")
    with ui.button(icon="save", on_click=save_to_file):
        ui.tooltip("Save to File 'nodes.save'")
    with ui.button(icon="file_open", on_click=lambda: load_from_file(container)):
        ui.tooltip("Load from File 'nodes.save'")
    with ui.button(icon="refresh", on_click=update_plots):
        ui.tooltip("Update Plots")

ui.separator().style("top: 50px; bottom: 50px;")

container_plots = ui.row()

ui.run(title="Testsuit")