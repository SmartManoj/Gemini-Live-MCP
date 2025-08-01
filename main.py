
import warnings
# -*- coding: utf-8 -*-
# Copyright 2025 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.


import asyncio
import base64
import io
import os
import sys
import traceback

import cv2
import pyaudio
import PIL.Image
import mss

import argparse
from dotenv import load_dotenv

from google import genai
from google.genai import types

from mcp_handler import MCP

load_dotenv()

if sys.version_info < (3, 11, 0):
    import taskgroup, exceptiongroup

    asyncio.TaskGroup = taskgroup.TaskGroup
    asyncio.ExceptionGroup = exceptiongroup.ExceptionGroup

FORMAT = pyaudio.paInt16
CHANNELS = 1
SEND_SAMPLE_RATE = 16000
RECEIVE_SAMPLE_RATE = 24000
CHUNK_SIZE = 1024

MODEL = "models/gemini-2.5-flash-live-preview"
# MODEL = "models/gemini-2.5-flash-preview-native-audio-dialog"
# MODEL = "models/gemini-2.0-flash-exp"
DEFAULT_MODE = "screen"
if os.path.exists('system_instruction.txt'):
    with open('system_instruction.txt', 'r') as f:
        SYSTEM_INSTRUCTION = f.read()
else:
    SYSTEM_INSTRUCTION = 'You are ASI agent.'

client = genai.Client(http_options={"api_version": "v1alpha"})
# import google.auth
# credentials = google.auth.default(scopes=["https://www.googleapis.com/auth/cloud-platform"])[0]
# client = genai.Client(vertexai=True, location="us-central1", credentials=credentials, http_options={"api_version": "v1alpha"})

# While Gemini 2.0 Flash is in experimental preview mode, only one of AUDIO or
# TEXT may be passed here.
# CONFIG = {"tools": tools, "response_modalities": ["AUDIO"]}

pya = pyaudio.PyAudio()


def alert_error(error_msg, exception=None):
    """Display error alert with optional exception details"""
    print(f"\n🚨 ERROR ALERT: {error_msg}")
    if exception:
        print(f"Exception: {type(exception).__name__}: {str(exception)}")
        print("Full traceback:")
        traceback.print_exception(type(exception), exception, exception.__traceback__)
    print("🚨 END ERROR ALERT\n")


