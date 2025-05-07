import os
from dotenv import load_dotenv
import json
import asyncio
import sys
import threading
import time
import numpy as np
import sounddevice as sd
from my_agents import support_agent
from agents.voice import (
    AudioInput,
    SingleAgentVoiceWorkflow,
    VoicePipeline,
    SingleAgentWorkflowCallbacks,
    OpenAIVoiceModelProvider,
    VoicePipelineConfig,
    TTSModelSettings,
    STTModelSettings
)
from agents.run import Runner
from agents.voice.workflow import VoiceWorkflowHelper
import itertools
load_dotenv()
# Global variables to control conversation state
conversation_running = False
conversation_thread = None
player = None
stream = None
microphone_muted = False
speaker_muted = False

def get_input_device():
    """Get the default input device with proper error handling."""
    try:
        devices = sd.query_devices()
        default_input = sd.default.device[0]  # Get default input device ID
        
        # If default device is not set, find the first input device
        if default_input is None:
            for device in devices:
                if device['max_input_channels'] > 0:
                    return device['index']
            raise RuntimeError("No input devices found")
        
        return default_input
    except Exception as e:
        print(f"Error getting input device: {e}")
        # List all available devices for debugging
        print("\nAvailable devices:")
        print(sd.query_devices())
        raise


class WorkflowCallbacks(SingleAgentWorkflowCallbacks):
    def on_run(self, workflow: SingleAgentVoiceWorkflow, transcription: str) -> None:
        print("\n" + "-"*50)
        print(f"TRANSCRIPTION: {transcription}")
        print("-"*50 + "\n")

    def on_agent_response(self, workflow: SingleAgentVoiceWorkflow, response: str) -> None:
        print("\n" + "-"*50)
        print(f"AGENT RESPONSE::: {response}")
        print("-"*50 + "\n")

    def on_error(self, workflow: SingleAgentVoiceWorkflow, error: Exception) -> None:
        print(f"\nERROR in workflow: {error}\n")

agent = support_agent

