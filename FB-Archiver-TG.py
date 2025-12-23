# Team FlashBytes - t.me/FlashBytess
import asyncio, io, os, hashlib, json
from telethon import TelegramClient, functions, types, events

api_id = 123456
api_hash = ""
session_name = 'FlashBytes_session'
history_file = "transfer_history.json"
max_parallel_downloads = 3
progress_update_interval = 2

client = TelegramClient(session_name, api_id, api_hash)

def load_history():
    if not os.path.exists(history_file):
        return {}
    with open(history_file, "r") as f:
        return json.load(f)

def save_to_history(msg_id, file_hash=None):
    history = load_history()
    history[str(msg_id)] = file_hash
    with open(history_file, "w") as f:
        json.dump(history, f)

def is_duplicate(msg_id, file_hash):
    history = load_history()
    if str(msg_id) in history:
        return True
    if file_hash and file_hash in history.values():
        return True
    return False

def hash_bytesio(buffer):
    buffer.seek(0)
    h = hashlib.sha256(buffer.read()).hexdigest()
    buffer.seek(0)
    return h

async def get_or_create_channel(name="FlashBytess archives"):
    print("[ ~ ] Checking archive channel...")
    dialogs = await client.get_dialogs()
    for dialog in dialogs:
        if dialog.name == name:
            return dialog.id
    created = await client(functions.channels.CreateChannelRequest(
        title=name,
        about="@FlashBytess",
        megagroup=False
    ))
    return created.chats[0].id

class Archiver:
    def __init__(self, client, max_parallel=3):
        self.client = client
        self.semaphore = asyncio.Semaphore(max_parallel)
        self.total_messages = 0
        self.transferred_messages = 0

    async def archive_message(self, message, destination):
        async with self.semaphore:
            try:
                file_hash = None
                if message.media:
                    buffer = io.BytesIO()
                    await self.client.download_media(message, file=buffer)
                    buffer.seek(0)
                    file_hash = hash_bytesio(buffer)

                    if is_duplicate(message.id, file_hash):
                        return

                    file_name = getattr(message.file, 'name', None)
                    if not file_name:
                        ext = getattr(message.file, 'ext', '')
                        file_name = f"file_{message.id}{ext}"
                    buffer.name = file_name

                    await self.client.send_file(destination, file=buffer, caption=message.text)
                    print(f"[ ~ ] Media transferred (ID : {message.id})")

                elif message.text:
                    if is_duplicate(message.id, None):
                        return
                    await self.client.send_message(destination, message.text)
                    print(f"[ ~ ] Text transferred (ID : {message.id})")

                save_to_history(message.id, file_hash)
                self.transferred_messages += 1

            except Exception as e:
                print(f"[ × ]Error in message {message.id} : {e}")

    async def archive_channel(self, sources, destination):
        if isinstance(sources, str):
            sources = [sources]
        for source in sources:
            print(f"[ ~ ]Archiving from {source}...")
            async for message in self.client.iter_messages(source, reverse=True):
                self.total_messages += 1
                await self.archive_message(message, destination)

async def show_progress(archiver):
    while archiver.transferred_messages < archiver.total_messages:
        print(f"[ ~ ] Progress : {archiver.transferred_messages}/{archiver.total_messages} messages transferred")
        await asyncio.sleep(progress_update_interval)

async def start_engine():
    await client.start()
    print("✅ Connected to Telegram")

    destination_id = await get_or_create_channel()
    sources_input = input("[ ? ] Enter source channels (comma separated @source1,@source2) >  ")
    sources = [s.strip() for s in sources_input.split(",")]

    archiver = Archiver(client, max_parallel_downloads)
    progress_task = asyncio.create_task(show_progress(archiver))
    await archiver.archive_channel(sources, destination_id)
    progress_task.cancel()

    print("[ ~ ] Archiving completed")
    await client.run_until_disconnected()

if __name__ == '__main__':
    with client:
        client.loop.run_until_complete(start_engine())
