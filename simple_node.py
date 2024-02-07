import time
from uuid import UUID, uuid4
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from datetime import datetime
import os
import helper
from helper import print_colored, exit_error, Color

session = requests.Session()
retry = Retry(connect=3)
adapter = HTTPAdapter(max_retries=retry)
session.mount('http://', adapter)
session.mount('https://', adapter)

class SimpleNode:
    def __init__(self, save_string: str, run_uuid: UUID) -> None:
            strings = save_string[1:-2].split(",")
            self.uuid = UUID(strings[0])
            self.name = strings[1]
            self.ip = strings[2]
            self.isPi = strings[3] == "True"
            self.version = strings[4]
            self.type = strings[5]
            self.sleep_mode = strings[6]
            self.power_save_mode = strings[7]
            self.jobs = {}
            self.run_uuid = run_uuid
            self.started_at = 0
    
    def ping(self):
        try:
            print_colored(f"Node {self.name} trying to connect to device with ip {self.ip} ...", Color.YELLOW)
            response = session.get(f"http://{self.ip}:{helper.config['general']['APIPort']}/", timeout=5)
            result = response.json()
            print_colored(f"Node {self.name} responded with status {result['status']}", Color.GREEN)
        except requests.exceptions.ConnectTimeout:
            exit_error(f"No response from node {self.name} with ip/hostname {self.ip}!\nConnectTimeout")
        except requests.exceptions.ConnectionError:
            exit_error(f"No response from node {self.name} with ip/hostname {self.ip}!\nConnectionError")
            
    def start_test(self):
        try:
            response = session.post(f"http://{self.ip}:{helper.config['general']['APIPort']}/start/", params={"version": f"{self.version}-{self.sleep_mode}-{self.power_save_mode}", "node_type": self.type}, timeout=5)
            result = response.json()
            self.started_at = time.time()
            if result["status"] == "OK" or result["status"] == "started" or result["status"] == "created":
                print_colored(f"Node {self.name} started test successfully with status of '{result['status']}'", Color.GREEN)
                response2 = session.get(f"http://{self.ip}:{helper.config['general']['APIPort']}/status/", params={"uuid": result["uuid"]}, timeout=10)
                result2 = response2.json()
                if not(result2["status"] == "OK" or result2["status"] == "started" or result2["status"] == "created"):
                    # Error
                    exit_error(f"Node {self.name} could not start test with status of '{result2['status']}' -> please retry")
                else:
                    print_colored(f"Node {self.name} started test with status of '{result2['status']}'", Color.GREEN)
            else:
                exit_error(f"Node {self.name} could not start test with status of '{result['status']}' -> please retry")
        except requests.exceptions.ConnectTimeout:
            exit_error(f"Node {self.name} could not connect to device with ip {self.ip} ...\nConnectTimeout")
        except requests.exceptions.ConnectionError:
            exit_error(f"Node {self.name} could not connect to device with ip {self.ip} ...\nConnectionError")
            
    def stop_test(self, collect_data = True):
        try:
            print_colored(f"Node {self.name} stopping all tests ...", Color.YELLOW)
            response = session.get(f"http://{self.ip}:{helper.config['general']['APIPort']}/stop/", timeout=60)
            if collect_data:
                result = response.json()
                result.pop("status")
                self.process_data(result)
            print_colored(f"Node {self.name} successfully stopped all tests!", Color.GREEN)
            time.sleep(1) # wait a bit for ppk2 to reset
        except requests.exceptions.ConnectTimeout:
            exit_error(f"Node {self.name} could not stop tests ...\nConnectTimeout")
        except requests.exceptions.ConnectionError:
            exit_error(f"Node {self.name} could not stop tests ...\nConnectionError")
            
    def get_data(self):
        try:
            response = session.get(f"http://{self.ip}:{helper.config['general']['APIPort']}/jobs", timeout=60)
            result = response.json()
            self.process_data(result)
        except requests.exceptions.ConnectTimeout:
            exit_error(f"Node {self.name} could not connect to device with ip {self.ip} ...\nConnectTimeout")
        except requests.exceptions.ConnectionError:
            exit_error(f"Node {self.name} could not connect to device with ip {self.ip} ...\nConnectionError")
            
    def process_data(self, data):
        for uuid in [*data]:
            print(f"Received Job Data from {self.name} with length of ", len(data[uuid]["collected_power_samples"]))
            if not uuid in self.jobs:
                self.jobs[uuid] = helper.Job(uuid=uuid, version=self.version, type=self.type, sleep_mode=self.sleep_mode, power_save_mode=self.power_save_mode, started_at=self.started_at)
            self.jobs[uuid].add_data(averages=[{"time": value[0], "value": value[1]} for value in data[uuid]["collected_power_samples"]], data_samples=[{"time": value[0], "value": value[1]} for value in data[uuid]["collected_data_samples"]])
        for key, job in self.jobs.items():
            with open(os.path.join(helper.BASE_DIR, f"result-{datetime.fromtimestamp(job.started_at).strftime('%y%m%d%H%M%S')}-node-{self.uuid}-job-{job.uuid}-run-{self.run_uuid}.json"), "w") as outfile:
                outfile.write(job.model_dump_json(indent=4))
                
    def flash(self):
        try:
            print_colored(f"Node {self.name} trying to flash device with logger version {self.version} and option {self.type}-{self.sleep_mode}-{self.power_save_mode} ...", Color.YELLOW)
            response = session.post(f"http://{self.ip}:{helper.config['general']['APIPort']}/flash/", params={"version": self.version, "node_type": f"{self.type}-{self.sleep_mode}-{self.power_save_mode}"}, timeout=60)
            result = response.json()
            if result["status"] == "OK":
                print_colored(f"Node {self.name} successfully flashed device ...", Color.GREEN)
                time.sleep(1) # wait a bit for ppk2 to reset
            else:
                exit_error(f"Node {self.name} could not flash ...")
        except requests.exceptions.ConnectTimeout:
            exit_error(f"Node {self.name} could not connect to device with ip {self.ip} ...\nConnectTimeout")
        except requests.exceptions.ConnectionError:
            exit_error(f"Node {self.name} could not connect to device with ip {self.ip} ...\nConnectionError")