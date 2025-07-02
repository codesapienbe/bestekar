import os
import re
import shutil
import zipfile
import requests
import argparse
import librosa
import soundfile as sf
import yt_dlp
import numpy as np
import torch
from pydub import AudioSegment, silence
from pathlib import Path

BASE_DIR = os.path.expanduser('~/.bestekar/rvc')
DIRS = {
    'dataset': os.path.join(BASE_DIR, 'dataset'),
    'weights': os.path.join(BASE_DIR, 'weights'),
    'vocals': os.path.join(BASE_DIR, 'vocals'),
    'audio': os.path.join(BASE_DIR, 'audio'),
    'models': os.path.join(BASE_DIR, 'models')
}
for d in DIRS.values():
    os.makedirs(d, exist_ok=True)

MODEL_URLS = {
    'uvr': [
        'https://huggingface.co/Politrees/UVR_resources/resolve/9e384b72631c40f6cd11ac61b59280ed271e14e3/MDXNet_models/UVR-MDX-NET-Voc_FT.onnx?download=true'
    ],
    'hubert': [
        'https://huggingface.co/lj1995/VoiceConversionWebUI/resolve/main/hubert_base.pt'
    ],
    'pretrained_g': [
        'https://huggingface.co/lj1995/VoiceConversionWebUI/resolve/main/pretrained/f0G40k.pth'
    ],
    'pretrained_d': [
        'https://huggingface.co/lj1995/VoiceConversionWebUI/resolve/main/pretrained/f0D40k.pth'
    ],
    'rmvpe': [
        'https://huggingface.co/lj1995/VoiceConversionWebUI/resolve/main/rmvpe.pt'
    ]
}


MODEL_PATHS = {
    'uvr': os.path.join(DIRS['weights'], 'UVR-MDX-NET-Voc_FT.onnx'),
    'hubert': os.path.join(DIRS['weights'], 'hubert_base.pt'),
    'pretrained_g': os.path.join(DIRS['weights'], 'f0G40k.pth'),
    'pretrained_d': os.path.join(DIRS['weights'], 'f0D40k.pth'),
    'rmvpe': os.path.join(DIRS['weights'], 'rmvpe.pt')
}

def sanitize_filename(filename):
    sanitized = re.sub(r'[^a-zA-Z0-9._-]', '_', filename)
    sanitized = sanitized.strip('_')
    return sanitized

def download_if_not_exists(urls, path):
    if os.path.isfile(path):
        return
    for url in urls:
        try:
            r = requests.get(url, stream=True, timeout=60)
            if r.status_code == 200:
                with open(path, 'wb') as f:
                    for chunk in r.iter_content(chunk_size=8192):
                        if chunk:
                            f.write(chunk)
                print(f"Downloaded: {path}")
                return
            else:
                print(f"Failed to download from {url} (status {r.status_code})")
        except Exception as e:
            print(f"Error downloading from {url}: {e}")
    raise RuntimeError(f"Could not download {os.path.basename(path)} from any known public mirror.")

def ensure_all_models():
    for key in MODEL_URLS:
        download_if_not_exists(MODEL_URLS[key], MODEL_PATHS[key])

def download_yt_audio(url, output_dir=DIRS['audio']):
    os.makedirs(output_dir, exist_ok=True)
    ydl_opts = {
        'format': 'bestaudio/best',
        'outtmpl': os.path.join(output_dir, '%(title)s.%(ext)s'),
        'postprocessors': [{
            'key': 'FFmpegExtractAudio',
            'preferredcodec': 'wav',
        }],
        'quiet': True,
        'no_warnings': True
    }
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url)
        filename = ydl.prepare_filename(info)
        filename = filename.replace('.webm', '.wav').replace('.m4a', '.wav')
        base = os.path.basename(filename)
        sanitized = sanitize_filename(base)
        sanitized_path = os.path.join(output_dir, sanitized)
        if sanitized != base:
            if os.path.exists(sanitized_path):
                os.remove(sanitized_path)
            os.rename(filename, sanitized_path)
        else:
            sanitized_path = filename
        return sanitized_path

def run_uvr(input_path, output_dir=DIRS['vocals']):
    os.makedirs(output_dir, exist_ok=True)
    import onnxruntime as ort
    import soundfile as sf
    import numpy as np
    from scipy.signal import resample_poly
    audio, sr = sf.read(input_path)
    if sr != 44100:
        audio = resample_poly(audio, 44100, sr)
        sr = 44100
    if audio.ndim == 1:
        audio = np.expand_dims(audio, axis=1)
    ort_sess = ort.InferenceSession(MODEL_PATHS['uvr'])
    audio = audio.T
    input_feed = {ort_sess.get_inputs()[0].name: audio.astype(np.float32)}
    pred = ort_sess.run(None, input_feed)[0]
    vocals = pred[0]
    vocals = vocals.T
    out_path = os.path.join(output_dir, os.path.basename(input_path))
    sf.write(out_path, vocals, sr, subtype='PCM_16')
    return out_path

