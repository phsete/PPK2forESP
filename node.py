import asyncio
import websockets
import json
import log
import requests

ESP32_VID_PID = "10c4:ea60"
LOGGER_VERSION = "latest"
URL_LATEST = "https://github.com/phsete/ESPNOWLogger/releases/latest/download/sender.bin"
URL_VERSION = "https://github.com/phsete/ESPNOWLogger/releases/download/" + LOGGER_VERSION + "/sender.bin"

async def process_message(message):
    data = json.loads(message)
    print(f"received message of type {data['type']}")
    if data["type"] == "start_test":
        (collected_power_samples, collected_data_samples) = log.start_test(esp32_vid_pid=ESP32_VID_PID, flash=True)
        return json.dumps({"power_samples": collected_power_samples._getvalue(), "data_samples": collected_data_samples._getvalue()})
    else:
        return "OK"

async def respond(websocket):
    incoming = await websocket.recv()
    print(f"<<< {incoming}")

    outgoing = await process_message(incoming)

    await websocket.send(outgoing)
    print(f">>> {outgoing}")

async def main():
    async with websockets.serve(respond, "0.0.0.0", 8765):
        await asyncio.Future()  # run forever

if __name__ == "__main__":
    if(LOGGER_VERSION == "latest"):
        url = URL_LATEST
    else:
        url = URL_VERSION
        
    response = requests.get(url)
    if(response.ok):
        with open("firmware.bin", mode="wb") as file:
            file.write(response.content)
    else:
        exit("Download failed!")

    asyncio.run(main())
