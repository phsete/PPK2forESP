import asyncio
import websockets
import json
import log
import helper
import time

from fastapi import FastAPI
from pydantic import BaseModel, Field
from uuid import UUID, uuid4
from fastapi import BackgroundTasks
from typing import Dict
from concurrent.futures.process import ProcessPoolExecutor
from contextlib import asynccontextmanager
from http import HTTPStatus
import uvicorn

class Job(BaseModel):
    uid: UUID = Field(default_factory=uuid4)
    status: str = "in_progress"
    result: int = None

app = FastAPI()
jobs: Dict[UUID, Job] = {}

async def run_in_process(fn, *args):
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(app.state.executor, fn, *args)  # wait and return result

async def start_task(uid: UUID, func, param: int) -> None:
    jobs[uid].result = await run_in_process(func, param)
    jobs[uid].status = "complete"

@app.get("/")
def hello_world():
    return {"Hello": "World"}

@app.get("/start")
def start():
    log.ppk2_device_temp = log.get_PPK2()
    (log_status, collected_power_samples, collected_data_samples) = log.start_test(esp32_vid_pid=helper.config["node"]["ESP32VidPid"], ppk2_device=log.ppk2_device_temp, version="latest", flash=False)
    return json.dumps({"status": log_status})

@app.get("/values")
def values():
    print("Calculating values ...")

    values = log.value_buffer._getvalue()
    del log.value_buffer[:]

    collected_power_samples_return = []

    collected_data_samples_return = log.collected_data_samples._getvalue()
    del log.collected_data_samples[:]

    for timestamp, value in values:
        if value != b'':
            samples, raw_output = log.ppk2_device_temp.get_samples(value)
            average = sum(samples)/len(samples)
            collected_power_samples_return.append((timestamp-log.shared_time.value, average))
    if len(collected_power_samples_return) > 0:
        print(f"Finished calculating values -> got {len(collected_power_samples_return)} averages")
        return json.dumps({"power_samples": collected_power_samples_return, "data_samples": collected_data_samples_return})
    elif log.is_sampling.value:
        return json.dumps({"status": "running test but no samples available yet"})
    else:
        return json.dumps({"status": "not running test and no samples available"})
    


async def process_message(message):
    data = json.loads(message)
    print(f"received message of type {data['type']}")
    if data["type"] == "start_test":
        (log_status, collected_power_samples, collected_data_samples) = log.start_test(esp32_vid_pid=helper.config["node"]["ESP32VidPid"], ppk2_device=log.get_PPK2(), version=data["version"], flash=False)
        return json.dumps({"status": log_status, "power_samples": collected_power_samples._getvalue(), "data_samples": collected_data_samples._getvalue()})
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

    uvicorn.run("node:app", host='localhost', port= 8000, loop='asyncio')