def preprocess_audio(input_path, output_dir=DIRS['dataset']):
    os.makedirs(output_dir, exist_ok=True)
    output_path = os.path.join(output_dir, os.path.basename(input_path))
    y, sr = librosa.load(input_path, sr=44100)
    trimmed, _ = librosa.effects.trim(y, top_db=25)
    rms = np.sqrt(np.mean(trimmed**2))
    normalized = trimmed * (0.1 / rms)
    sf.write(output_path, normalized, sr, subtype='PCM_16')
    return output_path

def segment_audio(audio_path, segment_length=10000, overlap=300, output_dir=DIRS['dataset']):
    os.makedirs(output_dir, exist_ok=True)
    audio = AudioSegment.from_wav(audio_path)
    segments = silence.split_on_silence(audio, min_silence_len=500, silence_thresh=-40, keep_silence=300)
    final_segments = []
    for seg in segments:
        if len(seg) > segment_length:
            for i in range(0, len(seg), segment_length - overlap):
                final_segments.append(seg[i:i+segment_length])
        else:
            final_segments.append(seg)
    for i, seg in enumerate(final_segments):
        seg.export(os.path.join(output_dir, f'clip_{i:04d}.wav'), format='wav')
    return output_dir

def process_single_url(url):
    raw_audio = download_yt_audio(url)
    vocal_audio = run_uvr(raw_audio)
    cleaned_audio = preprocess_audio(vocal_audio)
    segment_audio(cleaned_audio)
    os.remove(raw_audio)
    os.remove(vocal_audio)
    os.remove(cleaned_audio)

def train_rvc_model(dataset_dir, model_name, sample_rate='40k', f0method='rmvpe', epochs=50, batch_size=7):
    from rvc.lib.train import preprocess_all, extract_f0, extract_feature, train, train_index
    logs_dir = os.path.join('logs', model_name)
    os.makedirs(logs_dir, exist_ok=True)
    preprocess_all(sr=sample_rate, data_path=dataset_dir, n_p=os.cpu_count() // 2)
    extract_f0(data_path=dataset_dir, sr=sample_rate, n_p=os.cpu_count() // 2, method=f0method)
    extract_feature(data_path=dataset_dir, sr=sample_rate, n_p=os.cpu_count() // 2)
    train(experiment_name=model_name, data_path=dataset_dir, sample_rate=sample_rate, f0=1, batch_size=batch_size, total_epoch=epochs, save_every_epoch=10, pretrained_G=MODEL_PATHS['pretrained_g'], pretrained_D=MODEL_PATHS['pretrained_d'])
    train_index(experiment_name=model_name, data_path=dataset_dir)
    model_files = sorted([os.path.join(logs_dir, f) for f in os.listdir(logs_dir) if f.startswith('G_') and f.endswith('.pth')], key=os.path.getmtime)
    latest_model = model_files[-1] if model_files else None
    index_file = os.path.join(logs_dir, f'added_{model_name}.index')
    if not latest_model or not os.path.isfile(index_file):
        raise RuntimeError('Training failed - output files not found')
    return latest_model, index_file

def create_final_zip(model_path, index_path, model_name):
    temp_dir = os.path.join(BASE_DIR, 'temp_rvc')
    if os.path.exists(temp_dir):
        shutil.rmtree(temp_dir)
    os.makedirs(os.path.join(temp_dir, 'indices'), exist_ok=True)
    os.makedirs(os.path.join(temp_dir, 'models'), exist_ok=True)
    shutil.copy(model_path, os.path.join(temp_dir, 'models', f'{model_name}.pth'))
    shutil.copy(index_path, os.path.join(temp_dir, 'indices', f'{model_name}.index'))
    zip_path = os.path.join(BASE_DIR, f'{model_name}_rvc.zip')
    with zipfile.ZipFile(zip_path, 'w') as zipf:
        for root, _, files in os.walk(temp_dir):
            for file in files:
                file_path = os.path.join(root, file)
                arcname = os.path.relpath(file_path, temp_dir)
                zipf.write(file_path, os.path.join('rvc', arcname))
    shutil.rmtree(temp_dir)
    return zip_path

def main():
    parser = argparse.ArgumentParser(description='RVC Training Pipeline (Bestekar, minimal args)')
    parser.add_argument('-u', '--urls', nargs='+', required=True, help='YouTube URLs to process')
    parser.add_argument('-m', '--model_name', default='turkish_default', help='Model name')
    parser.add_argument('-e', '--epochs', type=int, default=50, help='Training epochs')
    parser.add_argument('-b', '--batch_size', type=int, default=7, help='Batch size')
    args = parser.parse_args()

    ensure_all_models()
    for url in args.urls:
        process_single_url(url)
    torch.set_num_threads(1)
    model_path, index_path = train_rvc_model(DIRS['dataset'], args.model_name, epochs=args.epochs, batch_size=args.batch_size)
    zip_path = create_final_zip(model_path, index_path, args.model_name)
    print(f'Success! Model packaged at: {zip_path}')
    print(f'  - Models: rvc/models/{args.model_name}.pth')
    print(f'  - Indices: rvc/indices/{args.model_name}.index')

if __name__ == '__main__':
    main()
