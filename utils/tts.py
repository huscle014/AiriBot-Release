# Imports used through the rest of the notebook.
import torch
import torchaudio
import torch.nn as nn
import torch.nn.functional as F

import IPython

from tortoise.api import TextToSpeech
from tortoise.utils.audio import load_audio, load_voice, load_voices

def tts(text = ""):
    tts = TextToSpeech()

    # Define your own voice folder
    VOICE_PATH = r'.\resources\public\voices'
    VOICE_NAME = 'AIRI'

    # Generate with your own voice
    voice_samples, conditioning_latents = load_voice(VOICE_PATH)
    gen = tts.tts_with_preset(text, voice_samples=voice_samples, conditioning_latents=conditioning_latents)
    torchaudio.save(f'generated-{VOICE_NAME}.wav', gen.squeeze(0).cpu(), 24000)
    # IPython.display.Audio(f'generated-{VOICE_NAME}.wav')