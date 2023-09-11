import asyncio
import websockets

async def respond(websocket):
    incoming = await websocket.recv()
    print(f"<<< {incoming}")

    outgoing = "Hello from the node!"
    await websocket.send(outgoing)
    print(f">>> {outgoing}")

async def main():
    async with websockets.serve(respond, "localhost", 8765):
        await asyncio.Future()  # run forever

if __name__ == "__main__":
    asyncio.run(main())