def capture_audio_until_silence(silence_duration=0.6, samplerate=24000):
    """Capture audio until silence is detected for the specified duration."""
    global conversation_running, stream, microphone_muted
    
    try:
        # Check if conversation is still running before starting
        if not conversation_running:
            print("Conversation is not running, skipping audio capture")
            return None
            
        # If microphone is muted, return None
        if microphone_muted:
            print("Microphone is muted, skipping audio capture")
            return None
            
        # Get input device
        device = get_input_device()
        print(f"Using input device: {sd.query_devices(device)['name']}")
        
        # Initialize audio buffer and counters
        audio_buffer = []
        silence_counter = 0
        has_speech = False
        
        # Calculate how many blocks make up our desired silence duration
        # Assuming a typical block size of 1024 samples
        block_size = 1024
        blocks_per_silence = int(samplerate * silence_duration / block_size)
        
        # Parameters for noise filtering
        silence_threshold = 0.01  # Increased from 0.005
        speech_threshold = 0.02   # Higher threshold to detect actual speech
        noise_floor = None        # Will be calculated dynamically
        calibration_frames = 10   # Number of frames to calibrate noise floor
        calibration_buffer = []   # Buffer to store calibration frames
        
        print(f"Listening... (speak now, will stop after {silence_duration} seconds of silence)")
        
        # Create a stream without a callback
        stream = sd.InputStream(samplerate=samplerate, device=device, channels=1, 
                              dtype=np.float32, blocksize=block_size)
        stream.start()
        
        # Main recording loop - continue until silence after speech detected
        for iteration in itertools.count():
            # Check if conversation is still running or if microphone was muted during recording
            if not conversation_running or microphone_muted:
                print("Conversation stopped or microphone muted, ending audio capture")
                break
                
            # Read audio data
            try:
                data, overflowed = stream.read(block_size)
                if overflowed:
                    print("Audio buffer overflowed")
            except Exception as e:
                print(f"Error reading from stream: {e}")
                break
            
            # Flatten data
            flat_data = data.flatten()
            
            # Calculate audio level
            audio_level = np.abs(flat_data).mean()
            
            # Calibrate noise floor during first few frames
            if iteration < calibration_frames:
                calibration_buffer.append(audio_level)
                if iteration == calibration_frames - 1:
                    # Set noise floor as the average of calibration frames plus a small margin
                    noise_floor = np.mean(calibration_buffer) * 1.5
                    print(f"Calibrated noise floor: {noise_floor:.6f}")
                    # Adjust silence threshold based on noise floor
                    silence_threshold = max(silence_threshold, noise_floor * 1.2)
                    speech_threshold = max(speech_threshold, noise_floor * 2.5)
                    print(f"Adjusted silence threshold: {silence_threshold:.6f}")
                    print(f"Speech detection threshold: {speech_threshold:.6f}")
                continue
            
            # Apply simple noise gate - only add to buffer if above noise floor
            if audio_level > noise_floor:
                audio_buffer.extend(flat_data)
            else:
                # Add zeros instead to maintain timing
                audio_buffer.extend(np.zeros_like(flat_data))
            
            # Print audio level with noise floor for reference
            print(f"Current audio level: {audio_level:.6f} (Noise floor: {noise_floor:.6f})", end='\r')
            
            # Check for silence vs speech
            if audio_level < silence_threshold:
                silence_counter += 1
            else:
                silence_counter = 0
                # Only set has_speech if we're well above the noise floor
                if audio_level > speech_threshold:
                    has_speech = True
            
            # If we've had enough silence blocks and we detected speech before, stop recording
            if silence_counter >= blocks_per_silence and has_speech:
                print(f"\nDetected {silence_duration} seconds of silence after speech, stopping...")
                break
        
        # Stop and close the stream
        if stream and stream.active:
            try:
                stream.stop()
                stream.close()
            except Exception as e:
                print(f"Error closing stream: {e}")
        stream = None
        
        # Check if we timed out without detecting speech
        if not has_speech:
            print("\nTimeout reached - no speech detected")
            return None
        
        # Check if we have any audio data
        if not audio_buffer:
            print("No audio data captured")
            return None
            
        # Convert to int16 and normalize
        audio_data = np.array(audio_buffer)
        if len(audio_data) == 0:
            print("No audio data captured")
            return None
            
        audio_data = (audio_data * 32767).astype(np.int16)
        
        print(f"Finished recording. Captured {len(audio_data)} samples")
        return audio_data
        
    except Exception as e:
        print(f"Error in audio capture: {e}")
        if stream:
            try:
                if stream.active:
                    stream.stop()
                stream.close()
            except Exception as e2:
                print(f"Error closing stream after exception: {e2}")
        stream = None
        return None

def start_conversation():
    """Start the voice conversation."""
    global conversation_running, conversation_thread
    
    if conversation_running:
        print("Conversation is already running")
        return True
    
    conversation_running = True
    
    # Start the conversation in a separate thread with error handling
    def run_conversation_safely():
        try:
            asyncio.run(continuous_conversation())
        except Exception as e:
            print(f"Error in conversation thread: {e}")
            import traceback
            traceback.print_exc()
            # Make sure to reset the flag if there's an error
            global conversation_running
            conversation_running = False
    
    conversation_thread = threading.Thread(target=run_conversation_safely)
    conversation_thread.daemon = True  # Make thread daemon so it doesn't block program exit
    conversation_thread.start()
    print("Conversation started")
    return True


def stop_conversation():
    """Stop the voice conversation and clean up resources."""
    global conversation_running, player, stream
    
    if not conversation_running:
        print("Conversation is not running")
        return True
        
    print("Stopping conversation...")
    # Set the flag to stop the conversation loop
    conversation_running = False
    
    # Give a moment for the flag to take effect
    time.sleep(0.5)
    
    # Clean up audio resources
    if stream:
        try:
            if hasattr(stream, 'active') and stream.active:
                stream.stop()
            stream.close()
            stream = None
            print("Audio input stream stopped")
        except Exception as e:
            print(f"Error stopping input stream: {e}")
    
    if player:
        try:
            if hasattr(player, 'active') and player.active:
                player.stop()
            player.close()
            player = None
            print("Audio output player stopped")
        except Exception as e:
            print(f"Error stopping output player: {e}")
    
    print("Conversation stopped")
    return True  # Return success status

