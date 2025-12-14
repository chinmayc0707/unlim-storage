import os
import asyncio
from telethon import TelegramClient, errors
from config import Config
from telethon.tl.types import DocumentAttributeFilename
from telethon.sessions import StringSession
import math
import shutil

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# 2GB limit (leaving a small buffer)
CHUNK_SIZE = 2000 * 1024 * 1024

class TelegramManager:
    def __init__(self, session_name=None, session_string=None):
        self.session_name = session_name
        self.loop = asyncio.new_event_loop()
        # Set the event loop for the current thread
        asyncio.set_event_loop(self.loop)

        # Use StringSession if provided, otherwise create a new one (will be saved later)
        if session_string:
            self.session = StringSession(session_string)
        else:
            self.session = StringSession()

        self.client = TelegramClient(self.session, Config.API_ID, Config.API_HASH, loop=self.loop)
        self.phone = None
        self.phone_code_hash = None
        self.is_connected = False

        # Initial check (without connecting fully, just check if authorized locally)
        # Note: can't check easily without connecting.
        pass

    def _ensure_loop(self):
        """
        Ensure the event loop is set for the current thread.
        This is crucial for Flask's multi-threaded environment where
        each request might run in a thread without a loop set.
        """
        try:
            loop = asyncio.get_event_loop()
            if loop != self.loop:
                asyncio.set_event_loop(self.loop)
        except RuntimeError:
            asyncio.set_event_loop(self.loop)

    def _run_with_retry(self, callback, *args, **kwargs):
        """
        Runs a coroutine callback with retry logic for connection issues.
        callback: method that returns a coroutine (e.g. self.client.send_message)
        """
        self._ensure_loop()
        
        # 1. Ensure connected initially (best effort)
        try:
             if not self.client.is_connected():
                 self.loop.run_until_complete(self.client.connect())
        except Exception:
             pass # Will be caught by main try/except or retry logic

        try:
            return self.loop.run_until_complete(callback(*args, **kwargs))
        except Exception as e:
            error_str = str(e).lower()
            # Catch "disconnected", "cannot send requests", or ConnectionError
            if "disconnected" in error_str or "request" in error_str or isinstance(e, (ConnectionError, sqlite3.OperationalError)):
                print(f"TelegramManager: Connection issue detected ({e}). Reconnecting and retrying...")
                try:
                    self.loop.run_until_complete(self.client.disconnect())
                except:
                    pass
                
                # Reconnect
                try:
                    self.loop.run_until_complete(self.client.connect())
                except Exception as connect_err:
                     print(f"TelegramManager: Reconnect failed: {connect_err}")
                     raise connect_err
                
                # Retry
                return self.loop.run_until_complete(callback(*args, **kwargs))
            else:
                raise e

    def connect(self):
        # Managed by _run_with_retry usually, but for explicit connect check:
        self._ensure_loop()
        if not self.client.is_connected():
            self.loop.run_until_complete(self.client.connect())

        self.is_connected = self.loop.run_until_complete(self.client.is_user_authorized())
        return self.is_connected

    def send_code(self, phone):
        # Use _run_with_retry to handle potential disconnects
        try:
            sent = self._run_with_retry(self.client.send_code_request, phone)
            self.phone = phone
            self.phone_code_hash = sent.phone_code_hash
            return True, None
        except Exception as e:
            return False, str(e)

    def sign_in(self, code, password=None):
        try:
            if password:
                self._run_with_retry(
                    self.client.sign_in, self.phone, code, password=password, phone_code_hash=self.phone_code_hash
                )
            else:
                self._run_with_retry(
                    self.client.sign_in, self.phone, code, phone_code_hash=self.phone_code_hash
                )
            self.is_connected = True
            return True, None
        except errors.SessionPasswordNeededError:
            return False, "PASSWORD_REQUIRED"
        except Exception as e:
            return False, str(e)

    def ensure_connected(self):
        self._ensure_loop()
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
            msg = self._run_with_retry(
                self.client.send_file,
                "me",
                file_path,
                caption=f"Codeword: {codeword} | Part: 1/1",
                attributes=attributes,
                force_document=True
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
                        part_attributes = []
                        if file_name:
                             part_attributes.append(DocumentAttributeFilename(file_name=f"{file_name}.part{part_num}"))

                        msg = self._run_with_retry(
                            self.client.send_file,
                            "me",
                            temp_chunk_path,
                            caption=f"Codeword: {codeword} | Part: {part_num}/{total_parts}",
                            attributes=part_attributes,
                            force_document=True
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
                msg = self._run_with_retry(self.client.get_messages, "me", ids=msg_id)
                if msg and msg.media:
                    self._run_with_retry(self.client.download_media, msg, f)
                else:
                    raise Exception(f"Message {msg_id} not found or has no media")

    def delete_file(self, message_ids):
        self.ensure_connected()
        self._run_with_retry(self.client.delete_messages, "me", message_ids)

    def copy_file(self, message_ids, new_codeword):
        self.ensure_connected()
        new_message_ids = []

        for i, msg_id in enumerate(message_ids):
            # Forward the message to "me" (Saved Messages)
            forwarded_msgs = self._run_with_retry(
                self.client.forward_messages, "me", [msg_id], from_peer="me"
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
            self._run_with_retry(self.client.edit_message, new_msg, new_caption)

            new_message_ids.append(new_msg.id)

        return new_message_ids

    def logout(self):
        # We don't always need retry for logout, but good to have
        if self.is_connected:
            try:
                self._run_with_retry(self.client.log_out)
            except Exception as e:
                print(f"Error logging out: {e}")
            finally:
                self.is_connected = False
                self.phone = None
                self.phone_code_hash = None
                # Clean disconnect
                if self.client:
                    self.loop.run_until_complete(self.client.disconnect())

    def close(self):
        """Safely disconnect the client."""
        self._ensure_loop()
        try:
            if self.client and self.client.is_connected():
                self.loop.run_until_complete(self.client.disconnect())
        except Exception as e:
            # Ignore if already disconnected or other trivial errors during cleanup
            print(f"Error closing manager: {e}")

    def get_session_string(self):
        """Returns the current session string for persistence."""
        return StringSession.save(self.client.session)


# Global registry for active managers
# Key: user_id (str or int) or phone (str) for pending logins
_active_managers = {}

def get_manager(key, session_string=None):
    """
    Get or create a TelegramManager for the given key (user_id or phone).
    session_string: Optional existing session string to load.
    """
    key = str(key)
    if key not in _active_managers:
        _active_managers[key] = TelegramManager(session_name=key, session_string=session_string)
    return _active_managers[key]

def remove_manager(key):
    key = str(key)
    if key in _active_managers:
        manager = _active_managers[key]
        try:
            manager.close()
        except:
            pass
        del _active_managers[key]
