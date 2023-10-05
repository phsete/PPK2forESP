import asyncio
import websockets
import json
import log

async def process_message(message):
    data = json.loads(message)
    print(f"received message of type {data['type']}")
    if data["type"] == "start_test":
        print("Starting Test ...")
        (collected_power_samples, collected_data_samples) = log.start_test()
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
    asyncio.run(main())