async def continuous_conversation():
    """Run a continuous voice conversation until stopped."""
    global conversation_running, player
    
    print("Starting continuous voice conversation...")
    
    # Initialize conversation history outside the loop to maintain context between turns
    conversation_history = []
    
    # Create a custom workflow that maintains conversation history
    class StatefulWorkflow(SingleAgentVoiceWorkflow):
        def __init__(self, agent, callbacks=None, conversation_history=None):
            super().__init__(agent, callbacks)
            self._conversation_history = conversation_history or []
            
        
        async def run(self, input_text):
            # Add user message to history
            self._conversation_history.append({"role": "user", "content": input_text})
            
            # Print the updated conversation history
            print("\n" + "="*30)
            print("CONVERSATION HISTORY:")
            for i, msg in enumerate(self._conversation_history):
                print(f"{i+1}. {msg['role'].upper()}: {msg['content']}")
            print("="*30 + "\n")
            
            # Call callbacks
            if self._callbacks and hasattr(self._callbacks, "on_run"):
                self._callbacks.on_run(self, input_text)
            
            # Add system message with customer state information
            system_content = agent.instructions
            
            
            # Create a custom input history with our state information
            custom_input_history = [
                {
                    "role": "system",
                    "content": system_content
                }
            ]
            
            # Add conversation history (last 40 messages to avoid context limit)
            custom_input_history.extend(self._conversation_history[-40:])
            
            # Run the agent with our custom input history
            result = Runner.run_streamed(self._current_agent, custom_input_history)
            
            # Get the full response for state tracking
            full_response = ""
            
            # Stream the text from the result
            async for chunk in VoiceWorkflowHelper.stream_text_from(result):
                full_response += chunk
                yield chunk
            
            
            # Add agent response to history
            self._conversation_history.append({"role": "assistant", "content": full_response})
            
            # Print the updated conversation history after agent response
            print("\n" + "="*30)
            print("UPDATED CONVERSATION HISTORY:")
            for i, msg in enumerate(self._conversation_history):
                print(f"{i+1}. {msg['role'].upper()}: {msg['content']}")
            print("="*30 + "\n")
            
            # Call callbacks
            if self._callbacks and hasattr(self._callbacks, "on_agent_response"):
                self._callbacks.on_agent_response(self, full_response)
            
            # Update the input history and current agent
            self._input_history = result.to_input_list()
            self._current_agent = result.last_agent
    
    # Create a single pipeline with stateful workflow and OpenAI TTS
    workflow = StatefulWorkflow(
        agent, 
        callbacks=WorkflowCallbacks(),
        conversation_history=conversation_history,
    )
    
    pipeline = VoicePipeline(
        workflow=workflow,
        config=VoicePipelineConfig(
            model_provider=OpenAIVoiceModelProvider(),
            tts_settings=TTSModelSettings(
                voice="alloy",  
                instructions="""Speak as a friendly, patient tech support agent with these qualities:
                - Warm and reassuring tone that makes users feel at ease
                - Clear articulation at a steady pace, avoiding technical jargon
                - Encouraging and empathetic attitude, especially when users are confused
                - Natural conversational style with a hint of a smile in your voice
                """
            ),
            stt_settings=STTModelSettings(
                language="en",
                temperature= 0.5
            ),
        )
    )
    
    # Create a single audio player for the entire conversation
    player = sd.OutputStream(samplerate=24000, channels=1, dtype=np.int16)
    player.start()
    
    # Add a small delay after starting the player to ensure it's fully initialized
    await asyncio.sleep(0.1)
    
    try:
        while conversation_running:
            print("\n" + "="*50)
            print("NEW CONVERSATION TURN")
            print("="*50)
            
            # Capture audio until silence is detected
            audio_data = capture_audio_until_silence(silence_duration=0.6)
            
            # Check if conversation was stopped during audio capture
            if not conversation_running:
                print("Conversation stopped during audio capture")
                break
                
            if audio_data is None:
                print("Failed to capture audio. Please check your microphone.")
                await asyncio.sleep(1)  
                continue
            
            # Check if audio has actual content
            audio_level = np.abs(audio_data).mean()
            print(f"Audio level: {audio_level}")
            
            if audio_level < 5:  
                print("No significant audio detected. Please speak louder or check your microphone.")
                continue
            
            print("Running pipeline with existing workflow...")
            
            # Create audio input from captured audio
            audio_input = AudioInput(buffer=audio_data)
            
            # Run the pipeline with the new audio input
            result = await pipeline.run(audio_input)
            print(f"--------------{result}-----------------")
            
            print("Processing response...")
            # Process the audio stream
            response_text = ""  
            
            # Buffer to collect initial audio chunks
            audio_buffer = []
            initial_buffer_size = 3  # Number of initial audio chunks to buffer
            buffer_count = 0
            
            async for event in result.stream():
                # Check if conversation was stopped during response
                if not conversation_running:
                    print("Conversation stopped during response")
                    break
                    
                # Print event type for debugging
                print(f"Event type: {event.type}")
                
                if event.type == "voice_stream_event_audio":
                    if not speaker_muted:
                        # Buffer initial audio chunks to prevent cutting off the beginning
                        if buffer_count < initial_buffer_size:
                            audio_buffer.append(event.data)
                            buffer_count += 1
                            # When buffer is full, play all buffered chunks at once
                            if buffer_count == initial_buffer_size:
                                for chunk in audio_buffer:
                                    player.write(chunk)
                                audio_buffer = []  # Clear the buffer
                        else:
                            # After initial buffering, play chunks normally
                            player.write(event.data)
                    # Add audio data info for debugging
                    if hasattr(event.data, 'shape'):
                        print(f"Audio data shape: {event.data.shape}")
                elif event.type == "raw_response_event" and event.data.type == "response.output_text.delta":
                    # Collect the response text
                    response_text += event.data.delta
                    # Print the delta for real-time feedback
                    print(event.data.delta, end="", flush=True)
                elif event.type == "voice_stream_event_lifecycle":
                    print(f"Lifecycle event: {event.__dict__ if hasattr(event, '__dict__') else event}")
                    if hasattr(event, 'event') and event.event == "session_ended":
                        # Play any remaining buffered audio
                        if audio_buffer and not speaker_muted:
                            for chunk in audio_buffer:
                                player.write(chunk)
                        if response_text:
                            print("\n" + "-"*50)
                            print(f"COMPLETE RESPONSE: {response_text}")
                            print("-"*50 + "\n")
                        print("\nSession ended, ready for next turn...")
                        break
                else:
                    # Print unknown event types for debugging
                    print(f"Unknown event: {event.__dict__ if hasattr(event, '__dict__') else event}")
            
            # Check if conversation was stopped
            if not conversation_running:
                break
                
    except KeyboardInterrupt:
        print("\nExiting voice conversation...")
    except Exception as e:
        print(f"\nError in voice conversation: {e}")
        import traceback
        traceback.print_exc()
    finally:
        # Clean up resources
        if player:
            try:
                player.stop()
                player.close()
                player = None
            except:
                pass
        conversation_running = False
        print("Conversation ended")


