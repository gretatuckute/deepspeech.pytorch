import json
from typing import List

import hydra
import torch
from torch.cuda.amp import autocast

from deepspeech_pytorch.configs.inference_config import TranscribeConfig
from deepspeech_pytorch.decoder import Decoder
from deepspeech_pytorch.loader.data_loader import SpectrogramParser
from deepspeech_pytorch.model import DeepSpeech
from deepspeech_pytorch.utils import load_decoder, load_model

# import matplotlib.pyplot as plt
import librosa
import matplotlib
matplotlib.use('TkAgg')
import matplotlib.pyplot as plt
import numpy as np


def decode_results(decoded_output: List,
                   decoded_offsets: List,
                   cfg: TranscribeConfig):
    results = {
        "output": [],
        "_meta": {
            "acoustic_model": {
                "path": cfg.model.model_path
            },
            "language_model": {
                "path": cfg.lm.lm_path
            },
            "decoder": {
                "alpha": cfg.lm.alpha,
                "beta": cfg.lm.beta,
                "type": cfg.lm.decoder_type.value,
            }
        }
    }

    for b in range(len(decoded_output)):
        for pi in range(min(cfg.lm.top_paths, len(decoded_output[b]))):
            result = {'transcription': decoded_output[b][pi]}
            if cfg.offsets:
                result['offsets'] = decoded_offsets[b][pi].tolist()
            results['output'].append(result)
    return results


def transcribe(cfg: TranscribeConfig):
    device = torch.device("cuda" if cfg.model.cuda else "cpu")

    model = load_model(
        device=device,
        model_path=cfg.model.model_path
    )

    decoder = load_decoder(
        labels=model.labels,
        cfg=cfg.lm
    )

    spect_parser = SpectrogramParser(
        audio_conf=model.spect_cfg,
        normalize=True
    )

    decoded_output, decoded_offsets = run_transcribe(
        audio_path=hydra.utils.to_absolute_path(cfg.audio_path),
        spect_parser=spect_parser,
        model=model,
        decoder=decoder,
        device=device,
        precision=cfg.model.precision
    )
    results = decode_results(
        decoded_output=decoded_output,
        decoded_offsets=decoded_offsets,
        cfg=cfg
    )
    print(json.dumps(results))


def run_transcribe(audio_path: str,
                   spect_parser: SpectrogramParser,
                   model: DeepSpeech,
                   decoder: Decoder,
                   device: torch.device,
                   precision: int):
    # spect = spect_parser.parse_audio(audio_path).contiguous()
    

    # Resample to 16 kHz
    # import soundfile as sf
    # sf.write('/Users/gt/Documents/GitHub/deepspeech.pytorch/data/inference/test_audio_16khz.wav', audio_input, 16000)
    #
    # audio_input, _ = librosa.load('/Users/gt/Documents/GitHub/deepspeech.pytorch/data/inference/test_audio2.wav', sr=16000)
    # librosa.write('/Users/gt/Documents/GitHub/deepspeech.pytorch/data/inference/test_audio_16khz.wav', audio_input)
    #
    
    spect = spect_parser.parse_audio(
        '/Users/gt/Documents/GitHub/deepspeech.pytorch/data/inference/test_audio_16khz.wav').contiguous()
    spect = spect.view(1, 1, spect.size(0), spect.size(1))
    spect = spect.to(device)
    input_sizes = torch.IntTensor([spect.size(3)]).int()
    with autocast(enabled=precision == 16):
        out, output_sizes = model(spect, input_sizes)
    decoded_output, decoded_offsets = decoder.decode(out, output_sizes)
    
    # look into state
    sdict = model.state_dict()
    skeys = list(sdict.keys())

    # if testing a rnn weight
    # g = sdict[skeys[41]]
    
    # print sizes of all outputs:
    for i, v in enumerate(skeys):
        val = sdict[v]
        print(v, val.shape)
        
    # look into spect
    s = spect.squeeze().detach().numpy()

    plt.figure()
    plt.imshow((s), origin='lower')
    plt.show()
    
    return decoded_output, decoded_offsets
