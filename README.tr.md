<div align="center">

# Open-Dev-Plan

**Yerel LLM destekli iş planlayıcı: toplantı sesini takip edilen görevlere, kararlara ve bir takvime dönüştürür — verileriniz cihazınızdan hiç çıkmadan.**

[English README](README.md) · [Katkıda Bulunma](CONTRIBUTING.md) · [Güvenlik](SECURITY.md)

</div>

---

## Neden yerel?

Toplantı sesleri ve iş planları küçük bir ekibin ürettiği en hassas verilerden biridir. Open-Dev-Plan; LLM'ini ([Ollama](https://ollama.com) üzerinden), konuşmadan metne dönüşümünü ([faster-whisper](https://github.com/SYSTRAN/faster-whisper) üzerinden) ve depolamasını (tek bir SQLite dosyası) tamamen kendi donanımınızda çalıştırır. API anahtarı yok, bulut faturası yok, hiçbir transkript ağdan geçmiyor — bu sadece bu paragrafta verilen bir söz değil, CI'da doğrulanan bir kural (bkz. [`tests/conftest.py`](tests/conftest.py)).

## Ne yapar

- **Toplantı kaydet veya içe aktar** → Türkçe'ye ayarlanmış yerel Whisper deşifresi, halüsinasyon filtresi ve segment bazlı oynatıcı ile.
- **Aksiyon maddesi ve kararları çıkar**: yerel LLM ile, JSON şemasına kısıtlanmış olarak — her öneri bir *proposal* olarak düşer, siz onaylayana/düzenleyene/reddedene kadar gerçek bir göreve dönüşmez (hiçbir şey otomatik yazılmaz).
- **İşi takip et**: Kanban panosu ve bağımlılık farkında Gantt şeması (kritik yol dahil).
- **Toplantı planla**: doğal dilden ("Çarşamba, 1.5 saat, X müşterisiyle") — LLM sadece niyetinizi ayrıştırır; çakışma çözümü model tahmini değil, deterministik koddur.
- **`.ics` dışa/içe aktar**: tekrarlayan toplantılar (RRULE) dahil.
- **Geçmiş tüm toplantılarda ara**: hibrit tam metin + anlamsal arama ile.
- **İnce ayar yap**: kendi düzeltmelerinizle çıkarım modelini (isteğe bağlı, yerel, LoRA ile).

## Durum

🚧 Erken geliştirme aşamasında, ama temel döngü uçtan uca çalışıyor ve testlerle kaplı (gerçek yerel modellere karşı canlı bir çalıştırma dahil — bkz. `evals/README.md`).

**Şu an çalışıyor:** SQLite şema + migration'lar · yerel LLM sağlayıcı soyutlaması (Ollama, şemaya kısıtlanmış JSON çıktı) · dayanıklı/GPU-koordineli iş kuyruğu · toplantı → yapılandırılmış çıkarım hattı (aksiyon maddesi, karar, özet) — her sonuç bir *proposal* olarak düşer, hiçbiri otomatik olarak bir domain tablosuna yazılmaz · deterministik (LLM'siz) toplantı planlayıcı ve çakışma tespiti · RRULE destekli `.ics` dışa/içe aktarım · tam HTTP API + SSE iş ilerlemesi · çıkarım modelini tahminle değil veriyle seçen bir eval harness · kendi onayladığınız/düzelttiğiniz proposal'ları okuyan bir fine-tuning veri seti ihraç script'i.

**Henüz kurulmadı:** web arayüzü (Kanban/Gantt/takvim görünümleri — API hazır, frontend değil) · canlı toplantı kaydı + Whisper deşifresi (şimdilik sadece elle transkript içe aktarımı bağlı) · hibrit tam metin/anlamsal arama · günlük brief/rapor · kurulum sihirbazı. Sürüm sürüm neyin geldiği için `CHANGELOG.md`'ye bakın.

## Donanım

| VRAM | Önerilen modeller |
|------|---------------------|
| 8 GB | `qwen3:8b` (veya daha küçük), `faster-whisper` medium |
| 16 GB | Hem çıkarım hem Türkçe düzyazı için `gpt-oss:20b` (tek model neden yeterli: `evals/README.md`), `faster-whisper` large-v3-turbo |
| 24 GB+ | Yukarıdakilerin büyük versiyonları, veya düşük VRAM modunda `gpt-oss:120b` |

Sadece CPU ile de çalışır ama deşifre ve üretim belirgin şekilde yavaşlar.

## Hızlı Başlangıç

```bash
# 1. Ollama'yı kurun ve kullanacağınız modelleri çekin
ollama pull gpt-oss:20b   # çıkarım + Türkçe düzyazı (bkz. evals/README.md)
ollama pull bge-m3        # arama için embedding

# 2. Open-Dev-Plan'ı kurun ve çalıştırın (uv, Python ortamını yönetir)
uv sync
uv run odp serve
```

Bu komut tarayıcınızda `http://127.0.0.1:8765` adresini açar. İlk çalıştırma; Ollama bağlantısını, model varlığını, GPU tespitini ve ses cihazı seçimini adım adım kontrol eder.

## Geliştirme

```bash
uv sync --group dev
uv run ruff check .
uv run mypy src
uv run pytest -m "not gpu and not eval"
```

Tam iş akışı için [CONTRIBUTING.md](CONTRIBUTING.md), veri yerelliği tehdit modeli için [SECURITY.md](SECURITY.md) dosyasına bakın.

## Lisans

[Apache License 2.0](LICENSE).
