# 🎵 Bestekar - Türkçe AI Besteci (RVC Entegreli)

[![Python 3.9+](https://img.shields.io/badge/python-3.9+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![uv](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/uv/main/assets/badge/v0.json)](https://github.com/astral-sh/uv)

> **Türkçe şarkı sözlerinizi yapay zeka ile müziğe dönüştürün ve RVC ile gerçek AI vokal ekleyin!**

Bestekar, Facebook'un MusicGen modeli ile RVC (Retrieval-based Voice Conversion) teknolojisini birleştirerek Türkçe şarkı sözlerinizi hem enstrümantal müzik hem de AI vokal ile tam bir şarkıya dönüştüren devrimsel bir Python uygulamasıdır.

## ✨ Özellikler

### 🎼 Müzik Üretimi
- **AI Destekli Enstrümantal**: Facebook MusicGen-Large modeli ile yüksek kalite
- **RVC Vokal Sentezi**: Gerçek AI vokal ile şarkı söyleme
- **Tam Şarkı Pipeline**: Enstrümantal + Vokal = Komple şarkı

### 🇹🇷 Türkçe Desteği
- **Türkçe Odaklı**: Türk müzik tarzlarına uygun melodi üretimi
- **Edge TTS Entegrasyonu**: Türkçe metin-konuşma dönüşümü
- **RVC Ses Dönüşümü**: Kendi sesinizle AI şarkı söyleme

### 🎨 Gelişmiş Özellikler
- **3 Üretim Modu**: Komple şarkı, sadece enstrümantal, sadece vokal
- **Özelleştirilebilir Stiller**: Ballad, türkü, pop ve daha fazlası
- **GUI Arayüz**: Kullanıcı dostu Kivy arayüzü
- **Sistem Tray**: Arka planda çalışan uygulama
- **Yerel İşlem**: Tamamen offline çalışır

## 🚀 Hızlı Başlangıç

### Gereksinimler

- Python 3.9 veya üzeri
- [uv](https://github.com/astral-sh/uv) paket yöneticisi
- CUDA destekli GPU (önerilen, CPU'da da çalışır)

### Kurulum

1. **Depoyu klonlayın:**

```bash
git clone https://github.com/yourusername/bestekar.git
cd bestekar
```

2. **Bağımlılıkları yükleyin:**

```bash
uv sync
```

3. **RVC entegrasyonunu kurun (opsiyonel - gelişmiş kullanıcılar için):**

```bash
# RVC bağımlılıklarını yükleyin
uv sync --extra rvc

# Not: RVC-python Windows'ta derleme sorunları yaşayabilir
# Alternatif: Sadece TTS vokalları kullanın (RVC olmadan)
```

4. **Uygulamayı çalıştırın:**

```bash
uv run bestekar
```

### RVC Model Kurulumu

RVC ile AI vokal üretimi için:

1. **Otomatik Varsayılan Model:**
   - Bestekar ilk çalıştırmada otomatik olarak varsayılan bir RVC modeli oluşturur
   - Model seçmezseniz varsayılan model kullanılır
   - `rvc_models/models/turkish_default.pth` dosyası otomatik oluşturulur

2. **Kendi RVC modellerinizi ekleyin:**
   - Kendi sesinizle RVC-WebUI ile model eğitin
   - Hazır Türkçe RVC modellerini indirin
   - `.pth` model dosyalarını `rvc_models/models/` klasörüne koyun
   - `.index` dosyalarını `rvc_models/indices/` klasörüne koyun

3. **Bestekar GUI'de:**
   - "RVC Model" alanında model dosyanızı seçin (opsiyonel)
   - Seçmezseniz varsayılan model otomatik kullanılır
   - "Complete Song (RVC)" modunu seçin
   - Şarkınızı AI vokal ile üretin!

## 📖 Kullanım

### Basit Kullanım

```
# Varsayılan şarkı sözleri ile
uv run bestekar
```

### Programatik Kullanım

```
from bestekar import TurkishSongGenerator

# Şarkı sözleriniz
lyrics = """
Gece iner, başın yastıkta ağır,
Düşünceler döner, kalbinde bir çağrı.
Uyku kaçar, gözlerin dalar,
Endişe sarar, ruhunu yorar.
"""

# Üreticiyi başlatın
generator = TurkishSongGenerator()

# Şarkıyı üretin
song_file = generator.generate_song(
    lyrics=lyrics,
    style="Turkish emotional ballad, acoustic guitar, soft piano",
    duration=45,
    output_name="benim_sarkim"
)

print(f"Şarkınız hazır: {song_file}")
```

## 🎨 Müzik Stilleri

Bestekar farklı Türk müzik stillerini destekler:

- **Duygusal Ballad**: `Turkish emotional ballad, acoustic guitar, soft piano`
- **Türkü Tarzı**: `Turkish folk song, traditional instruments, emotional vocals`
- **Modern Pop**: `Turkish pop ballad, contemporary, heartfelt vocals`
- **Akustik**: `Turkish acoustic song, guitar, intimate, emotional`
- **Romantik**: `Turkish romantic ballad, soft melody, love song`

## 🛠️ Geliştirme

### Geliştirme Ortamını Kurun

```
# Geliştirme bağımlılıklarını yükleyin
uv sync --extra dev

# Kod formatlaması
uv run black src/
uv run isort src/

# Testleri çalıştırın
uv run pytest
```

### Proje Yapısı

```
bestekar/
├── src/
│   └── __init__.py          # Ana uygulama kodu
├── tests/                   # Test dosyaları
├── examples/               # Örnek şarkı sözleri
├── pyproject.toml          # Proje konfigürasyonu
├── README.md               # Bu dosya
└── LICENSE                 # MIT lisansı
```

## 📋 Gereksinimler

### Sistem Gereksinimleri

- **RAM**: En az 8GB (GPU kullanımı için 12GB+ önerilen)
- **Depolama**: Model dosyaları için ~3GB boş alan
- **İşlemci**: Modern CPU (GPU kullanımı önerilen)

### Python Bağımlılıkları

- `torch>=2.0.0`
- `torchaudio>=2.0.0`
- `audiocraft>=1.2.0`
- `transformers>=4.30.0`
- `numpy>=1.21.0`
- `scipy>=1.9.0`

## 🎵 Örnek Çıktılar

Bestekar ile üretilmiş örnek şarkıları [examples/](examples/) klasöründe bulabilirsiniz:

- `aile_sevgisi.wav` - Aile temalı duygusal ballad
- `ayrilik_acisi.wav` - Ayrılık temalı türkü
- `umut_sarki.wav` - Umut temalı pop ballad

## 🤝 Katkıda Bulunma

1. Bu depoyu fork edin
2. Özellik dalınızı oluşturun (`git checkout -b feature/yeni-ozellik`)
3. Değişikliklerinizi commit edin (`git commit -am 'Yeni özellik eklendi'`)
4. Dalınızı push edin (`git push origin feature/yeni-ozellik`)
5. Pull Request oluşturun

## 📝 Lisans

Bu proje MIT lisansı altında lisanslanmıştır. Detaylar için [LICENSE](LICENSE) dosyasına bakın.

## 🙏 Teşekkürler

- [Facebook Research](https://github.com/facebookresearch/audiocraft) - MusicGen modeli için
- [Astral](https://github.com/astral-sh/uv) - uv paket yöneticisi için
- Tüm katkıda bulunanlar için

## 📞 İletişim

- **Geliştirici**: Yilmaz Mustafa
- **E-posta**: <ymus@tuta.io>
- **Proje**: [GitHub](https://github.com/codesapienbe/bestekar)

## 🔧 Sorun Giderme

### Yaygın Sorunlar

**Model yüklenmiyor:**

```bash
# CUDA bellek sorunu
export PYTORCH_CUDA_ALLOC_CONF=max_split_size_mb:512

# CPU kullanımı zorlama
export CUDA_VISIBLE_DEVICES=""
```

**AudioCraft kurulum sorunu:**

```
uv add audiocraft --extra-index-url https://download.pytorch.org/whl/cpu
```

**Bellek yetersizliği:**

- Model parametrelerinde `duration` değerini azaltın (örn: 15 saniye)
- Daha küçük batch boyutu kullanın

### Performans İpuçları

- GPU kullanımı için CUDA kurulu olduğundan emin olun
- İlk çalıştırmada model dosyaları indirilir (~3GB)
- SSD kullanımı önerilir
- Uzun şarkılar için RAM kullanımını izleyin

---

  🎵 Hayallerinizdeki melodileri Bestekar ile yaratın! 🎵

---

## 📋 Celery Task Management

Bestekar now supports distributed task processing using Celery with an in-memory broker (no Redis required).

### Prerequisites

**Dependencies**: Already included in `pyproject.toml`
```toml
"celery>=5.3.0"
```

### Starting Celery Worker

Open a separate terminal and start the Celery worker:

```bash
# Start Celery worker for task processing
uv run bestekar-worker
```

This is equivalent to running:
```bash
# Alternative method (more verbose)
uv run celery -A src.bestekar worker --loglevel=info -Q generate_music,ui_actions --pool=solo
```

### Task Queues

Bestekar uses different queues for different types of tasks:

- **`generate_music`**: Music generation tasks (high priority, resource intensive)
- **`ui_actions`**: UI actions like opening help, exiting (low priority, quick)

### Viewing Tasks

1. **System Tray Menu**: Right-click tray icon → "View Music Tasks"
2. **Celery Flower** (optional monitoring):
   ```bash
   pip install flower
   uv run celery -A src.bestekar flower
   # Open http://localhost:5555 in browser
   ```

3. **Command Line**:
   ```bash
   # View active tasks
   uv run celery -A src.bestekar inspect active
   
   # View scheduled tasks  
   uv run celery -A src.bestekar inspect scheduled
   
   # View registered tasks
   uv run celery -A src.bestekar inspect registered
   ```

### Task Management Commands

```bash
# Purge all tasks
uv run celery -A src.bestekar purge

# Revoke a specific task
uv run celery -A src.bestekar control revoke <task-id>

# Get task stats
uv run celery -A src.bestekar inspect stats
```

### Fallback Mode

If Celery is not available or no worker is running, Bestekar automatically falls back to thread-based execution:

- All actions still work normally
- Tasks run in background threads instead of Celery workers
- No distributed processing capabilities
- Logs will show "Celery not available, using fallback"

### Memory-Based Broker Benefits

- **No external dependencies**: No Redis or RabbitMQ installation required
- **Simple setup**: Just run `uv run bestekar-worker` 
- **Lightweight**: Perfect for single-machine development and testing
- **Automatic cleanup**: Memory is freed when worker stops

## 🎵 Music Generation Modes

1. **Complete Song (RVC)**: Instrumental + AI vocals using RVC
2. **Instrumental Only**: Pure instrumental music generation  
3. **Vocals Only (RVC)**: Just the singing voice using RVC

## 🔧 Configuration

### Model Selection
- **Default**: `facebook/musicgen-large` (best quality)
- **Medium**: `facebook/musicgen-medium` (balanced)
- **Small**: `facebook/musicgen-small` (fastest)

### Hardware Requirements
- **Minimum**: 8GB RAM, 3GB disk space
- **Recommended**: 16GB RAM, 5GB disk space
- **Optimal**: 32GB RAM for large models

## 📁 Project Structure

```
YapayMuzik/
├── src/bestekar/__init__.py    # Main application with Celery integration
├── rvc/                        # RVC models and indices
├── music/                      # Generated output files
├── pyproject.toml             # Dependencies and project config
└── README.md                  # This file
```

## 🛠️ Development

### Running Tests
```bash
uv run pytest
```

### Code Quality
```bash
# Format code
uv run black src/

# Lint code  
uv run flake8 src/
```

## 📝 License

This project is licensed under the MIT License.

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests if applicable
5. Submit a pull request

## 📞 Support

- **Issues**: [GitHub Issues](https://github.com/YapayMuzik/Bestekar/issues)
- **Discussions**: [GitHub Discussions](https://github.com/YapayMuzik/Bestekar/discussions)
- **Documentation**: Check the code comments and this README

---

**Bestekar** - Bringing AI-powered Turkish music generation to everyone! 🎵🇹🇷
