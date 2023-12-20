from nicegui import ui
from typing import Any, Dict, Generator, List, Optional
from uuid import UUID, uuid4
from websockets import client
import json
import plotly.graph_objects as go
import plotly.colors as plotly_colors
import configparser

import websockets.typing
import helper
from contextlib import contextmanager, suppress
import requests
import time
from datetime import datetime
import asyncio
from pydantic import BaseModel

class Job(BaseModel):
    uuid: str
    version: str
    type: str
    started_at: float
    averages: Optional[List[Dict]] = []
    data_samples: Optional[List[Dict]] = []

    def add_data(self, averages: List[Dict], data_samples: List[Dict]):
        if self.averages:
            self.averages.extend(averages)
        else:
            self.averages = averages
        
        if self.data_samples:
            self.data_samples.extend(data_samples)
        else:
            self.data_samples = data_samples

class Periodic:
    def __init__(self, func, time):
        self.func = func
        self.time = time
        self.is_started = False
        self._task = None

    async def start(self):
        if not self.is_started:
            self.is_started = True
            # Start task to call func periodically:
            self._task = asyncio.ensure_future(self._run())

    async def stop(self):
        if self.is_started:
            self.is_started = False
            # Stop task and await it stopped:
            self._task.cancel()
            with suppress(asyncio.CancelledError):
                await self._task

    async def _run(self):
        while True:
            await asyncio.sleep(self.time)
            await self.func()

class Data:
    def __init__(self, uuid: str | None = None, value: int | None = None, created_by_mac: str | None = None, crc_equal: bool | None = None, timestamp_send: float | None = None, timestamp_recv: float | None = None):
        self.uuid = uuid
        self.value = value
        self.created_by_mac = created_by_mac
        self.timestamp_send = timestamp_send
        self.timestamp_recv = timestamp_recv
        self.crc_equal = crc_equal

    def parse_sender_data(self, value: int, uuid: str, created_by_mac: str, timestamp: float):
        self.uuid = uuid
        self.created_by_mac = created_by_mac
        self.timestamp_send = timestamp

    def parse_receiver_data(self, value: int, uuid: str, created_by_mac: str, crc_equal: bool, timestamp: float):
        self.value = value
        self.crc_equal = crc_equal
        self.timestamp_recv = timestamp

    def add_to_table(self, table: ui.table):
        if self.crc_equal == "1":
            crc_str = "True"
        else:
            crc_str = "False"
        print(f"{self.uuid}: {self.timestamp_recv}, {self.timestamp_send}")
        if self.timestamp_send and self.timestamp_recv:
            table.add_rows({'uuid': self.uuid, 'value': self.value, 'created_by': self.created_by_mac, 'crc_equal': crc_str, 'timestamp_send': "{:.2f} ms".format(self.timestamp_send), 'timestamp_recv': "{:.2f} ms".format(self.timestamp_recv), 'latency': "{:.2f} ms".format(self.timestamp_recv-self.timestamp_send)})
        else:
            table.add_rows({'uuid': self.uuid, 'value': "ERROR"})

