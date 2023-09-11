import asyncio
import websockets
import json

async def process_message(message):
    data = json.loads(message)
    print(f"received message of type {data['type']}")

async def respond(websocket):
    incoming = await websocket.recv()
    print(f"<<< {incoming}")

    await process_message(incoming)

    outgoing = "OK"
    await websocket.send(outgoing)
    print(f">>> {outgoing}")

async def main():
    async with websockets.serve(respond, "localhost", 8765):
        await asyncio.Future()  # run forever

if __name__ == "__main__":
    asyncio.run(main())