import os
import random
import csv
import torch
import torchaudio
import torchaudio.transforms as T
from torch.utils.data import Dataset


class AudioAugmentor:
    def __init__(self, p_noise=0.4, p_spec_aug=0.5):
        self.p_noise = p_noise
        self.p_spec_aug = p_spec_aug
        self.freq_mask = T.FrequencyMasking(freq_mask_param=12)
        self.time_mask = T.TimeMasking(time_mask_param=25)

    def apply_waveform_noise(self, waveform):
        if random.random() < self.p_noise:
            noise = torch.randn_like(waveform)
            snr = random.uniform(15.0, 30.0)
            signal_power = waveform.norm(p=2)
            noise_power = noise.norm(p=2)
            if noise_power > 0:
                scale = (signal_power / noise_power) * (10 ** (-snr / 20.0))
                waveform = waveform + scale * noise
        return waveform

    def apply_spec_augment(self, mel):
        if random.random() < self.p_spec_aug:
            mel = self.freq_mask(mel)
            mel = self.time_mask(mel)
        return mel


class MelSpectrogramExtractor:
    def __init__(self, sample_rate=16000, n_mels=80, n_fft=400, hop_length=160):
        self.sample_rate = sample_rate
        self.mel_transform = T.MelSpectrogram(
            sample_rate=sample_rate,
            n_fft=n_fft,
            win_length=n_fft,
            hop_length=hop_length,
            n_mels=n_mels,
            f_min=20.0,
            f_max=7600.0
        )

    def __call__(self, waveform, sample_rate):
        if waveform.shape[0] > 1:
            waveform = torch.mean(waveform, dim=0, keepdim=True)

        if sample_rate != self.sample_rate:
            resampler = T.Resample(sample_rate, self.sample_rate)
            waveform = resampler(waveform)

        mel = self.mel_transform(waveform)
        log_mel = torch.log(torch.clamp(mel, min=1e-5))
        mean = log_mel.mean(dim=-1, keepdim=True)
        std = log_mel.std(dim=-1, keepdim=True) + 1e-6
        norm_mel = (log_mel - mean) / std
        return norm_mel.squeeze(0)


class VoiceprintDataset(Dataset):
    def __init__(self, manifest_csv, segment_length=32000, augment=False):
        self.segment_length = segment_length
        self.augment = augment
        self.extractor = MelSpectrogramExtractor()
        self.augmentor = AudioAugmentor() if augment else None

        self.samples = []
        with open(manifest_csv, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                self.samples.append((row["path"], int(row["speaker_id"])))

    def __len__(self):
        return len(self.samples)

    def __getitem__(self, idx):
        wav_path, speaker_id = self.samples[idx]
        waveform, sr = torchaudio.load(wav_path)

        if self.augment and self.augmentor:
            waveform = self.augmentor.apply_waveform_noise(waveform)

        if waveform.shape[-1] < self.segment_length:
            pad_amount = self.segment_length - waveform.shape[-1]
            waveform = torch.nn.functional.pad(waveform, (0, pad_amount), mode="reflect")
        elif waveform.shape[-1] > self.segment_length:
            max_start = waveform.shape[-1] - self.segment_length
            start = random.randint(0, max_start) if self.augment else 0
            waveform = waveform[:, start:start + self.segment_length]

        mel = self.extractor(waveform, sr)

        if self.augment and self.augmentor:
            mel = self.augmentor.apply_spec_augment(mel)

        return mel, speaker_id


def build_manifests(base_raw_dir="data/raw", manifest_dir="data/manifest", pairs_count=200):
    os.makedirs(manifest_dir, exist_ok=True)

    speakers = {}
    speaker_names = {}

    dev_dir = os.path.join(base_raw_dir, "developer", "model_data")
    dev_files = []
    if os.path.exists(dev_dir):
        for root, _, files in os.walk(dev_dir):
            for f in files:
                if f.lower().endswith(".wav"):
                    dev_files.append(os.path.join(root, f))

    if dev_files:
        speakers[0] = dev_files
        speaker_names[0] = "developer"

    dist_dir = os.path.join(base_raw_dir, "distractors", "model_data")
    current_id = 1
    if os.path.exists(dist_dir):
        for folder_name in sorted(os.listdir(dist_dir)):
            sub_path = os.path.join(dist_dir, folder_name)
            if os.path.isdir(sub_path):
                spk_files = [
                    os.path.join(sub_path, f)
                    for f in os.listdir(sub_path)
                    if f.lower().endswith(".wav")
                ]
                if spk_files:
                    speakers[current_id] = spk_files
                    speaker_names[current_id] = folder_name
                    current_id += 1

    if len(speakers) < 2:
        raise ValueError("Найдено меньше двух дикторов. Проверь наличие .wav файлов в папках model_data!")

    train_rows = []
    for spk_id, paths in speakers.items():
        for path in paths:
            train_rows.append({"path": path, "speaker_id": spk_id})

    train_csv = os.path.join(manifest_dir, "train.csv")
    with open(train_csv, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["path", "speaker_id"])
        writer.writeheader()
        writer.writerows(train_rows)

    pairs = []
    spk_ids = list(speakers.keys())
    eligible_positive_spks = [s for s in spk_ids if len(speakers[s]) >= 2]

    half_pairs = pairs_count // 2

    for _ in range(half_pairs):
        spk = random.choice(eligible_positive_spks)
        w1, w2 = random.sample(speakers[spk], 2)
        pairs.append({"path1": w1, "path2": w2, "label": 1})

    for _ in range(half_pairs):
        spk1, spk2 = random.sample(spk_ids, 2)
        w1 = random.choice(speakers[spk1])
        w2 = random.choice(speakers[spk2])
        pairs.append({"path1": w1, "path2": w2, "label": 0})

    random.shuffle(pairs)
    val_csv = os.path.join(manifest_dir, "val_pairs.csv")
    with open(val_csv, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["path1", "path2", "label"])
        writer.writeheader()
        writer.writerows(pairs)

    print(f"Успешно сгенерирован train.csv: {len(train_rows)} сэмплов от {len(speakers)} дикторов.")
    for spk_id, name in speaker_names.items():
        print(f"  * ID {spk_id:02d} ({name}): {len(speakers[spk_id])} файлов")
    print(f"Успешно сгенерирован val_pairs.csv: {len(pairs)} проверочных пар (50% совпадений, 50% чужаков).")


if __name__ == "__main__":
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    build_manifests(
        base_raw_dir=os.path.join(base_dir, "data", "raw"),
        manifest_dir=os.path.join(base_dir, "data", "manifest"),
        pairs_count=160
    )