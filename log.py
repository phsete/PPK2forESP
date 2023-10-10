import serial
from serial.tools import list_ports
from ppk2_api.ppk2_api import PPK2_API
import time
# import matplotlib.pyplot as plt
from multiprocessing import Process, Manager
from serial.tools import list_ports
import esptool

def get_time_in_ms():
    return int(time.time() * 1000)

# def plot_graph(averages, data_samples):
#     x_val = [x[0] for x in averages]
#     y_val = [x[1] for x in averages]
#     print(x_val, y_val)
#     plt.plot(x_val, y_val)
#     plt.ylabel('Power [uA]')
#     plt.xlabel('Time after boot [ms]')
#     for data in data_samples:
#         plt.axvline(data[0], color='r', ls="--", lw=0.5)
#     plt.show()

def find_serial_device(device_signature: str):
    candidates = list(list_ports.grep(device_signature))
    if not candidates:
        return None
    if len(candidates) > 1:
        # Should throw an error: for debugging with two ESP32-C6 Devkits connected commented out!
        # raise ValueError(f'More than one device with signature {device_signature} found')
        return candidates[0].device
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

def start_sampling():
    ppk2_test.start_measuring()  # start measuring

    print("starting to sample ...")
    power_on = False
    # read measured values in a for loop like this:
    while not is_esp32_done.value:
        do_test_cycle(ppk2_test=ppk2_test, power_on=power_on)

    ppk2_test.stop_measuring()
    ppk2_test.toggle_DUT_power("OFF")

    # plot_power_averages(all_power_averages)

def log_esp32():
    while not is_esp32_powered.value:
        time.sleep(0.1)
        print("waiting for esp32 to be started")
    serial_device = get_serial_device("10c4:ea60") # ESP32-C6 Devkit-M has Vendor ID 303a and Product ID 1001 // UART Bridge: 10c4:ea60
    print("Serial device 0:", serial_device)         # check which port was really used
    # print("Serial device 1:" + serial_device_1.name)         # check which port was really used
    
    # Flash ESP before test run
    try:
        esptool.main(["-p", serial_device, "-b", "460800", "--before", "default_reset", "--after", "hard_reset", "--chip", "esp32c6", "write_flash", "--flash_mode", "dio", "--flash_size", "2MB", "--flash_freq", "80m", "0x10000", "firmware.bin"])
        # It worked! Display a nice green message
        print("Flash worked!")
    except:
        # It failed, just wait a second a try again
        print("Flash failed!")

    # Wait for the ESP to be ready (when it outputs "READY" to its serial)
    while((line := serial_device.readline()) != b'READY\r\n'):
        pass
    print("READY")
    line = serial_device.readline()   # read a '\n' terminated line => WARNING: waits for a line to be available
    stripped_line = line.decode('utf-8').strip()
    collected_data_samples.append((get_time_in_ms()-shared_time.value, stripped_line))
    print("LINE: ", stripped_line)

    serial_device.close()
    is_esp32_done.value = True

def start_test():
    print("Starting Test ...")
    init_values()
    if ppk2_port != None:
        sampler = Process(target=start_sampling)
        logger = Process(target=log_esp32)
        sampler.start()
        logger.start()
        sampler.join()
        logger.join()
        # plot_graph(collected_power_samples, collected_data_samples)
        return (collected_power_samples, collected_data_samples)
    else:
        print("Did not find PPK2 Serial Device!")

def do_test_cycle(ppk2_test, power_on):
    # print("Test Cycle ...")
    read_data = ppk2_test.get_data()
    if not power_on:
        power_on = True
        ppk2_test.toggle_DUT_power("ON")
        is_esp32_powered.value = True
    if read_data != b'':
        samples = ppk2_test.get_samples(read_data)
        power_samples = samples[0]
        average = sum(power_samples)/len(power_samples)
        collected_power_samples.append((get_time_in_ms()-shared_time.value, average))
        # print(f"Average of {len(power_samples)} samples is: {average}uA")
    time.sleep(0.00001)  # lower time between sampling -> less samples read in one sampling period

def init_values():
    is_esp32_powered.value = False
    is_esp32_done.value = False
    del collected_power_samples[:]
    del collected_data_samples[:]
    shared_time.value = get_time_in_ms()

# MAIN ENTRY POINT

if((ppk2_port := find_serial_device("PPK2")) == None):
    exit("ERROR: No PPK2 device found!")
print(ppk2_port)   
ppk2_test = PPK2_API(ppk2_port)  # serial port will be different for you
ppk2_test.get_modifiers()
ppk2_test.use_ampere_meter()  # set source meter mode
ppk2_test.set_source_voltage(3300)  # set source voltage in mV

manager = Manager()
is_esp32_powered = manager.Value('b', False)
is_esp32_done = manager.Value('b', False)
collected_power_samples = manager.list()
collected_data_samples = manager.list()
shared_time = manager.Value('i', get_time_in_ms())

if __name__ == '__main__':
    start_test()