class Node:
    def __init__(self, name="", ip="", isPi=False, save_string: str | None = None, logger_version_to_flash = "latest", logger_type = "sender") -> None:
        if not save_string:
            self.uuid = uuid4()
            self.name = name
            self.ip = ip
            self.isPi = isPi
            self.is_connected = False
            self.is_running = False
            self.logger_version_to_flash = logger_version_to_flash
            self.logger_type = logger_type
            self.jobs = {}
            self.rendered_plot_once = False
        else:
            strings = save_string[1:-2].split(",")
            self.uuid = UUID(strings[0])
            self.name = strings[1]
            self.ip = strings[2]
            self.isPi = strings[3] == "True"
            self.is_running = False
            self.is_connected = False
            self.logger_version_to_flash = strings[4]
            self.logger_type = strings[5]
            self.jobs = {} # could be saved and reloaded here
            self.rendered_plot_once = False
        self.plot_dialog = create_plot_dialog()
    def __str__(self) -> str:
        return f"({self.uuid},{self.name},{self.ip},{self.isPi},{self.logger_version_to_flash},{self.logger_type})"
    def __repr__(self):
        return str(self)
    async def connect_to_device(self, button: ui.button):
        with disable(button, "Connect to device"):
            try:
                ui.notify(f"Node {self.name} trying to connect to device with ip {self.ip} ...")
                loop = asyncio.get_event_loop()
                future1 = loop.run_in_executor(None, lambda: requests.get(f"http://{self.ip}:{config['general']['APIPort']}/", timeout=5))
                response = await future1
                result = response.json()
                print(result["status"])
                if result["status"] == "OK" or result["status"] == "stopped":
                    self.is_connected = True
                    update_diagram()
                    update_nodes()
                    ui.notify(f"Node {self.name} successfully connected to device with ip {self.ip} ...", type='positive')
                else:
                    ui.notify(f"Node {self.name} could not connect to device with ip {self.ip} ...", type='negative') # throws KeyError: 60?!
            except requests.exceptions.ConnectTimeout or requests.exceptions.ConnectionError:
                ui.notify(f"Node {self.name} could not connect to device with ip {self.ip} ...", type='negative')
    async def start_test(self, button: ui.button):
        with disable(button, "Starting Test"):
            try:
                loop = asyncio.get_event_loop()
                # print(f"Started test at NTP Time: {helper.get_ntp_time_in_ms()}")
                future1 = loop.run_in_executor(None, lambda: requests.post(f"http://{self.ip}:{config['general']['APIPort']}/start", params={"version": self.logger_version_to_flash, "node_type": self.logger_type}, timeout=10)) # missing: "version": self.logger_version_to_flash
                response = await future1
                result = response.json()
                if result["status"] == "OK" or result["status"] == "started" or result["status"] == "created":
                    latest_job_uuid = result["uuid"]
                    self.jobs[latest_job_uuid] = Job(version=self.logger_version_to_flash, type=self.logger_type, uuid=str(latest_job_uuid), started_at=time.time() * 1000)
                    ui.notify(f"Node {self.name} started test successfully with status of '{result['status']}'", type='positive')
                    time.sleep(3)
                    future2 = loop.run_in_executor(None, lambda: requests.get(f"http://{self.ip}:{config['general']['APIPort']}/status/", params={"uuid": result["uuid"]}, timeout=10)) # missing: "version": self.logger_version_to_flash
                    response2 = await future2
                    print(response2.text)
                    result2 = response2.json()
                    if not(result2["status"] == "OK" or result2["status"] == "started" or result2["status"] == "created"):
                        # Error
                        ui.notify(f"Node {self.name} could not start test with status of '{result2['status']}' -> please retry", type='negative', timeout=0, close_button="Dismiss")
                    else:
                        self.is_running = True
                        update_nodes()
                else:
                    ui.notify(f"Node {self.name} could not start test with status of '{result['status']}' -> please retry", type='negative', timeout=0, close_button="Dismiss")
            except requests.exceptions.ConnectTimeout or requests.exceptions.ConnectionError:
                ui.notify(f"Node {self.name} could not connect to device with ip {self.ip} ...", type='negative')
    async def sync_time(self, button: ui.button):
        with disable(button, "Syncing Time"):
            try:
                loop = asyncio.get_event_loop()
                future1 = loop.run_in_executor(None, lambda: requests.post(f"http://{self.ip}:{config['general']['APIPort']}/sync", timeout=10))
                response = await future1
                result = response.json()
                if result["status"] == "OK":
                    ui.notify(f"Node {self.name} synced time successfully with status of '{result['status']}'", type='positive')
                else:
                    ui.notify(f"Node {self.name} could not synced time with status of '{result['status']}' -> please retry", type='negative', timeout=0, close_button="Dismiss")
            except requests.exceptions.ConnectTimeout or requests.exceptions.ConnectionError:
                ui.notify(f"Node {self.name} could not connect to device with ip {self.ip} ...", type='negative')
    async def flash(self, button: ui.button):
        with disable(button, "Flashing device"):
            try:
                ui.notify(f"Node {self.name} trying to flash device with logger version {self.logger_version_to_flash} ...")
                loop = asyncio.get_event_loop()
                future1 = loop.run_in_executor(None, lambda: requests.post(f"http://{self.ip}:{config['general']['APIPort']}/flash/", params={"version": self.logger_version_to_flash, "node_type": self.logger_type}, timeout=60))
                response = await future1
                result = response.json()
                if result["status"] == "OK":
                    ui.notify(f"Node {self.name} successfully flashed device ...", type='positive')
                else:
                    ui.notify(f"Node {self.name} could not flash ...", type='negative')
            except requests.exceptions.ConnectTimeout or requests.exceptions.ConnectionError:
                ui.notify(f"Node {self.name} could not connect to device with ip {self.ip} ...", type='negative')
    async def get_jobs(self):
        try:
            if(self.is_connected):
                loop = asyncio.get_event_loop()
                future1 = loop.run_in_executor(None, lambda: requests.get(f"http://{self.ip}:{config['general']['APIPort']}/jobs", timeout=3600))
                response = await future1
                result = response.json()
                for uuid in [*result]:
                    print("Result has length: ", len(result[uuid]["collected_power_samples"]))
                    self.jobs[uuid].add_data(averages=[{"time": value[0], "value": value[1]} for value in result[uuid]["collected_power_samples"]], data_samples=[{"time": value[0], "value": value[1]} for value in result[uuid]["collected_data_samples"]])
                # print(f"Job UUID's: {[*result]}") # get the first key of the json response
                for key, job in self.jobs.items():
                    with open(f"result-{datetime.fromtimestamp(job.started_at / 1000).strftime('%y%m%d%H%M%S')}-node-{self.uuid}-job-{job.uuid}.json", "w") as outfile:
                        outfile.write(job.model_dump_json(indent=4))
            else:
                ui.notify(f"Node {self.name} not connected -> skipping plot update for this node ...", type='info')
        except requests.exceptions.ConnectTimeout or requests.exceptions.ConnectionError:
            ui.notify(f"Node {self.name} could not connect to device with ip {self.ip} ...", type='negative')
    async def stop_all(self, button: ui.button):
        with disable(button, "Stopping all jobs"):
            try:
                if(self.is_connected):
                    loop = asyncio.get_event_loop()
                    future1 = loop.run_in_executor(None, lambda: requests.get(f"http://{self.ip}:{config['general']['APIPort']}/stop/", timeout=3600))
                    response = await future1
                    print(response)
                    result = response.json()
                    ui.notify(f"Node {self.name} stopping all tests ...", type='positive')
                    time.sleep(5) # wait for possible calculation to finish
                    future2 = loop.run_in_executor(None, lambda: requests.get(f"http://{self.ip}:{config['general']['APIPort']}/", timeout=3600))
                    response2 = await future2
                    print(response2.text)
                    result2 = response2.json()
                    if result2["status"] == "stopped":
                        self.is_running = False
                        if poll_periodic:
                            await poll_periodic.stop()
                        ui.notify(f"Node {self.name} stopped all tests successfully", type='positive')
                    else:
                        ui.notify(f"Node {self.name} could not stop all tests -> please retry", type='negative')
                else:
                    ui.notify(f"Node {self.name} not connected -> skipping stop for this node ...", type='info')
            except requests.exceptions.ConnectTimeout or requests.exceptions.ConnectionError:
                ui.notify(f"Node {self.name} could not connect to device with ip {self.ip} ...", type='negative')
    async def update_plot(self, button: ui.button):
        self.plot_dialog.clear()
        with self.plot_dialog:
            temp_card = ui.card()
        with disable(button, "Updating Plot", container=temp_card, remove_container_afterwards=True):
            self.plot_dialog.open()
            await self.get_jobs()
            with self.plot_dialog:
                fig = go.Figure()
                fig.update_layout(legend_title_text="Jobs", title=self.name)
                fig.update_xaxes(title_text="Time [ms]")
                fig.update_yaxes(title_text="Power [uA]")
                i = 0
                for key, job in self.jobs.items():
                    fig.add_trace(go.Scatter(x=[x.get("time") for x in job.averages], y=[x.get("value") for x in job.averages], line=dict(color=plotly_colors.qualitative.Plotly[i]), mode="lines", name=f"{i}: {job.uuid}"))
                    for data in job.data_samples:
                        fig.add_vline(
                            x=data.get("time"), line_width=3, line_dash="dash", 
                            line_color=plotly_colors.qualitative.Plotly[i],
                            annotation=dict(
                                text=f"{i}: {data.get('value')}",
                                textangle=-90)
                            )
                    i += 1
                with ui.card().classes("w-full h-full").style("max-width: None"):
                    ui.plotly(fig).classes("w-full max-w-none").style("max-width: none; height: calc(100% - 60px);")
                    with ui.row():
                        ui.button("Update", on_click=lambda e: self.update_plot(e.sender))
                        ui.button("Close", on_click=self.plot_dialog.close)
    async def show_plot(self, button: ui.button):
        if self.rendered_plot_once:
            self.plot_dialog.open()
        else:
            await self.update_plot(button)
            self.rendered_plot_once = True
    async def change_type(self, switch: ui.switch):
        print(switch.value)
        if switch.value == True:
            self.logger_type = "receiver"
        else:
            self.logger_type = "sender"

