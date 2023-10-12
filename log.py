from ppk2_api.ppk2_api import PPK2_API
from multiprocessing import Process, Manager
import esptool
import time
import helper

def start_sampling(ppk2_device):
    print("Sampling ESP32 with PPK2 ...")

    ppk2_device.toggle_DUT_power("ON")

    ppk2_device.start_measuring()  # start measuring

    # read measured values in a for loop like this:
    while not is_esp32_done.value:
        do_test_cycle(ppk2_device=ppk2_device)

    ppk2_device.stop_measuring()
    print("Finished sampling -> powering down ESP32")
    ppk2_device.toggle_DUT_power("OFF")

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

def log_esp32(vid_pid):
    print("Logging ESP32 ...")
    serial_device = helper.get_serial_device(vid_pid)

    # Wait for the ESP to be ready (when it outputs "READY" to its serial)
    while((line := serial_device.readline()) != b'READY\r\n'):
        pass
    line = serial_device.readline()   # read a '\n' terminated line => WARNING: waits for a line to be available
    stripped_line = line.decode('utf-8').strip()
    collected_data_samples.append((helper.get_time_in_ms()-shared_time.value, stripped_line))

    serial_device.close()
    is_esp32_done.value = True
    print("Finished logging")

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
    logger = Process(target=log_esp32, args={esp32_vid_pid})

    sampler.start()
    logger.start()
    sampler.join()
    logger.join()
    print("Finished Test")

    return (collected_power_samples, collected_data_samples)


def do_test_cycle(ppk2_device):
    read_data = ppk2_device.get_data()
    if read_data != b'':
        samples = ppk2_device.get_samples(read_data)
        power_samples = samples[0]
        average = sum(power_samples)/len(power_samples)
        collected_power_samples.append((helper.get_time_in_ms()-shared_time.value, average))
    time.sleep(0.00001)  # lower time between sampling -> less samples read in one sampling period

def init_values():
    print("Resetting values for new Test run ...")
    is_esp32_done.value = False
    del collected_power_samples[:]
    del collected_data_samples[:]
    shared_time.value = helper.get_time_in_ms()

# MAIN ENTRY POINT

manager = Manager()
is_esp32_done = manager.Value('b', False)
collected_power_samples = manager.list()
collected_data_samples = manager.list()
shared_time = manager.Value('i', helper.get_time_in_ms())

if __name__ == '__main__':
    start_test(esp32_vid_pid="10c4:ea60", ppk2_device=get_PPK2(), flash=False)