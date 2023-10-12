import asyncio
import websockets
import json
import log
import helper

async def process_message(message):
    data = json.loads(message)
    print(f"received message of type {data['type']}")
    if data["type"] == "start_test":
        (collected_power_samples, collected_data_samples) = log.start_test(esp32_vid_pid=helper.config["node"]["ESP32VidPid"], ppk2_device=log.get_PPK2(), flash=False)
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
    async with websockets.serve(respond, "0.0.0.0", helper.config["general"]["WebsocketPort"]):
        await asyncio.Future()  # run forever

if __name__ == "__main__":    
    helper.download_asset_from_release("sender.bin", "firmware.bin")

    asyncio.run(main())
