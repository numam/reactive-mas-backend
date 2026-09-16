# Reactive MAS — Poultry Supply Chain Resilience (Backend)

Simulasi ketahanan rantai pasok unggas menggunakan **Reactive Baseline Multi-Agent System (MAS)**. Setiap agen tier (Supplier → Farm → Slaughterhouse → Wholesaler → Retail) bereaksi secara mandiri terhadap disrupsi tanpa koordinasi terpusat.

Simulasi mencakup **100 skenario Avian Influenza (AI)** yang telah digenerate secara programatik dengan distribusi severity, seed node, cascade depth, dan durasi yang terkontrol.

> **Frontend** tersedia secara terpisah di: [https://github.com/numam/reactive-mas-frontend](https://github.com/numam/reactive-mas-frontend)

---

## Daftar Isi

- [Arsitektur Sistem](#arsitektur-sistem)
- [Struktur Folder](#struktur-folder)
- [Prasyarat](#prasyarat)
- [Instalasi](#instalasi)
- [Menjalankan Backend](#menjalankan-backend)
- [API Endpoints](#api-endpoints)
- [Skenario Simulasi](#skenario-simulasi)
- [Output Simulasi](#output-simulasi)

---

## Arsitektur Sistem

```
Frontend (React/Next.js)          Backend (FastAPI)
  github.com/numam/          ←→    localhost:8000
  reactive-mas-frontend
```

Reactive mode bekerja dengan mekanisme berikut:
- Setiap tier memiliki **fixed reorder policy** berdasarkan threshold inventory lokal
- Tidak ada `CoordinationSignal` dari orchestrator
- Supply flow dikurangi oleh faktor tetap saat disrupsi terdeteksi secara lokal
- Metrik yang dihasilkan: **SAR**, **TTR**, **SOD**, **SOF**, **RSI**

---

## Struktur Folder

```
code/
├── backend/
│   ├── main.py               # FastAPI app — entry point API
│   ├── requirements.txt      # Python dependencies
│   ├── start.bat             # Script start server (Windows)
│   └── stop.bat              # Script stop server (Windows)
├── hitl/
│   ├── reactive_baseline.py  # Engine simulasi reactive mode
│   ├── agent_database.py     # Definisi agen dan variabel per tier
│   ├── disruption_triggers.py# Aturan deteksi disrupsi per tier
│   ├── scenario_loader.py    # Load scenarios_100.json
│   ├── scenario_generator.py # Generate ulang 100 skenario
│   ├── scenario_validator.py # Validasi skenario
│   ├── scenarios_100.json    # 100 skenario AI outbreak (pre-generated)
│   ├── data_normal_*.csv     # Data baseline normal operasi per tier
│   └── output_3mode/         # Folder output hasil simulasi
└── dataset/                  # Salinan dataset CSV
```

---

## Prasyarat

- **Python 3.10+**
- pip
- Laragon dengan MySQL/MariaDB aktif
- HeidiSQL (untuk menjalankan schema database)

---

## Instalasi

**1. Clone repository**

```bash
git clone https://github.com/numam/reactive-mas-backend.git
cd reactive-mas-backend
```

**2. Buat virtual environment (direkomendasikan)**

```bash
python -m venv venv

# Windows
venv\Scripts\activate

# Linux / macOS
source venv/bin/activate
```

**3. Install dependencies**

```bash
pip install -r backend/requirements.txt
```

### Menyiapkan database Laragon melalui HeidiSQL

1. Jalankan **MySQL** dari Laragon.
2. Buka HeidiSQL dan buat koneksi baru dengan host `127.0.0.1`, port `3306`,
  user `root`, serta password sesuai konfigurasi Laragon.
3. Pilih database `supply` yang sudah dibuat.
4. Buka file [`database/supply_schema.sql`](database/supply_schema.sql), buka
  di query tab HeidiSQL, lalu jalankan seluruh script.

Script membuat 19 tabel InnoDB, foreign key, composite primary key untuk tabel
junction, index unik yang relevan, dan validasi CHECK. Kolom polimorfik
(`vehicle.owner_id`, `shipment.origin_id`, `shipment.destination_id`, dan
`inspection.entity_id`) sengaja tidak diberi FK tunggal karena dapat menunjuk
lebih dari satu tabel; `*_type` menjadi discriminator dan divalidasi di API.

Konfigurasi koneksi backend menggunakan environment variable berikut (nilai
default cocok dengan instalasi Laragon umum):

```text
DB_HOST=127.0.0.1
DB_PORT=3306
DB_USER=root
DB_PASSWORD=
DB_NAME=supply
```

---

## Menjalankan Backend

Jalankan perintah berikut dari **root folder** (folder `code/`), setelah MySQL
Laragon aktif:

```bash
python -m uvicorn backend.main:app --host 0.0.0.0 --port 8000 --reload
```

Server akan berjalan di `http://localhost:8000`.

Dokumentasi API interaktif tersedia di:
- **Swagger UI**: [http://localhost:8000/docs](http://localhost:8000/docs)
- **ReDoc**: [http://localhost:8000/redoc](http://localhost:8000/redoc)

> Alternatif: gunakan script `backend/start.bat` (Windows only).

`backend/start.bat` sekarang juga menjalankan `backend.main:app` dari root
project. Ini diperlukan agar modul `backend.db` dan `backend.routers` dapat
diimpor dengan benar.

Untuk memeriksa koneksi SQL:

```text
GET http://127.0.0.1:8000/api/v1/database/health
```

Jika MySQL belum aktif atau kredensial salah, endpoint mengembalikan HTTP 503.

---

## API Endpoints

### Info
| Method | Endpoint | Deskripsi |
|--------|----------|-----------|
| GET | `/` | Status server |

### Agent Database
| Method | Endpoint | Deskripsi |
|--------|----------|-----------|
| GET | `/agents` | Semua agen dan variabelnya |
| GET | `/agents/{node_type}` | Detail satu tier |
| GET | `/agents/{node_type}/initial-state` | State awal default |

### Skenario (100 skenario)
| Method | Endpoint | Deskripsi |
|--------|----------|-----------|
| GET | `/hitl/scenarios` | Daftar skenario (paginasi, filter severity/type) |
| GET | `/hitl/scenarios/{id}` | Detail satu skenario |
| GET | `/hitl/scenarios/{id}/events` | Event timeline disrupsi |
| GET | `/hitl/scenarios/meta/severity-distribution` | Distribusi per severity |

### Simulasi
| Method | Endpoint | Deskripsi |
|--------|----------|-----------|
| POST | `/hitl/simulate/scenario` | Jalankan satu skenario |
| POST | `/hitl/simulate/batch` | Jalankan batch (subset atau semua 100) |

**Request body `/hitl/simulate/scenario`:**
```json
{
  "scenario_id": 1,
  "mode": "reactive",
  "verbose": false,
  "rng_seed": 42
}
```

**Request body `/hitl/simulate/batch`:**
```json
{
  "mode": "reactive",
  "rng_seed": 42,
  "scenario_ids": [1, 2, 3]
}
```
> Gunakan `"scenario_ids": null` untuk menjalankan semua 100 skenario sekaligus.

### Hasil Simulasi
| Method | Endpoint | Deskripsi |
|--------|----------|-----------|
| GET | `/hitl/results/metrics` | Metrics semua skenario yang sudah dijalankan |
| GET | `/hitl/results/stock-log` | Log inventori per tick |
| GET | `/hitl/results/summary` | Statistik deskriptif (mean, std, CI 95%) |
| GET | `/hitl/results/sar-by-severity` | SAR rata-rata per severity |
| POST | `/hitl/results/rebuild` | Rebuild file gabungan dari subfolder |

### Download CSV
| Method | Endpoint | Deskripsi |
|--------|----------|-----------|
| GET | `/hitl/csv/list` | Daftar file CSV yang tersedia |
| GET | `/hitl/csv/download/{filename}` | Download file gabungan |
| GET | `/hitl/csv/scenario/{id}/{filename}` | Download CSV per skenario |
| GET | `/hitl/csv/scenario/{id}/json/{datatype}` | Ambil CSV sebagai JSON |

### Supply Chain Database

Endpoint ini membaca tabel SQL `supply` secara read-only. Nama tabel memakai
whitelist sehingga nama tabel tidak pernah diteruskan bebas ke query.

| Method | Endpoint | Deskripsi |
|--------|----------|-----------|
| GET | `/api/v1/database/health` | Cek koneksi MySQL |
| GET | `/api/v1/database/tables` | Daftar tabel yang tersedia |
| GET | `/api/v1/database/{table}?limit=100&offset=0` | Baca baris tabel dengan paginasi |

Contoh request:

```text
GET http://127.0.0.1:8000/api/v1/database/farm?limit=20&offset=0
```

Contoh response:

```json
{
  "table": "farm",
  "total": 1,
  "limit": 20,
  "offset": 0,
  "data": [{"farm_id": "FRM-JBR-008", "farm_name": "Peternakan Berkah Mandiri"}]
}
```

### Akses dari frontend

Frontend cukup mengatur base URL ke `http://127.0.0.1:8000` saat development.
Contoh JavaScript:

```javascript
const API_BASE_URL = "http://127.0.0.1:8000";

export async function getFarms(page = 0, pageSize = 20) {
  const params = new URLSearchParams({
    limit: String(pageSize),
    offset: String(page * pageSize),
  });
  const response = await fetch(`${API_BASE_URL}/api/v1/database/farm?${params}`);
  if (!response.ok) throw new Error("Gagal mengambil data farm");
  return response.json();
}
```

Untuk daftar entitas lain, ganti `farm` dengan nama tabel dari
`GET /api/v1/database/tables`. Swagger tersedia di `/docs` dan menjadi sumber
kontrak interaktif terbaru untuk frontend.

---

## Skenario Simulasi

Semua 100 skenario bertipe **AVIAN_INFLUENZA** dengan distribusi:

| Severity | Jumlah | Seed Node Utama |
|----------|--------|-----------------|
| `low` | 15 | farm, supplier, slaughterhouse |
| `medium` | 30 | farm, supplier, slaughterhouse, wholesaler |
| `high` | 35 | farm, supplier, slaughterhouse, wholesaler, retail |
| `crisis` | 20 | farm, supplier |

Durasi simulasi: 48h / 72h / 96h / 120h (15 menit per tick).

Untuk generate ulang skenario:
```bash
cd hitl
python scenario_generator.py
```

---

## Output Simulasi

Hasil disimpan di `hitl/output_3mode/`:

```
output_3mode/
├── scenario_001/
│   ├── metrics.csv       # Metrik per skenario (SAR, TTR, SOD, SOF, RSI)
│   └── stock_log.csv     # Log inventori per tick per tier
├── scenario_002/
│   └── ...
└── scenario_metrics_3mode.csv  # Gabungan metrics semua skenario
```

### Metrik yang Dihasilkan

| Metrik | Singkatan | Deskripsi |
|--------|-----------|-----------|
| Stock Availability Rate | SAR (%) | Persentase waktu inventori ≥ safety stock |
| Time to Recovery | TTR (jam) | Durasi dari onset disrupsi hingga pulih |
| Stockout Duration | SOD (jam) | Total waktu inventori = 0 |
| Stockout Frequency | SOF | Jumlah kejadian stockout |
| Recovery Speed Index | RSI | 1 − TTR/duration (semakin tinggi semakin cepat pulih) |