class AudioLoop:
    def __init__(self, video_mode=DEFAULT_MODE):
        self.video_mode = video_mode

        self.audio_in_queue = None
        self.out_queue = None

        self.session = None

        self.send_text_task = None
        self.receive_audio_task = None
        self.play_audio_task = None
        
        self.mcp = MCP()

    async def send_text(self):
        try:
            while True:
                text = await asyncio.to_thread(
                    input,
                    "message > ",
                )
                if text.lower() == "q":
                    break
                with warnings.catch_warnings():
                    warnings.simplefilter("ignore", DeprecationWarning)
                    await self.session.send(input=text or ".", end_of_turn=True)
        except Exception as e:
            alert_error("Failed to send text input", e)
            raise
            
    def handle_server_content(self, server_content):
        try:
            model_turn = server_content.model_turn
            if model_turn:
                for part in model_turn.parts:
                    executable_code = part.executable_code
                    if executable_code is not None:
                        print('-------------------------------')
                        print(f'``` python\n{executable_code.code}\n```')
                        print('-------------------------------')

                    code_execution_result = part.code_execution_result
                    if code_execution_result is not None:
                        print('-------------------------------')
                        print(f'```\n{code_execution_result.output}\n```')
                        print('-------------------------------')

            grounding_metadata = getattr(server_content, 'grounding_metadata', None)
            if grounding_metadata is not None:
                print(grounding_metadata.search_entry_point.rendered_content)
        except Exception as e:
            alert_error("Failed to handle server content", e)
            raise

        return
    
    async def handle_tool_call(self, tool_call):
        try:
            for fc in tool_call.function_calls:
                result = await self.mcp.client.call_tool(
                    name=fc.name,
                    arguments=fc.args,
                )
                print(result)
                tool_response = types.LiveClientToolResponse(
                    function_responses=[types.FunctionResponse(
                        name=fc.name,
                        id=fc.id,
                        response={'result':result},
                    )]
                )

                print('\n>>> ', tool_response)
                with warnings.catch_warnings():
                    warnings.simplefilter("ignore", DeprecationWarning)
                    await self.session.send(input=tool_response)
        except Exception as e:
            alert_error("Failed to handle tool call", e)
            raise

    def _get_frame(self, cap):
        try:
            # Read the frameq
            ret, frame = cap.read()
            # Check if the frame was read successfully
            if not ret:
                return None
            # Fix: Convert BGR to RGB color space
            # OpenCV captures in BGR but PIL expects RGB format
            # This prevents the blue tint in the video feed
            frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            img = PIL.Image.fromarray(frame_rgb)  # Now using RGB frame
            img.thumbnail([1024, 1024])

            image_io = io.BytesIO()
            img.save(image_io, format="jpeg")
            image_io.seek(0)

            mime_type = "image/jpeg"
            image_bytes = image_io.read()
            return {"mime_type": mime_type, "data": base64.b64encode(image_bytes).decode()}
        except Exception as e:
            alert_error("Failed to get camera frame", e)
            return None

    async def get_frames(self):
        try:
            # This takes about a second, and will block the whole program
            # causing the audio pipeline to overflow if you don't to_thread it.
            cap = await asyncio.to_thread(
                cv2.VideoCapture, 0
            )  # 0 represents the default camera

            while True:
                frame = await asyncio.to_thread(self._get_frame, cap)
                if frame is None:
                    break

                await asyncio.sleep(1.0)

                await self.out_queue.put(frame)

            # Release the VideoCapture object
            cap.release()
        except Exception as e:
            alert_error("Failed to get camera frames", e)
            raise

    def _get_screen(self):
        try:
            sct = mss.mss()
            monitor = sct.monitors[0]

            i = sct.grab(monitor)

            mime_type = "image/jpeg"
            image_bytes = mss.tools.to_png(i.rgb, i.size)
            img = PIL.Image.open(io.BytesIO(image_bytes))

            image_io = io.BytesIO()
            img.save(image_io, format="jpeg")
            image_io.seek(0)

            image_bytes = image_io.read()
            return {"mime_type": mime_type, "data": base64.b64encode(image_bytes).decode()}
        except Exception as e:
            alert_error("Failed to capture screen", e)
            return None

    async def get_screen(self):
        try:
            while True:
                frame = await asyncio.to_thread(self._get_screen)
                if frame is None:
                    break

                await asyncio.sleep(1.0)

                await self.out_queue.put(frame)
        except Exception as e:
            alert_error("Failed to get screen frames", e)
            raise

    async def send_realtime(self):
        try:
            while True:
                msg = await self.out_queue.get()
                with warnings.catch_warnings():
                    warnings.simplefilter("ignore", DeprecationWarning)
                    await self.session.send(input=msg)
        except Exception as e:
            alert_error("Failed to send realtime data", e)
            raise

    async def listen_audio(self):
        try:
            mic_info = pya.get_default_input_device_info()
            print('Microphone:', mic_info['name'])
            self.audio_stream = await asyncio.to_thread(
                pya.open,
                format=FORMAT,
                channels=CHANNELS,
                rate=SEND_SAMPLE_RATE,
                input=True,
                input_device_index=mic_info["index"],
                frames_per_buffer=CHUNK_SIZE,
            )
            if __debug__:
                kwargs = {"exception_on_overflow": False}
            else:
                kwargs = {}
            while True:
                data = await asyncio.to_thread(self.audio_stream.read, CHUNK_SIZE, **kwargs)
                await self.out_queue.put({"data": data, "mime_type": "audio/pcm"})
        except Exception as e:
            alert_error("Failed to listen to audio", e)
            raise

    async def receive_audio(self):
        "Background task to reads from the websocket and write pcm chunks to the output queue"
        try:
            while True:
                turn = self.session.receive()
                async for response in turn:
                    if data := response.data:
                        self.audio_in_queue.put_nowait(data)
                        continue
                    if text := response.text:
                        print(text, end="")
                        
                    server_content = response.server_content
                    if server_content is not None:
                        self.handle_server_content(server_content)
                        continue

                    tool_call = response.tool_call
                    if tool_call is not None:
                        await self.handle_tool_call(tool_call)

                # If you interrupt the model, it sends a turn_complete.
                # For interruptions to work, we need to stop playback.
                # So empty out the audio queue because it may have loaded
                # much more audio than has played yet.
                while not self.audio_in_queue.empty():
                    self.audio_in_queue.get_nowait()
        except Exception as e:
            alert_error("Failed to receive audio", e)
            raise

    async def play_audio(self):
        try:
            stream = await asyncio.to_thread(
                pya.open,
                format=FORMAT,
                channels=CHANNELS,
                rate=RECEIVE_SAMPLE_RATE,
                output=True,
            )
            while True:
                bytestream = await self.audio_in_queue.get()
                await asyncio.to_thread(stream.write, bytestream)
        except Exception as e:
            alert_error("Failed to play audio", e)
            raise

    async def run(self):
        try:
            await self.mcp.connect_to_server()
            available_tools = await self.mcp.client.list_tools()
            
            functional_tools = []
            for tool in available_tools:
                tool_desc = {
                        "name": tool.name,
                        "description": tool.description
                    }
                if tool.inputSchema["properties"]:
                    tool_desc["parameters"] = {
                        "type": tool.inputSchema["type"],
                        "properties": {},
                    }
                    for param in tool.inputSchema["properties"]:
                        tool_desc["parameters"]["properties"][param] = {
                            "type": tool.inputSchema["properties"][param]["type"],
                            "description": "",
                        }
                    
                if "required" in tool.inputSchema:
                    tool_desc["parameters"]["required"] = tool.inputSchema["required"]
                    
                functional_tools.append(tool_desc)
            print(functional_tools)
            tools = [
                {
                    'function_declarations': functional_tools,
                    'code_execution': {},
                    'google_search': {},
                    },
            ]
            
            CONFIG = {
                "tools": tools, "response_modalities": ["AUDIO"], 
                "speech_config": {
                                "voice_config": {
                        "prebuilt_voice_config": {
                            "voice_name": "Zephyr",
                        }
                    },
                },
                'system_instruction': SYSTEM_INSTRUCTION
            }
            
            try:
                async with (
                    client.aio.live.connect(model=MODEL, config=CONFIG) as session,
                    asyncio.TaskGroup() as tg,
                ):
                    self.session = session

                    self.audio_in_queue = asyncio.Queue()
                    self.out_queue = asyncio.Queue(maxsize=5)

                    send_text_task = tg.create_task(self.send_text())
                    tg.create_task(self.send_realtime())
                    tg.create_task(self.listen_audio())
                    if self.video_mode == "camera":
                        tg.create_task(self.get_frames())
                    elif self.video_mode == "screen":
                        tg.create_task(self.get_screen())

                    tg.create_task(self.receive_audio())
                    tg.create_task(self.play_audio())

                    await send_text_task
                    raise asyncio.CancelledError("User requested exit")

            except asyncio.CancelledError:
                pass
            except Exception as e:
                if hasattr(self, 'audio_stream'):
                    self.audio_stream.close()
                alert_error("Session error occurred", e)
                raise
        except Exception as e:
            alert_error("Failed to initialize or run audio loop", e)
            raise


if __name__ == "__main__":
    try:
        parser = argparse.ArgumentParser()
        parser.add_argument(
            "--mode",
            type=str,
            default=DEFAULT_MODE,
            help="pixels to stream from",
            choices=["camera", "screen", "none"],
        )
        args = parser.parse_args()
        main = AudioLoop(video_mode=args.mode)
        asyncio.run(main.run())
    except KeyboardInterrupt:
        print("\n🛑 Application interrupted by user")
    except Exception as e:
        alert_error("Application failed to start or run", e)
        sys.exit(1)