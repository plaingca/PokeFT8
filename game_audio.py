"""Optional bounded SDL playback for the embedded, windowless emulator."""

import ctypes

import sdl2


class GameAudio:
    def __init__(self):
        self.device = 0
        self.enabled = False
        self.playing = False

    def enable(self, enabled):
        if enabled and not self.device:
            if sdl2.SDL_InitSubSystem(sdl2.SDL_INIT_AUDIO) < 0:
                raise RuntimeError("Audio device could not be initialized")
            self.want = sdl2.SDL_AudioSpec(48000, sdl2.AUDIO_S8, 2, 1024)
            self.have = sdl2.SDL_AudioSpec(0, 0, 0, 0)
            self.device = sdl2.SDL_OpenAudioDevice(None, 0, self.want, self.have, 0)
            if not self.device:
                raise RuntimeError("No compatible audio output is available")
        self.enabled = enabled
        self.clear()

    def clear(self):
        if self.device:
            sdl2.SDL_PauseAudioDevice(self.device, 1)
            sdl2.SDL_ClearQueuedAudio(self.device)
        self.playing = False

    def push(self, samples):
        if not self.enabled or not samples.size:
            return
        queued = sdl2.SDL_GetQueuedAudioSize(self.device)
        if self.playing and queued == 0:
            self.clear()  # Rebuffer after an actual underrun, rather than stuttering.
        if queued > 38400:
            self.clear()  # Never replay a backlog after UI stalls.
        data = (samples.astype("int16") // 2).astype("int8").tobytes()
        buffer = ctypes.create_string_buffer(data)
        if sdl2.SDL_QueueAudio(self.device, buffer, len(data)) < 0:
            self.enable(False)
        elif not self.playing and sdl2.SDL_GetQueuedAudioSize(self.device) >= 9600:
            self.playing = True
            sdl2.SDL_PauseAudioDevice(self.device, 0)

    def close(self):
        if self.device:
            sdl2.SDL_CloseAudioDevice(self.device)
            self.device = 0
        self.enabled = False
