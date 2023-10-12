from ppk2_api.ppk2_api import PPK2_API
from multiprocessing import Process, Manager
import esptool
import time
import helper

def start_sampling(ppk2_device):
    print("Sampling ESP32 with PPK2 ...")

    values = []

    # read measured values
    while not is_esp32_done.value:
        values.append((helper.get_time_in_ms(), ppk2_device.get_data()))
        time.sleep(1/100000)

    print("Finished sampling -> calculating values ...")

    for timestamp, value in values:
        if value != b'':
            samples, raw_output = ppk2_device.get_samples(value)
            average = sum(samples)/len(samples)
            collected_power_samples.append((timestamp-shared_time.value, average))

    print(f"Finished calculating values -> got {len(collected_power_samples)} averages")

def flash_esp32(vid_pid, ppk2_device=None):
    print("Flashing ESP32 ...")
    if ppk2_device:
        ppk2_device.toggle_DUT_power("ON")
    serial_device = helper.get_serial_device(vid_pid)
    
    command = ["-p", serial_device.port, "-b", "460800", "--before", "default_reset", "--after", "hard_reset", "--chip", "esp32c6", "write_flash", "--flash_mode", "dio", "--flash_size", "2MB", "--flash_freq", "80m", "0x10000", "firmware.bin"]
    print('Using command %s' % ' '.join(command))
    try:
        esptool.main(command)
        print("Finished flashing successfull")
    except:
        exit("Flash failed!")

    serial_device.close()
    if ppk2_device:
        ppk2_device.toggle_DUT_power("OFF")

def log_esp32(vid_pid, ppk2_device):
    print("Logging ESP32 ...")
    shared_time.value = helper.get_time_in_ms()
    ppk2_device.start_measuring()  # start measuring
    time.sleep(0.25) # give the PPK2 time to get the first valid measurement (first read values from PPK2 are just b'' for ~200ms)
    ppk2_device.toggle_DUT_power("ON")
    print("Powering up ESP32 ...")
    serial_device = helper.get_serial_device(vid_pid)

    # Wait for the ESP to be ready (when it outputs "READY" to its serial)
    while((line := serial_device.readline()) != b'READY\r\n'):
        pass
    while((line := serial_device.readline())[0:9] != b'ADC_VALUE'):
        pass
    collected_data_samples.append((helper.get_time_in_ms()-shared_time.value, line.decode('utf-8').strip().split(':')[1]))
    line = serial_device.readline()   # read a '\n' terminated line => WARNING: waits for a line to be available
    stripped_line = line.decode('utf-8').strip()
    collected_data_samples.append((helper.get_time_in_ms()-shared_time.value, stripped_line))

    serial_device.close()
    print("Finished logging -> powering down ESP32 ...")
    ppk2_device.toggle_DUT_power("OFF")
    time.sleep(0.1)
    ppk2_device.stop_measuring()
    is_esp32_done.value = True

def get_PPK2():
    print("Looking for PPK2 device ...")
    if((ppk2_port := helper.find_serial_device("PPK2")) == None):
        exit("ERROR: No PPK2 device found!")
    ppk2 = PPK2_API(ppk2_port)
    ppk2.get_modifiers()
    ppk2.use_ampere_meter()
    ppk2.set_source_voltage(3300)  # set source voltage in mV
    print("Found and configured PPK2 device")
    return ppk2

def start_test(esp32_vid_pid, ppk2_device, flash=True):
    print("Starting Test ...")

    if(flash):
        flash_esp32(vid_pid=esp32_vid_pid, ppk2_device=ppk2_device)

    init_values()

    sampler = Process(target=start_sampling, args={ppk2_device})
    logger = Process(target=log_esp32, args=(esp32_vid_pid, ppk2_device))

    sampler.start()
    logger.start()
    sampler.join()
    logger.join()
    print("Finished Test")

    return (collected_power_samples, collected_data_samples)

def init_values():
    print("Resetting values for new Test run ...")
    is_esp32_done.value = False
    del collected_power_samples[:]
    del collected_data_samples[:]
    shared_time.value = 0

# MAIN ENTRY POINT

manager = Manager()
is_esp32_done = manager.Value('b', False)
collected_power_samples = manager.list()
collected_data_samples = manager.list()
shared_time = manager.Value('i', 0)

if __name__ == '__main__':
    start_test(esp32_vid_pid="10c4:ea60", ppk2_device=get_PPK2(), flash=False)