async def start_poll():
    global poll_periodic
    poll_periodic = Periodic(update_table, 10)
    await poll_periodic.start()

nodes : List[Node] = []

data_values: Dict[str, Data] = {}

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

def create_plot_dialog():
    with ui.dialog() as dialog:
        pass
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
def disable(button: ui.button, status_text, container=None, remove_container_afterwards=False) -> Generator[Any, Any, Any]:
    button.disable()
    with ui.row().classes("w-56") as row:
        ui.label(status_text).classes("w-22 animate-pulse")
        ui.spinner(type="dots").classes("w-24")
        if(container):
            row.move(container)
        try:
            yield
        finally:
            row.delete()
            button.enable()
            if remove_container_afterwards:
                if container:
                    container.delete()

def add_node_to_container(node: Node):
    with container:
        with ui.card().classes('w-64') as tempCard:
            ui.label(node.name)
            ui.label("TYPE: " + ("Pi" if node.isPi else "ESP"))
            ui.label("IP: " + node.ip)
            with ui.row():
                ui.label("Sender")
                ui.switch("Receiver", value=node.logger_type == "receiver",on_change=lambda e: node.change_type(e.sender))
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
                    with ui.button(icon='close', on_click=lambda e: node.stop_all(e.sender)):
                        ui.tooltip("Stop test")
                    with ui.button(icon='play_arrow', on_click=lambda e: node.start_test(e.sender)):
                        ui.tooltip("Run test")
                    with ui.button(icon="refresh", on_click=lambda e: node.show_plot(e.sender)):
                        ui.tooltip("Show Plot")
                if not node.is_connected:
                    with ui.button(icon='link', on_click=lambda e: node.connect_to_device(e.sender)):
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

