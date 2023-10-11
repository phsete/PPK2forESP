import serial
from serial.tools import list_ports
import time

def get_time_in_ms():
    return int(time.time() * 1000)

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