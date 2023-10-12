import serial
from serial.tools import list_ports
import time
import configparser
import json
import requests

config = configparser.ConfigParser()
config.read("config.toml")

def get_time_in_ms():
    return time.time() * 1000

def find_serial_device(device_signature: str):
    candidates = list(list_ports.grep(device_signature))
    if not candidates:
        return None
    if len(candidates) > 1:
        exit(f'More than one device with signature {device_signature} found. Please remove every device that is not going to be used.')
    return candidates[0].device

def get_serial_device(device_signature: str):
    while not (port := find_serial_device(device_signature)):
        time.sleep(0.1)
        print("waiting for serial port to be available ...")

    serial_port = serial.Serial(port, baudrate=115200)

    while(not serial_port.is_open):
        time.sleep(0.1)
        print("waiting for serial port to be open ...")

    return serial_port

def get_suitable_releases_with_asset(asset_name):
    url = "https://api.github.com/repos/phsete/ESPNOWLogger/releases"
    response = requests.get(url, headers={'Authorization': 'token ' + config["general.github"]["Token"]})
    suitable_releases = [{"name": release["name"], "assets": [{"name": asset["name"], "url": asset["url"]} for asset in release["assets"]]} for release in json.loads(response.content) if asset_name in [asset["name"] for asset in release["assets"]]]
    return suitable_releases

def download_asset_from_release(asset_name, path, version="latest"):
    suitable_releases = get_suitable_releases_with_asset(asset_name)
    if(version == "latest"):
        version = suitable_releases[0]["name"]

    if(not any(release["name"] == version for release in suitable_releases)):
        exit("Specified Logger Version not found in Releases")

    assets = [release for release in suitable_releases if release["name"] == version][0]["assets"]
    sender_asset_url = [asset for asset in assets if asset["name"] == "sender.bin"][0]["url"]

    response = requests.get(sender_asset_url, headers={'Authorization': 'token ' + config["general.github"]["Token"], 'Accept': 'application/octet-stream'})
    if(response.ok):
        with open(path, mode="wb") as file:
            file.write(response.content)
    else:
        exit("Download failed!")