def add_node(node: Node, dialog: ui.dialog | None = None):
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

async def update_data_values():
    for node in nodes:
        await node.get_jobs()
        for key, job in node.jobs.items():
            for data in job.data_samples:
                raw_value = str(data.get("value"))
                text = raw_value.split(';')
                if len(text) > 1 :
                    if len(text) > 3: # not a good way to filter this -> crc_equal could be set as None
                        # should be receiver
                        value, uuid, created_by_mac, crc_equal = text
                        if uuid not in data_values.keys():
                            data_values[uuid] = Data()
                        data_values[uuid].parse_receiver_data(int(value), uuid, created_by_mac, bool(crc_equal), data.get("time"))
                    else:
                        # should be sender
                        value, uuid, created_by_mac = text
                        if uuid not in data_values.keys():
                            data_values[uuid] = Data()
                        data_values[uuid].parse_sender_data(int(value), uuid, created_by_mac, data.get("time"))

async def update_table():
    table_area.clear()
    with table_area:
        columns = [
            {'name': 'uuid', 'label': 'UUID', 'field': 'uuid'},
            {'name': 'value', 'label': 'Value', 'field': 'value'},
            {'name': 'created_by', 'label': 'Created By [MAC]', 'field': 'created_by'},
            {'name': 'crc_equal', 'label': 'CRC Equal', 'field': 'crc_equal'},
            {'name': 'timestamp_send', 'label': 'Timestamp Sender', 'field': 'timestamp_send'},
            {'name': 'timestamp_recv', 'label': 'Timestamp Receiver', 'field': 'timestamp_recv'},
            {'name': 'latency', 'label': 'Latency', 'field': 'latency'},
        ]
        table = ui.table(columns=columns, rows=[], row_key='uuid').classes('w-full')
        with table.add_slot('top-left'):
            def toggle() -> None:
                table.toggle_fullscreen()
                button.props('icon=fullscreen_exit' if table.is_fullscreen else 'icon=fullscreen')
            button = ui.button('Toggle fullscreen', icon='fullscreen', on_click=toggle).props('flat')
    await update_data_values()
    print(data_values)
    for uuid, data in data_values.items():
        data.add_to_table(table)
                    

async def send_json_data(uri, data) -> websockets.typing.Data:
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
    with ui.button(icon="refresh", on_click=lambda: update_table()):
        ui.tooltip("Update Table")
    with ui.button(icon="replay_10", on_click=start_poll): # type: ignore
        ui.tooltip("Update Table")

ui.separator().style("top: 50px; bottom: 50px;")

table_area = ui.row()

ui.run(title="Testsuit")