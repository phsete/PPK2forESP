from argparse import ArgumentParser
from enum import Enum
import serial
from serial.tools import list_ports
import time
import configparser
import json
import requests
from pydantic import BaseModel
from typing import Optional, Dict, List
import os
import re
from uuid import UUID

BASE_DIR = os.path.dirname(os.path.realpath(__file__))

config = configparser.ConfigParser()
config.read(os.path.join(BASE_DIR, "config.toml"))

class Job(BaseModel):
    uuid: str
    version: str
    type: str
    protocol: str
    sleep_mode: str
    power_save_mode: str
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

def get_corrected_time():
    """
    Get approximated ntp time (based on NTP Delta and system time)
    """
    return get_system_time_in_ms()

def get_system_time_in_ms():
    """
    Get current time from system in ms
    """
    return time.time() * 1000

def find_serial_device(device_signature: str) -> str | None:
    candidates = list(list_ports.grep(device_signature))
    if not candidates:
        return None
    if len(candidates) > 1:
        exit(f'More than one device with signature {device_signature} found. Please remove every device that is not going to be used.')
    return candidates[0].device # type: ignore

def get_serial_device(device_signature: str):
    while not (port := find_serial_device(device_signature)):
        time.sleep(0.1)
        print("waiting for serial port to be available ...")

    serial_port = serial.Serial(port,
                                baudrate=115200,
                                timeout=1,
                                write_timeout=2)

    while(not serial_port.is_open):
        try:
            serial_port.open()
        except serial.SerialException as e:
            print("error opening serial device: " + str(e))
        time.sleep(0.1)
        print("waiting for serial port to be open ...")

    return serial_port

def get_suitable_releases_with_asset(asset_name):
    url = "https://api.github.com/repos/phsete/ESPNOWLogger/releases"
    response = requests.get(url, headers={'Authorization': 'token ' + config["general.github"]["Token"]})
    if response.status_code == 401:
        print("ERROR: PAT for github releases is not valid!")
        exit(1)
    suitable_releases = [{"name": release["name"], "assets": [{"name": asset["name"], "url": asset["url"]} for asset in release["assets"]]} for release in json.loads(response.content) if asset_name in [asset["name"] for asset in release["assets"]]]
    return suitable_releases

def get_suitable_releases_with_asset_regex(asset_name_regex):
    url = "https://api.github.com/repos/phsete/ESPNOWLogger/releases"
    response = requests.get(url, headers={'Authorization': 'token ' + config["general.github"]["Token"]})
    if response.status_code == 401:
        print("ERROR: PAT for github releases is not valid!")
        exit(1)
    suitable_releases = [{"name": release["name"], "assets": [{"name": asset["name"], "url": asset["url"]} for asset in release["assets"]]} for release in json.loads(response.content) if len(["MATCHED" for asset in release["assets"] if re.search(asset_name_regex, asset["name"]) != None]) > 0]
    return suitable_releases

def get_available_options(logger_version, available_releases):
    assets_with_options = []
    for asset in [version["assets"] for version in available_releases if version["name"] == logger_version][0]:
        if not asset["name"][0:16] == "sender-sdkconfig" and not asset["name"][0:18] == "receiver-sdkconfig":
            options = re.sub("^sender-|^receiver-", "", asset["name"]).split("-")
            options[len(options)-1] = options[len(options)-1][:-4] # remove .bin
            assets_with_options.append({"asset": asset, "options": options})
    return assets_with_options

def print_available_versions():
    available_releases = get_suitable_releases_with_asset_regex("sender-.*\.bin")
    available_logger_versions = [version["name"] for version in available_releases]
    print("Available Versions:")
    for version in available_logger_versions:
        print(version)
        
def print_available_options(logger_version):
    available_releases = get_suitable_releases_with_asset_regex("sender-.*\.bin")
    available_logger_versions = [version["name"] for version in available_releases]
    if logger_version in available_logger_versions:
        available_options = get_available_options(logger_version, available_releases)
        print("Available Options:")
        protocols = []
        sleep_modes = []
        power_save_modes = []
        for option_combination in available_options:
            protocols.append(option_combination["options"][0])
            sleep_modes.append(option_combination["options"][1])
            power_save_modes.append(option_combination["options"][2])
        protocols = list(dict.fromkeys(protocols))
        sleep_modes = list(dict.fromkeys(sleep_modes))
        power_save_modes = list(dict.fromkeys(power_save_modes))
        print(f"Protocols: {protocols}")
        print(f"Sleep Modes: {sleep_modes}")
        print(f"Power Save Modes: {power_save_modes}")
        return True
    else:
        print_available_versions()
        return False

def download_asset_from_release(asset_name, path, version="latest"):
    suitable_releases = get_suitable_releases_with_asset(asset_name)
    if(version == "latest"):
        version = suitable_releases[0]["name"]

    if(not any(release["name"] == version for release in suitable_releases)):
        exit("Specified Logger Version not found in Releases")

    assets = [release for release in suitable_releases if release["name"] == version][0]["assets"]
    sender_asset_url = [asset for asset in assets if asset["name"] == asset_name][0]["url"]

    response = requests.get(sender_asset_url, headers={'Authorization': 'token ' + config["general.github"]["Token"], 'Accept': 'application/octet-stream'})
    if(response.ok):
        with open(path, mode="wb") as file:
            file.write(response.content)
    else:
        exit("Download failed!")
        
exit_parser: ArgumentParser

class Color(Enum):
    RED = 31
    GREEN = 32
    YELLOW = 33
    
def set_exit_parser(parser: ArgumentParser):
    exit_parser = parser
    
def exit_error(message):
    if exit_parser != None:
        exit_parser.exit(message=f"\n\033[1;{Color.RED.value}m{message}\033[0m")
    else:
        print_colored(f"\n{message}", Color.RED)
        exit(0)
        
def print_colored(message, color: Color):
    print(f"\033[1;{color.value}m{message}\033[0m")