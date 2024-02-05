import asyncio
import websockets
import json
import log
import helper
import uvicorn
import os

from fastapi import FastAPI
from uuid import UUID, uuid4
from fastapi import BackgroundTasks
from typing import Dict

class Job():
    def __init__(self):
        self.uuid: UUID = uuid4()
        self.status: str = "created"
        self.collected_power_samples: list = []
        self.collected_data_samples: list = []

app = FastAPI()
jobs: Dict[UUID, Job] = {}
calculating_values = False

def start_task(uuid: UUID, func, *args) -> None:
    jobs[uuid].status = "started"
    func(*args)

@app.get("/")
def hello_world():
    return {"Hello": "World", "status": log.log_status}

def test_callback(uuid: UUID, log_status):
    jobs[uuid].status = log_status
    # if log.ppk2_device_temp and log.ppk2_device_temp.ser:
    #     log.ppk2_device_temp.ser.close()
    # else:
    #     print("Error with Callback. No PPK2 device or corresponding Serial device set.")
        
def flash_callback():
    if log.ppk2_device_temp and log.ppk2_device_temp.ser:
        log.ppk2_device_temp.ser.close()
    else:
        print("Error with Callback. No PPK2 device or corresponding Serial device set.")

def change_status(uuid: UUID, log_status):
    print(f"change: {log_status}")
    jobs[uuid].status = log_status
    print(jobs[uuid].status)

@app.post("/start/")
def start(background_tasks: BackgroundTasks, version: str, node_type: str):
    log.ppk2_device_temp = log.get_PPK2()
    new_job = Job()
    jobs[new_job.uuid] = new_job
    background_tasks.add_task(start_task, new_job.uuid, log.start_test, helper.config["node"]["ESP32VidPid"], log.ppk2_device_temp, version, False, lambda log_status: test_callback(new_job.uuid, log_status), lambda log_status: change_status(new_job.uuid, log_status), node_type, lambda: calculate_values(new_job.uuid))
    return {"uuid": new_job.uuid, "status": jobs[new_job.uuid].status}

@app.get("/stop/")
def stop():
    global jobs
    print("Stopping all jobs ...")
    log.is_stopped.set()
    while calculating_values:
        # wait for calculation to finish (if a calculation is still running)
        pass
    log.log_status = "stopped" # could be done better with an actual result value
    for uuid, job in jobs.items():
        calculate_values(uuid)
    response = get_jobs()
    jobs = {}
    while not log.is_esp32_done.is_set():
        pass
    if log.ppk2_device_temp and log.ppk2_device_temp.ser:
        log.ppk2_device_temp.ser.close()
    else:
        print("Error while stopping jobs. No PPK2 device or corresponding Serial device set.")
    print("All Jobs stopped.")
    return {"status": log.log_status, **response}

@app.post("/flash/")
def flash(version: str, node_type: str):
    log.ppk2_device_temp = log.get_PPK2()
    helper.download_asset_from_release(f"{node_type}.bin", os.path.join(helper.BASE_DIR, "firmware.bin"), version)
    print(f"downloaded version {version} with options {node_type}")
    log.flash_esp32(vid_pid=helper.config["node"]["ESP32VidPid"], ppk2_device=log.ppk2_device_temp, callback=flash_callback)
    return {"status": "OK"}

@app.get("/status/")
def status(uuid: UUID):
    selected_job = jobs[uuid] if uuid in jobs else None
    if selected_job:
        print(selected_job.status)
        return {"status": selected_job.status}
    else:
        return {"error": "Job with specified UUID not found."}
    
@app.get("/jobs")
def get_jobs():
    response = {}
    for uuid, job in jobs.items():
        print(job.status)
        response[str(uuid)] = {"collected_power_samples": job.collected_power_samples, "collected_data_samples": job.collected_data_samples}
        job.collected_data_samples = []
        job.collected_power_samples = []
    return response
    
def calculate_values(uuid: UUID):
    global calculating_values
    print("Calculating values ...")
    calculating_values = True

    # Get values from the buffer and reset the buffer directly to not loose any sampled data
    values = log.value_buffer
    log.value_buffer = []

    # extend the collected data samples and clear the logging buffer
    jobs[uuid].collected_data_samples.extend(log.collected_data_samples)
    log.collected_data_samples = []

    # get the correct power readings and append them to the job
    for timestamp, value in values:
        if value != b'':
            if log.ppk2_device_temp:
                samples, raw_output = log.ppk2_device_temp.get_samples(value)
                average = sum(samples)/len(samples)
                jobs[uuid].collected_power_samples.append((timestamp, average))
            else:
                print("Error while calculating values. No PPK2 device set.")

    calculating_values = False
    print(f"Finished calculating values -> got {len(jobs[uuid].collected_power_samples)} overall averages")

async def process_message(message):
    data = json.loads(message)
    print(f"received message of type {data['type']}")
    if data["type"] == "start_test":
        log.start_test(esp32_vid_pid=helper.config["node"]["ESP32VidPid"], ppk2_device=log.get_PPK2(), version=data["version"], flash=False)
        return "started"
    elif data["type"] == "flash":
        helper.download_asset_from_release("sender.bin", os.path.join(helper.BASE_DIR, "firmware.bin"), data["version"])
        print(f"downloaded version {data['version']}")
        log.flash_esp32(vid_pid=helper.config["node"]["ESP32VidPid"], ppk2_device=log.get_PPK2())
        return "OK" # Temporary return value -> not representing actual result of flash
    elif data["type"] == "connection_test":
        return "OK"
    else:
        return "ERROR"

async def respond(websocket):
    incoming = await websocket.recv()
    print(f"<<< {incoming}")

    outgoing = await process_message(incoming)

    await websocket.send(outgoing)
    # print(f">>> {outgoing}")

async def main():
    async with websockets.serve(respond, "0.0.0.0", helper.config["general"]["WebsocketPort"]): # type: ignore
        await asyncio.Future()  # run forever

if __name__ == "__main__":    
    helper.download_asset_from_release("sender.bin", os.path.join(helper.BASE_DIR, "firmware.bin"))
    uvicorn.run("node:app", host='0.0.0.0', port= 8000, loop='asyncio')
