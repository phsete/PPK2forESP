import asyncio
import websockets
import json
import log
import helper
import uvicorn

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

def start_task(uuid: UUID, func, *args) -> None:
    jobs[uuid].status = "started"
    func(*args)

@app.get("/")
def hello_world():
    return {"Hello": "World", "status": log.log_status}

def test_callback(uuid: UUID, log_status):
    jobs[uuid].status = log_status
    log.ppk2_device_temp.ser.close()

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
    log.is_stopped.set()
    log.log_status = "stopped" # could be done better with an actual result value
    jobs = {}
    return {"status": log.log_status}

@app.post("/flash/")
def flash(version: str, node_type: str):
    helper.download_asset_from_release(f"{node_type}.bin", "firmware.bin", version)
    print(f"downloaded version {version}")
    log.flash_esp32(vid_pid=helper.config["node"]["ESP32VidPid"], ppk2_device=log.get_PPK2())
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
    print("Calculating values ...")

    values = log.value_buffer
    log.value_buffer = []

    collected_power_samples_return = []

    collected_data_samples_return = log.collected_data_samples
    print(collected_data_samples_return)
    log.collected_data_samples = []
    print(collected_data_samples_return)

    for timestamp, value in values:
        if value != b'':
            samples, raw_output = log.ppk2_device_temp.get_samples(value)
            average = sum(samples)/len(samples)
            collected_power_samples_return.append((timestamp, average))

    print(f"Finished calculating values -> got {len(collected_power_samples_return)} averages")
    jobs[uuid].collected_power_samples.extend(collected_power_samples_return)
    jobs[uuid].collected_data_samples.extend(collected_data_samples_return)



async def process_message(message):
    data = json.loads(message)
    print(f"received message of type {data['type']}")
    if data["type"] == "start_test":
        (log_status, collected_power_samples, collected_data_samples) = log.start_test(esp32_vid_pid=helper.config["node"]["ESP32VidPid"], ppk2_device=log.get_PPK2(), version=data["version"], flash=False)
        return json.dumps({"status": log_status, "power_samples": collected_power_samples, "data_samples": collected_data_samples})
    elif data["type"] == "flash":
        helper.download_asset_from_release("sender.bin", "firmware.bin", data["version"])
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
    async with websockets.serve(respond, "0.0.0.0", helper.config["general"]["WebsocketPort"]):
        await asyncio.Future()  # run forever

if __name__ == "__main__":    
    helper.download_asset_from_release("sender.bin", "firmware.bin")

    uvicorn.run("node:app", host='0.0.0.0', port= 8000, loop='asyncio')
