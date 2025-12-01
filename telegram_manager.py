import os
import asyncio
from telethon import TelegramClient, errors
from config import Config
from telethon.tl.types import DocumentAttributeFilename
import math

# 2GB limit (leaving a small buffer)
CHUNK_SIZE = 2000 * 1024 * 1024 

class TelegramManager:
    def __init__(self):
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)
        self.client = TelegramClient('drive_session', Config.API_ID, Config.API_HASH, loop=self.loop)
        self.phone = None
        self.phone_code_hash = None
        self.is_connected = False

    def connect(self):
        if not self.client.is_connected():
            self.loop.run_until_complete(self.client.connect())
        self.is_connected = self.loop.run_until_complete(self.client.is_user_authorized())
        return self.is_connected

    def send_code(self, phone):
        self.connect()
        try:
            sent = self.loop.run_until_complete(self.client.send_code_request(phone))
            self.phone = phone
            self.phone_code_hash = sent.phone_code_hash
            return True, None
        except Exception as e:
            return False, str(e)

    def sign_in(self, code, password=None):
        try:
            if password:
                self.loop.run_until_complete(
                    self.client.sign_in(self.phone, code, password=password, phone_code_hash=self.phone_code_hash)
                )
            else:
                self.loop.run_until_complete(
                    self.client.sign_in(self.phone, code, phone_code_hash=self.phone_code_hash)
                )
            self.is_connected = True
            return True, None
        except errors.SessionPasswordNeededError:
            return False, "PASSWORD_REQUIRED"
        except Exception as e:
            return False, str(e)

    def ensure_connected(self):
        if not self.is_connected:
            self.connect()
        if not self.is_connected:
            raise Exception("Not authenticated")

    def upload_file(self, file_path, codeword, file_name=None):
        self.ensure_connected()
        file_size = os.path.getsize(file_path)
        message_ids = []
        
        attributes = []
        if file_name:
            attributes.append(DocumentAttributeFilename(file_name=file_name))
        
        if file_size <= CHUNK_SIZE:
            msg = self.loop.run_until_complete(
                self.client.send_file(
                    "me", 
                    file_path, 
                    caption=f"Codeword: {codeword} | Part: 1/1",
                    attributes=attributes,
                    force_document=True
                )
            )
            message_ids.append(msg.id)
        else:
            total_parts = math.ceil(file_size / CHUNK_SIZE)
            with open(file_path, 'rb') as f:
                for part_num in range(1, total_parts + 1):
                    chunk_data = f.read(CHUNK_SIZE)
                    temp_chunk_path = f"{file_path}.part{part_num}"
                    with open(temp_chunk_path, 'wb') as temp_f:
                        temp_f.write(chunk_data)
                    
                    try:
                        # For parts, we might not want to force the filename as it's a part
                        # But user wants "same file name". 
                        # Usually split files are handled differently. 
                        # For now, let's keep parts as is or name them partX?
                        # Let's just apply attributes to the parts too, maybe with suffix?
                        # Or just leave parts alone as they are internal.
                        # The user likely means single files.
                        # Let's apply to parts but maybe that's confusing.
                        # Actually, if it's a large file, the parts are reassembled.
                        # Let's apply the filename to the parts so they look nice too.
                        part_attributes = []
                        if file_name:
                             part_attributes.append(DocumentAttributeFilename(file_name=f"{file_name}.part{part_num}"))

                        msg = self.loop.run_until_complete(
                            self.client.send_file(
                                "me", 
                                temp_chunk_path, 
                                caption=f"Codeword: {codeword} | Part: {part_num}/{total_parts}",
                                attributes=part_attributes,
                                force_document=True
                            )
                        )
                        message_ids.append(msg.id)
                    finally:
                        if os.path.exists(temp_chunk_path):
                            os.remove(temp_chunk_path)
                            
        return message_ids

    def download_file(self, message_ids, output_path):
        self.ensure_connected()
        with open(output_path, 'wb') as f:
            for msg_id in message_ids:
                msg = self.loop.run_until_complete(self.client.get_messages("me", ids=msg_id))
                if msg and msg.media:
                    self.loop.run_until_complete(self.client.download_media(msg, f))
                else:
                    raise Exception(f"Message {msg_id} not found or has no media")

    def delete_file(self, message_ids):
        self.ensure_connected()
        self.loop.run_until_complete(
            self.client.delete_messages("me", message_ids)
        )

    def copy_file(self, message_ids, new_codeword):
        self.ensure_connected()
        new_message_ids = []
        
        for i, msg_id in enumerate(message_ids):
            # Forward the message to "me" (Saved Messages)
            forwarded_msgs = self.loop.run_until_complete(
                self.client.forward_messages("me", [msg_id], from_peer="me")
            )
            
            if not forwarded_msgs:
                raise Exception(f"Failed to forward message {msg_id}")
                
            new_msg = forwarded_msgs[0]
            
            # Calculate part info if multiple parts
            total_parts = len(message_ids)
            part_num = i + 1
            
            # Update caption with new codeword
            new_caption = f"Codeword: {new_codeword} | Part: {part_num}/{total_parts}"
            
            # Edit the caption of the forwarded message
            self.loop.run_until_complete(
                self.client.edit_message(new_msg, new_caption)
            )
            
            new_message_ids.append(new_msg.id)
            
        return new_message_ids

    def logout(self):
        if self.is_connected:
            try:
                self.loop.run_until_complete(self.client.log_out())
            except Exception as e:
                print(f"Error logging out: {e}")
            finally:
                self.is_connected = False
                self.phone = None
                self.phone_code_hash = None
                # Re-initialize client to avoid "cannot be reused" error
                if self.client:
                    self.client.disconnect()
                self.client = TelegramClient('drive_session', Config.API_ID, Config.API_HASH, loop=self.loop)

tg_manager = TelegramManager()
