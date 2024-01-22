from ppk2_api.ppk2_api import PPK2_API
from threading import Thread, Event
from ctypes import c_char_p
import esptool
import time
import helper
import os

ppk2_device_temp: PPK2_API | None = None

def start_sampling(ppk2_device):
    global is_sampling
    global log_status
    global value_buffer

    print("Sampling ESP32 with PPK2 ...")
    is_sampling = True
    try:

        # read measured values
        while not is_esp32_done.is_set():
            value_buffer.append((helper.get_corrected_time(), ppk2_device.get_data()))
            time.sleep(1/100000)


        print("Finished sampling")
    except:
        log_status = "Unknown Error while sampling data!"
        print(log_status)
    is_sampling = False

def flash_esp32(vid_pid, ppk2_device=None):
    print("Flashing ESP32 ...")
    if ppk2_device:
        ppk2_device.toggle_DUT_power("ON")
    serial_device = helper.get_serial_device(vid_pid)
    
    command = ["-p", serial_device.port, "-b", "460800", "--before", "default_reset", "--after", "hard_reset", "--chip", "esp32c6", "write_flash", "--flash_mode", "dio", "--flash_size", "2MB", "--flash_freq", "80m", "0x10000", os.path.join(helper.BASE_DIR, "firmware.bin")]
    print('Using command %s' % ' '.join(command))
    try:
        esptool.main(command)
        print("Finished flashing successfull")
    except:
        exit("Flash failed!")

    serial_device.close()
    if ppk2_device:
        ppk2_device.toggle_DUT_power("OFF")

def process_log_message(line):
    global collected_data_samples
    if(line[0:3] == b'LOG'):
        split_log = line.decode('utf-8').strip().split(':')
        collected_data_samples.append((helper.get_corrected_time(), split_log[1]))
        if helper.config["node"]["PrintLogs"] == "True":
            print(f"LOG: {split_log[1]}")

def process_serial(line, node_type, version, latest_version, change_status, log_status, calculate_values):
    match line[0:4]:
        case b'Hell':
            log_status = check_version(line, node_type, version, latest_version, change_status, log_status)
        case b'READ':
            pass
        case b'ADC_' | b'RECV':
            collected_data_samples.append((helper.get_corrected_time(), line.decode('utf-8').strip().split(':')[1]))
            calculate_values()
        case _:
            process_log_message(line)

    return log_status

def check_version(line, node_type, version, latest_version, change_status, log_status):
    device_info = line.decode('utf-8').strip().split(':')
    print(f"Type: {device_info[1]}, Version: {device_info[2]}")

    if device_info[1] != node_type:
        log_status = f"Wrong device type! -> has type {device_info[1]} ... should be type {node_type}"
    if version != "debug" and device_info[2] == "not set":
        log_status = "Device Version not set!"
    elif (version != "debug" and version != "latest" and device_info[2] != version) or (version != "debug" and version == "latest" and device_info[2] != latest_version):
        log_status = f"Wrong version installed on ESP32 -> has version {device_info[2]} ... should be version {version}"

    print(f"Version check: {log_status}")
    if change_status:
        change_status(log_status)
    return log_status

def log_esp32(vid_pid, ppk2_device, version, change_status, calculate_values, node_type="sender"):
    global log_status
    global collected_data_samples
    global shared_time

    print("Logging ESP32 ...")
    latest_version = helper.get_suitable_releases_with_asset(f"{node_type}.bin")[0]
    shared_time = helper.get_system_time_in_ms()
    print(f"Started test at NTP Time: {shared_time}")
    ppk2_device.start_measuring()  # start measuring
    time.sleep(0.25) # give the PPK2 time to get the first valid measurement (first read values from PPK2 are just b'' for ~200ms)
    ppk2_device.toggle_DUT_power("ON")
    if log_status != "OK":
        return
    print("Powering up ESP32 ...")
    serial_device = helper.get_serial_device(vid_pid)

    while not is_stopped.is_set():
        log_status = process_serial(serial_device.readline(), node_type, version, latest_version, change_status, log_status, calculate_values)

    serial_device.close()
    print("Finished logging -> powering down ESP32 ...")
    ppk2_device.toggle_DUT_power("OFF")
    time.sleep(0.1)
    ppk2_device.stop_measuring()
    is_esp32_done.set()

def get_PPK2() -> PPK2_API | None:
    """Get a connected PPK2 device.

    Returns:
        PPK2_API | None: Returns a PPK2_API object if a PPK2 device was found. Returns None if none was found.
    """
    print("Looking for PPK2 device ...")
    ppk2 = None
    try:
        if((ppk2_port := helper.find_serial_device("PPK2")) == None):
            log_status = "ERROR: No PPK2 device found!"
            print(log_status)
            return
        ppk2 = PPK2_API(ppk2_port)
        ppk2.get_modifiers()
        ppk2.use_ampere_meter()
        ppk2.set_source_voltage(3300)  # set source voltage in mV
        print("Found and configured PPK2 device")
    except:
        log_status = "Unknown Error while looking for PPK2 device!"
        print(log_status)
    
    return ppk2

def start_test(esp32_vid_pid, ppk2_device, version, flash=True, callback=None, change_status=None, node_type="sender", calculate_values=None):
    print("Starting Test ...")

    if(flash):
        flash_esp32(vid_pid=esp32_vid_pid, ppk2_device=ppk2_device)

    init_values()
    print(value_buffer)

    sampler = Thread(target=start_sampling, args={ppk2_device})
    logger = Thread(target=log_esp32, args=(esp32_vid_pid, ppk2_device, version, change_status, calculate_values, node_type))

    sampler.start()
    logger.start()
    sampler.join()
    logger.join()
    print("Finished Test")

    if callback and not is_stopped.is_set():
        callback(log_status)

def init_values():
    print("Resetting values for new Test run ...")
    global is_sampling
    global log_status
    global collected_power_samples
    global collected_data_samples
    global shared_time
    global value_buffer
    is_esp32_done.clear()
    is_stopped.clear()
    is_sampling = False
    log_status = "OK"
    collected_power_samples = []
    collected_data_samples = []
    shared_time = 0
    value_buffer = []

# MAIN ENTRY POINT

is_esp32_done = Event()
is_stopped = Event()
is_sampling = False
log_status = "OK"
collected_power_samples = []
collected_data_samples = []
shared_time = 0
value_buffer = []

if __name__ == '__main__':
    start_test(esp32_vid_pid="10c4:ea60", ppk2_device=get_PPK2(), version="debug", flash=False)