def mute_microphone():
    """Mute the microphone input."""
    global microphone_muted, stream
    microphone_muted = True
    
    # If there's an active stream, stop it to interrupt any ongoing recording
    if stream and hasattr(stream, 'active') and stream.active:
        try:
            stream.stop()
            stream.close()
            stream = None
            print("Stopped active recording due to microphone mute")
        except Exception as e:
            print(f"Error stopping stream on mute: {e}")
    
    print("Microphone muted")
    return True

def unmute_microphone():
    """Unmute the microphone input."""
    global microphone_muted
    microphone_muted = False
    print("Microphone unmuted")
    return True

def mute_speaker():
    """Mute the speaker output."""
    global speaker_muted
    speaker_muted = True
    print("Speaker muted")
    return True

def unmute_speaker():
    """Unmute the speaker output."""
    global speaker_muted
    speaker_muted = False
    print("Speaker unmuted")
    return True

def toggle_microphone():
    """Toggle microphone mute state."""
    global microphone_muted
    if microphone_muted:
        return unmute_microphone()
    else:
        return mute_microphone()

def toggle_speaker():
    """Toggle speaker mute state."""
    global speaker_muted
    if speaker_muted:
        return unmute_speaker()
    else:
        return mute_speaker()

def get_mute_states():
    """Get the current mute states."""
    global microphone_muted, speaker_muted
    return {
        "microphone_muted": microphone_muted,
        "speaker_muted": speaker_muted
    }


if __name__ == "__main__":
    print("System info:", sys.version)
    print("Available audio devices:")
    print(sd.query_devices())
    try:
        input_device = get_input_device()
        print(f"\nUsing input device: {sd.query_devices(input_device)['name']}")
    except Exception as e:
        print(f"Error setting up audio device: {e}")
        sys.exit(1)
    
    # Start conversation
    conversation_running = True
    asyncio.run(continuous_conversation())