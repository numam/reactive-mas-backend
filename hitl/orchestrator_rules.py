"""
╔══════════════════════════════════════════════════════════════════════╗
║  FILE 03 — ORCHESTRATOR RULES v2 (EXECUTABLE INSTRUCTIONS)          ║
║  MAS Poultry Supply Chain                                            ║
║                                                                      ║
║  Setiap instruksi bersifat EXECUTABLE:                               ║
║    - variable  : atribut DB yang diubah                              ║
║    - operation : set / multiply / add / subtract / flag              ║
║    - value     : nilai baru / faktor / delta                         ║
║    - condition : (opsional) prasyarat sebelum eksekusi               ║
╚══════════════════════════════════════════════════════════════════════╝

Format instruksi per tier:
  {
    "variable"  : nama variabel di DB agent,
    "operation" : "set" | "multiply" | "add" | "subtract" | "flag",
    "value"     : nilai (float/int/str/bool),
    "condition" : ekspresi string opsional (dievaluasi dari DB state),
    "description": penjelasan singkat
  }

Operasi yang tersedia:
  set      → variable = value
  multiply → variable = variable * value
  add      → variable = variable + value
  subtract → variable = max(0, variable - value)
  flag     → variable = value  (khusus status/flag string atau bool)
"""

ORCHESTRATOR_RULES = {

    # ══════════════════════════════════════════════════════════════════
    # R1 — TIDAK ADA DISRUPSI
    # Pattern: (0,0,0,0,0)
    # ══════════════════════════════════════════════════════════════════
    "R1": {
        "pattern"     : (0, 0, 0, 0, 0),
        "decision"    : "Not Disruption",
        "urgency"     : "normal",
        "justification": "Tidak ada entitas yang mengalami gangguan",
        "instructions": {
            "supplier"      : [],
            "farm"          : [],
            "slaughterhouse": [],
            "wholesaler"    : [],
            "retail"        : [],
        },
    },

    # ══════════════════════════════════════════════════════════════════
    # R2 — SUPPLIER TERGANGGU
    # Pattern: (1,0,0,0,0)
    # ══════════════════════════════════════════════════════════════════
    "R2": {
        "pattern"     : (1, 0, 0, 0, 0),
        "decision"    : "Potential Disruption",
        "urgency"     : "normal",
        "justification": "Gangguan tunggal di Supplier berpotensi menjalar",
        "instructions": {
            "supplier": [
                {
                    "variable"   : "lead_time",
                    "operation"  : "multiply",
                    "value"      : 0.9,
                    "description": "Kurangi lead_time 10% dengan mempercepat proses pengiriman",
                },
            ],
            "farm": [
                {
                    "variable"   : "feed_stock",
                    "operation"  : "multiply",
                    "value"      : 1.0,
                    "condition"  : "feed_stock > expected_daily_feed * 5",
                    "description": "Pertahankan feed_stock; tidak ada aksi jika stok cukup > 5 hari",
                },
            ],
            "slaughterhouse": [],
            "wholesaler": [
                {
                    "variable"   : "reorder_point",
                    "operation"  : "multiply",
                    "value"      : 1.20,
                    "description": "Naikkan reorder_point 20% sebagai buffer antisipasi gangguan",
                },
            ],
            "retail": [],
        },
    },

    # ══════════════════════════════════════════════════════════════════
    # R3 — SUPPLIER + FARM TERGANGGU
    # Pattern: (1,1,0,0,0)
    # ══════════════════════════════════════════════════════════════════
    "R3": {
        "pattern"     : (1, 1, 0, 0, 0),
        "decision"    : "Disruption",
        "urgency"     : "high",
        "justification": "Gangguan berurutan di hulu dan produksi mengancam ketersediaan",
        "instructions": {
            "supplier": [
                {
                    "variable"   : "available_supply",
                    "operation"  : "multiply",
                    "value"      : 1.10,
                    "condition"  : "available_supply < capacity * 0.5",
                    "description": "Tambah available_supply 10% dari cadangan darurat jika stok < 50%",
                },
            ],
            "farm": [
                {
                    "variable"   : "outgoing_orders",
                    "operation"  : "multiply",
                    "value"      : 0.70,
                    "description": "Kurangi outgoing_orders ke 70% untuk menyesuaikan kapasitas produksi",
                },
                {
                    "variable"   : "feed_stock",
                    "operation"  : "multiply",
                    "value"      : 0.95,
                    "description": "Kurangi konsumsi pakan 5% (efisiensi darurat)",
                },
            ],
            "slaughterhouse": [
                {
                    "variable"   : "processing_capacity",
                    "operation"  : "multiply",
                    "value"      : 0.85,
                    "description": "Sesuaikan kapasitas pemrosesan ke 85% mengikuti penurunan pasokan Farm",
                },
            ],
            "wholesaler": [
                {
                    "variable"   : "inventory_level",
                    "operation"  : "multiply",
                    "value"      : 1.0,
                    "description": "Pertahankan inventory_level; prioritaskan alokasi ke Retail",
                },
                {
                    "variable"   : "reorder_point",
                    "operation"  : "multiply",
                    "value"      : 1.30,
                    "description": "Naikkan reorder_point 30% untuk antisipasi gangguan upstream",
                },
            ],
            "retail": [],
        },
    },

    # ══════════════════════════════════════════════════════════════════
    # R4 — FARM TERGANGGU
    # Pattern: (0,1,0,0,0)
    # ══════════════════════════════════════════════════════════════════
    "R4": {
        "pattern"     : (0, 1, 0, 0, 0),
        "decision"    : "Potential Disruption",
        "urgency"     : "normal",
        "justification": "Gangguan lokal di Farm masih dapat diredam",
        "instructions": {
            "supplier": [],
            "farm": [
                {
                    "variable"   : "outgoing_orders",
                    "operation"  : "multiply",
                    "value"      : 0.80,
                    "description": "Turunkan outgoing_orders ke 80% sesuai production_capacity aktual",
                },
            ],
            "slaughterhouse": [
                {
                    "variable"   : "processing_capacity",
                    "operation"  : "multiply",
                    "value"      : 0.80,
                    "description": "Sesuaikan jadwal penerimaan; turunkan kapasitas ke 80%",
                },
            ],
            "wholesaler": [],
            "retail": [
                {
                    "variable"   : "reorder_request",
                    "operation"  : "add",
                    "value"      : 20,
                    "description": "Tambah reorder_request +20 kg — MAS coordination signal",
                },
            ],
        },
    },

    # ══════════════════════════════════════════════════════════════════
    # R5 — FARM + SLAUGHTERHOUSE TERGANGGU
    # Pattern: (0,1,1,0,0)
    # ══════════════════════════════════════════════════════════════════
    "R5": {
        "pattern"     : (0, 1, 1, 0, 0),
        "decision"    : "Disruption",
        "urgency"     : "high",
        "justification": "Gangguan berantai Farm → RPH menghambat aliran produksi",
        "instructions": {
            "supplier": [],
            "farm": [
                {
                    "variable"   : "outgoing_orders",
                    "operation"  : "multiply",
                    "value"      : 0.60,
                    "description": "Kurangi outgoing_orders ke 60% agar tidak memperburuk bottleneck RPH",
                },
            ],
            "slaughterhouse": [
                {
                    "variable"   : "processing_delay",
                    "operation"  : "subtract",
                    "value"      : 1.0,
                    "condition"  : "processing_delay > 0",
                    "description": "Kurangi processing_delay 1 jam dengan memprioritaskan antrian",
                },
                {
                    "variable"   : "queue_length",
                    "operation"  : "multiply",
                    "value"      : 0.90,
                    "description": "Percepat pemrosesan antrian; kurangi queue_length 10%",
                },
            ],
            "wholesaler": [
                {
                    "variable"   : "pending_shipments",
                    "operation"  : "multiply",
                    "value"      : 0.70,
                    "description": "Batalkan 30% pending_shipments non-prioritas untuk efisiensi distribusi",
                },
                {
                    "variable"   : "inventory_level",
                    "operation"  : "multiply",
                    "value"      : 1.0,
                    "description": "Pertahankan inventory_level saat ini; tidak ada penambahan",
                },
            ],
            "retail": [],
        },
    },

    # ══════════════════════════════════════════════════════════════════
    # R6 — SLAUGHTERHOUSE TERGANGGU
    # Pattern: (0,0,1,0,0)
    # ══════════════════════════════════════════════════════════════════
    "R6": {
        "pattern"     : (0, 0, 1, 0, 0),
        "decision"    : "Potential Disruption",
        "urgency"     : "normal",
        "justification": "Gangguan tunggal di RPH masih bisa dikompensasi",
        "instructions": {
            "supplier": [],
            "farm": [
                {
                    "variable"   : "outgoing_orders",
                    "operation"  : "multiply",
                    "value"      : 0.75,
                    "description": "Tahan outgoing_orders ke 75%; jangan kirim ayam melebihi kapasitas RPH",
                },
            ],
            "slaughterhouse": [
                {
                    "variable"   : "worker_availability",
                    "operation"  : "multiply",
                    "value"      : 1.10,
                    "condition"  : "worker_availability < 0.90",
                    "description": "Tambah ketersediaan tenaga kerja 10% (lembur/shift tambahan)",
                },
                {
                    "variable"   : "processing_delay",
                    "operation"  : "subtract",
                    "value"      : 1.0,
                    "condition"  : "processing_delay > 0",
                    "description": "Kurangi processing_delay 1 jam dengan optimasi jadwal",
                },
            ],
            "wholesaler": [
                {
                    "variable"   : "reorder_point",
                    "operation"  : "multiply",
                    "value"      : 1.15,
                    "description": "Naikkan reorder_point 15% sebagai antisipasi penurunan pasokan",
                },
            ],
            "retail": [],
        },
    },

    # ══════════════════════════════════════════════════════════════════
    # R7 — SLAUGHTERHOUSE + WHOLESALER TERGANGGU
    # Pattern: (0,0,1,1,0)
    # ══════════════════════════════════════════════════════════════════
    "R7": {
        "pattern"     : (0, 0, 1, 1, 0),
        "decision"    : "Disruption",
        "urgency"     : "high",
        "justification": "Pemrosesan dan distribusi terganggu bersamaan",
        "instructions": {
            "supplier": [],
            "farm": [
                {
                    "variable"   : "outgoing_orders",
                    "operation"  : "multiply",
                    "value"      : 0.65,
                    "description": "Kurangi outgoing_orders ke 65% karena RPH tidak bisa menerima penuh",
                },
            ],
            "slaughterhouse": [
                {
                    "variable"   : "output_stock",
                    "operation"  : "multiply",
                    "value"      : 1.10,
                    "condition"  : "output_stock < max_output * 0.5",
                    "description": "Tingkatkan output_stock 10% dengan mempercepat pemrosesan prioritas",
                },
            ],
            "wholesaler": [
                {
                    "variable"   : "delivery_schedule",
                    "operation"  : "flag",
                    "value"      : "rerouted",
                    "description": "Ubah delivery_schedule ke 'rerouted' untuk jalur distribusi alternatif",
                },
                {
                    "variable"   : "pending_shipments",
                    "operation"  : "multiply",
                    "value"      : 0.60,
                    "description": "Batalkan 40% pending_shipments non-prioritas",
                },
                {
                    "variable"   : "inventory_level",
                    "operation"  : "multiply",
                    "value"      : 1.0,
                    "description": "Lindungi inventory_level saat ini; alokasikan minimum ke Retail",
                },
            ],
            "retail": [
                {
                    "variable"   : "reorder_request",
                    "operation"  : "add",
                    "value"      : 35,
                    "description": "Tambah reorder_request +35 kg — MAS coordination signal",
                },
            ],
        },
    },

    # ══════════════════════════════════════════════════════════════════
    # R8 — WHOLESALER TERGANGGU
    # Pattern: (0,0,0,1,0)
    # ══════════════════════════════════════════════════════════════════
    "R8": {
        "pattern"     : (0, 0, 0, 1, 0),
        "decision"    : "Potential Disruption",
        "urgency"     : "normal",
        "justification": "Gangguan logistik bersifat lokal dan dapat diatasi",
        "instructions": {
            "supplier": [],
            "farm": [],
            "slaughterhouse": [],
            "wholesaler": [
                {
                    "variable"   : "delivery_schedule",
                    "operation"  : "flag",
                    "value"      : "rerouted",
                    "description": "Ubah delivery_schedule ke 'rerouted' (jalur alternatif)",
                },
                {
                    "variable"   : "pending_shipments",
                    "operation"  : "multiply",
                    "value"      : 0.85,
                    "description": "Kurangi pending_shipments 15% dengan memprioritaskan pengiriman mendesak",
                },
            ],
            "retail": [
                {
                    "variable"   : "demand_estimate",
                    "operation"  : "multiply",
                    "value"      : 0.95,
                    "description": "Sesuaikan demand_estimate ke 95% mengantisipasi keterlambatan",
                },
            ],
        },
    },

    # ══════════════════════════════════════════════════════════════════
    # R9 — WHOLESALER + RETAIL TERGANGGU
    # Pattern: (0,0,0,1,1)
    # ══════════════════════════════════════════════════════════════════
    "R9": {
        "pattern"     : (0, 0, 0, 1, 1),
        "decision"    : "Disruption",
        "urgency"     : "high",
        "justification": "Gangguan distribusi berdampak langsung pada ketersediaan Retail",
        "instructions": {
            "supplier": [],
            "farm": [],
            "slaughterhouse": [
                {
                    "variable"   : "output_stock",
                    "operation"  : "multiply",
                    "value"      : 1.15,
                    "condition"  : "output_stock < max_output * 0.7",
                    "description": "Tingkatkan output_stock 15% untuk mengisi kekosongan distribusi",
                },
            ],
            "wholesaler": [
                {
                    "variable"   : "inventory_level",
                    "operation"  : "multiply",
                    "value"      : 1.0,
                    "description": "Prioritaskan inventory_level untuk Retail; tidak ada penurunan",
                },
                {
                    "variable"   : "pending_shipments",
                    "operation"  : "multiply",
                    "value"      : 0.50,
                    "description": "Batalkan 50% pending_shipments non-prioritas untuk fokus ke Retail kritis",
                },
            ],
            "retail": [
                {
                    "variable"   : "reorder_request",
                    "operation"  : "add",
                    "value"      : 30,
                    "condition"  : "retail_inventory < safety_stock",
                    "description": "Tambah reorder_request +30 kg — MAS coordination signal",
                },
                {
                    "variable"   : "safety_stock",
                    "operation"  : "multiply",
                    "value"      : 1.10,
                    "description": "Naikkan safety_stock 10% sebagai buffer darurat",
                },
            ],
        },
    },

    # ══════════════════════════════════════════════════════════════════
    # R10 — SUPPLIER + WHOLESALER TERGANGGU
    # Pattern: (1,0,0,1,0)
    # ══════════════════════════════════════════════════════════════════
    "R10": {
        "pattern"     : (1, 0, 0, 1, 0),
        "decision"    : "Disruption",
        "urgency"     : "high",
        "justification": "Disrupsi di dua ujung rantai meningkatkan risiko sistemik",
        "instructions": {
            "supplier": [
                {
                    "variable"   : "available_supply",
                    "operation"  : "multiply",
                    "value"      : 1.10,
                    "condition"  : "available_supply < capacity * 0.6",
                    "description": "Tambah available_supply 10% dari cadangan jika stok < 60%",
                },
                {
                    "variable"   : "lead_time",
                    "operation"  : "multiply",
                    "value"      : 0.85,
                    "description": "Percepat lead_time 15% untuk mengimbangi gangguan Wholesaler",
                },
            ],
            "farm": [],
            "slaughterhouse": [],
            "wholesaler": [
                {
                    "variable"   : "distribution_capacity",
                    "operation"  : "multiply",
                    "value"      : 0.90,
                    "description": "Sesuaikan distribution_capacity ke 90% mengikuti available_supply Supplier",
                },
                {
                    "variable"   : "reorder_point",
                    "operation"  : "multiply",
                    "value"      : 1.20,
                    "description": "Naikkan reorder_point 20% untuk sinkronisasi dengan Supplier",
                },
            ],
            "retail": [],
        },
    },

    # ══════════════════════════════════════════════════════════════════
    # R11 — SUPPLIER + FARM + SLAUGHTERHOUSE TERGANGGU
    # Pattern: (1,1,1,0,0)
    # ══════════════════════════════════════════════════════════════════
    "R11": {
        "pattern"     : (1, 1, 1, 0, 0),
        "decision"    : "Disruption",
        "urgency"     : "crisis",
        "justification": "Mayoritas entitas upstream terganggu secara bersamaan",
        "instructions": {
            "supplier": [
                {
                    "variable"   : "available_supply",
                    "operation"  : "multiply",
                    "value"      : 1.15,
                    "condition"  : "available_supply < capacity * 0.5",
                    "description": "Aktifkan cadangan darurat; naikkan available_supply 15%",
                },
                {
                    "variable"   : "lead_time",
                    "operation"  : "multiply",
                    "value"      : 0.80,
                    "description": "Percepat lead_time 20% (mode darurat)",
                },
            ],
            "farm": [
                {
                    "variable"   : "outgoing_orders",
                    "operation"  : "multiply",
                    "value"      : 0.50,
                    "description": "Kurangi outgoing_orders ke 50% (minimum produksi darurat)",
                },
                {
                    "variable"   : "feed_stock",
                    "operation"  : "multiply",
                    "value"      : 0.90,
                    "description": "Efisiensi konsumsi pakan 10% untuk memperpanjang ketahanan stok",
                },
            ],
            "slaughterhouse": [
                {
                    "variable"   : "processing_capacity",
                    "operation"  : "multiply",
                    "value"      : 0.70,
                    "description": "Sesuaikan kapasitas ke 70% (kapasitas darurat minimum)",
                },
                {
                    "variable"   : "processing_delay",
                    "operation"  : "subtract",
                    "value"      : 2.0,
                    "condition"  : "processing_delay > 2",
                    "description": "Kurangi processing_delay 2 jam dengan lembur darurat",
                },
            ],
            "wholesaler": [
                {
                    "variable"   : "inventory_level",
                    "operation"  : "multiply",
                    "value"      : 1.0,
                    "description": "Lindungi seluruh inventory_level; tidak ada pengurangan",
                },
                {
                    "variable"   : "reorder_point",
                    "operation"  : "multiply",
                    "value"      : 1.40,
                    "description": "Naikkan reorder_point 40% untuk buffer maximum",
                },
            ],
            "retail": [],
        },
    },

    # ══════════════════════════════════════════════════════════════════
    # R12 — FARM + WHOLESALER TERGANGGU
    # Pattern: (0,1,0,1,0)
    # ══════════════════════════════════════════════════════════════════
    "R12": {
        "pattern"     : (0, 1, 0, 1, 0),
        "decision"    : "Disruption",
        "urgency"     : "high",
        "justification": "Produksi dan distribusi terganggu secara bersamaan",
        "instructions": {
            "supplier": [],
            "farm": [
                {
                    "variable"   : "outgoing_orders",
                    "operation"  : "multiply",
                    "value"      : 0.75,
                    "description": "Kurangi outgoing_orders ke 75% sesuai production_capacity aktual",
                },
                {
                    "variable"   : "production_capacity",
                    "operation"  : "multiply",
                    "value"      : 1.05,
                    "condition"  : "production_capacity < planned_capacity * 0.8",
                    "description": "Tingkatkan production_capacity 5% dengan intensifikasi jika masih memungkinkan",
                },
            ],
            "slaughterhouse": [],
            "wholesaler": [
                {
                    "variable"   : "distribution_capacity",
                    "operation"  : "multiply",
                    "value"      : 0.85,
                    "description": "Sesuaikan distribution_capacity ke 85% mengikuti pasokan dari Farm",
                },
                {
                    "variable"   : "delivery_schedule",
                    "operation"  : "flag",
                    "value"      : "rerouted",
                    "description": "Ubah delivery_schedule ke 'rerouted' untuk optimasi distribusi",
                },
            ],
            "retail": [],
        },
    },

    # ══════════════════════════════════════════════════════════════════
    # R13 — SUPPLIER + RETAIL TERGANGGU
    # Pattern: (1,0,0,0,1)
    # ══════════════════════════════════════════════════════════════════
    "R13": {
        "pattern"     : (1, 0, 0, 0, 1),
        "decision"    : "Disruption",
        "urgency"     : "high",
        "justification": "Ketidaksinkronan supply–demand di hulu dan hilir",
        "instructions": {
            "supplier": [
                {
                    "variable"   : "available_supply",
                    "operation"  : "multiply",
                    "value"      : 1.10,
                    "condition"  : "available_supply < capacity * 0.6",
                    "description": "Naikkan available_supply 10% untuk mengimbangi lonjakan demand Retail",
                },
                {
                    "variable"   : "lead_time",
                    "operation"  : "multiply",
                    "value"      : 0.90,
                    "description": "Percepat lead_time 10% untuk respons lebih cepat ke demand",
                },
            ],
            "farm"          : [],
            "slaughterhouse": [],
            "wholesaler": [
                {
                    "variable"   : "inventory_level",
                    "operation"  : "multiply",
                    "value"      : 1.0,
                    "description": "Pertahankan inventory_level; siapkan buffer untuk Retail",
                },
                {
                    "variable"   : "reorder_point",
                    "operation"  : "multiply",
                    "value"      : 1.25,
                    "description": "Naikkan reorder_point 25% mengantisipasi lonjakan reorder dari Retail",
                },
            ],
            "retail": [
                {
                    "variable"   : "reorder_request",
                    "operation"  : "add",
                    "value"      : 40,
                    "condition"  : "retail_inventory < safety_stock",
                    "description": "Tambah reorder_request +40 kg — MAS coordination signal",
                },
                {
                    "variable"   : "safety_stock",
                    "operation"  : "multiply",
                    "value"      : 1.15,
                    "description": "Naikkan safety_stock 15% untuk buffer demand surge",
                },
            ],
        },
    },

    # ══════════════════════════════════════════════════════════════════
    # R14 — RETAIL TERGANGGU
    # Pattern: (0,0,0,0,1)
    # ══════════════════════════════════════════════════════════════════
    "R14": {
        "pattern"     : (0, 0, 0, 0, 1),
        "decision"    : "Potential Disruption",
        "urgency"     : "normal",
        "justification": "Gangguan di Retail belum menjalar ke upstream",
        "instructions": {
            "supplier"      : [],
            "farm"          : [],
            "slaughterhouse": [],
            "wholesaler": [
                {
                    "variable"   : "reorder_point",
                    "operation"  : "multiply",
                    "value"      : 1.10,
                    "description": "Naikkan reorder_point 10% sebagai antisipasi lonjakan reorder dari Retail",
                },
            ],
            "retail": [
                {
                    "variable"   : "reorder_request",
                    "operation"  : "add",
                    "value"      : 25,
                    "condition"  : "retail_inventory < safety_stock",
                    "description": "Tambah reorder_request +25 kg — MAS coordination signal",
                },
                {
                    "variable"   : "demand_estimate",
                    "operation"  : "multiply",
                    "value"      : 1.10,
                    "description": "Update demand_estimate naik 10% untuk mencerminkan kondisi aktual",
                },
            ],
        },
    },

    # ══════════════════════════════════════════════════════════════════
    # R15 — SEMUA NODE TERGANGGU (FULL CRISIS)
    # Pattern: (1,1,1,1,1)
    # ══════════════════════════════════════════════════════════════════
    "R15": {
        "pattern"     : (1, 1, 1, 1, 1),
        "decision"    : "Disruption",
        "urgency"     : "crisis",
        "justification": "Gangguan menyeluruh pada seluruh rantai pasok",
        "instructions": {
            "supplier": [
                {
                    "variable"   : "available_supply",
                    "operation"  : "multiply",
                    "value"      : 1.20,
                    "condition"  : "available_supply < capacity * 0.4",
                    "description": "Aktifkan stok cadangan darurat penuh; naikkan available_supply 20%",
                },
                {
                    "variable"   : "lead_time",
                    "operation"  : "multiply",
                    "value"      : 0.75,
                    "description": "Percepat lead_time 25% (mode krisis penuh)",
                },
            ],
            "farm": [
                {
                    "variable"   : "outgoing_orders",
                    "operation"  : "multiply",
                    "value"      : 0.40,
                    "description": "Kurangi outgoing_orders ke 40% (produksi minimum absolut)",
                },
                {
                    "variable"   : "feed_stock",
                    "operation"  : "multiply",
                    "value"      : 0.85,
                    "description": "Efisiensi pakan 15% untuk memaksimalkan ketahanan stok",
                },
            ],
            "slaughterhouse": [
                {
                    "variable"   : "processing_capacity",
                    "operation"  : "multiply",
                    "value"      : 0.60,
                    "description": "Turunkan kapasitas ke 60% (minimum operasional darurat)",
                },
                {
                    "variable"   : "worker_availability",
                    "operation"  : "multiply",
                    "value"      : 1.10,
                    "condition"  : "worker_availability < 0.8",
                    "description": "Tambah tenaga kerja 10% (panggil semua cadangan)",
                },
            ],
            "wholesaler": [
                {
                    "variable"   : "inventory_level",
                    "operation"  : "multiply",
                    "value"      : 1.0,
                    "description": "Pertahankan seluruh inventory_level; tidak ada pengurangan",
                },
                {
                    "variable"   : "pending_shipments",
                    "operation"  : "multiply",
                    "value"      : 0.30,
                    "description": "Batalkan 70% pending_shipments; fokus hanya ke Retail kritis",
                },
                {
                    "variable"   : "distribution_capacity",
                    "operation"  : "multiply",
                    "value"      : 0.80,
                    "description": "Sesuaikan distribution_capacity ke 80% (mode krisis)",
                },
            ],
            "retail": [
                {
                    "variable"   : "reorder_request",
                    "operation"  : "add",
                    "value"      : 55,
                    "condition"  : "retail_inventory < safety_stock * 0.5",
                    "description": "Tambah reorder_request +55 kg — MAS coordination signal",
                },
                {
                    "variable"   : "safety_stock",
                    "operation"  : "multiply",
                    "value"      : 1.20,
                    "description": "Naikkan safety_stock 20% (mode krisis)",
                },
            ],
        },
    },

    # ══════════════════════════════════════════════════════════════════
    # R16 — SUPPLIER + FARM + SLAUGHTERHOUSE + WHOLESALER TERGANGGU
    # Pattern: (1,1,1,1,0)
    # ══════════════════════════════════════════════════════════════════
    "R16": {
        "pattern"     : (1, 1, 1, 1, 0),
        "decision"    : "Disruption",
        "urgency"     : "crisis",
        "justification": "4 node upstream terganggu; Retail satu-satunya yang harus dilindungi",
        "instructions": {
            "supplier": [
                {
                    "variable"   : "available_supply",
                    "operation"  : "multiply",
                    "value"      : 1.15,
                    "condition"  : "available_supply < capacity * 0.5",
                    "description": "Alokasikan seluruh cadangan; naikkan available_supply 15%",
                },
                {
                    "variable"   : "lead_time",
                    "operation"  : "multiply",
                    "value"      : 0.80,
                    "description": "Percepat lead_time 20% (prioritas Farm)",
                },
            ],
            "farm": [
                {
                    "variable"   : "outgoing_orders",
                    "operation"  : "multiply",
                    "value"      : 0.45,
                    "description": "Kurangi outgoing_orders ke 45% (minimum darurat)",
                },
            ],
            "slaughterhouse": [
                {
                    "variable"   : "processing_capacity",
                    "operation"  : "multiply",
                    "value"      : 0.65,
                    "description": "Operasikan kapasitas darurat 65%",
                },
                {
                    "variable"   : "processing_delay",
                    "operation"  : "subtract",
                    "value"      : 2.0,
                    "condition"  : "processing_delay > 2",
                    "description": "Kurangi processing_delay 2 jam (lembur penuh)",
                },
            ],
            "wholesaler": [
                {
                    "variable"   : "inventory_level",
                    "operation"  : "multiply",
                    "value"      : 1.0,
                    "description": "Lindungi seluruh inventory_level untuk Retail",
                },
                {
                    "variable"   : "pending_shipments",
                    "operation"  : "multiply",
                    "value"      : 0.20,
                    "description": "Batalkan 80% pending_shipments non-Retail",
                },
            ],
            "retail": [
                {
                    "variable"   : "safety_stock",
                    "operation"  : "multiply",
                    "value"      : 1.25,
                    "description": "Naikkan safety_stock 25% sebagai buffer krisis upstream",
                },
                {
                    "variable"   : "reorder_request",
                    "operation"  : "add",
                    "value"      : 50,
                    "condition"  : "retail_inventory < safety_stock",
                    "description": "Tambah reorder_request +50 kg — MAS coordination signal",
                },
            ],
        },
    },

    # ══════════════════════════════════════════════════════════════════
    # R17 — FARM + SLAUGHTERHOUSE + WHOLESALER + RETAIL TERGANGGU
    # Pattern: (0,1,1,1,1)
    # ══════════════════════════════════════════════════════════════════
    "R17": {
        "pattern"     : (0, 1, 1, 1, 1),
        "decision"    : "Disruption",
        "urgency"     : "crisis",
        "justification": "Gangguan mid-chain hingga downstream mengancam ketersediaan Retail",
        "instructions": {
            "supplier": [
                {
                    "variable"   : "available_supply",
                    "operation"  : "multiply",
                    "value"      : 1.20,
                    "description": "Percepat pengiriman; naikkan available_supply 20% untuk mendukung Farm",
                },
                {
                    "variable"   : "lead_time",
                    "operation"  : "multiply",
                    "value"      : 0.80,
                    "description": "Percepat lead_time 20% untuk mendukung pemulihan Farm",
                },
            ],
            "farm": [
                {
                    "variable"   : "outgoing_orders",
                    "operation"  : "multiply",
                    "value"      : 0.50,
                    "description": "Batasi outgoing_orders ke 50%; fokus pada produksi minimum",
                },
                {
                    "variable"   : "production_capacity",
                    "operation"  : "multiply",
                    "value"      : 1.05,
                    "condition"  : "production_capacity < planned_capacity * 0.7",
                    "description": "Tingkatkan production_capacity 5% jika masih memungkinkan",
                },
            ],
            "slaughterhouse": [
                {
                    "variable"   : "processing_capacity",
                    "operation"  : "multiply",
                    "value"      : 0.70,
                    "description": "Operasikan kapasitas darurat 70%",
                },
                {
                    "variable"   : "output_stock",
                    "operation"  : "multiply",
                    "value"      : 1.10,
                    "condition"  : "output_stock < max_output * 0.5",
                    "description": "Tingkatkan output_stock 10% dengan memprioritaskan pemrosesan",
                },
            ],
            "wholesaler": [
                {
                    "variable"   : "inventory_level",
                    "operation"  : "multiply",
                    "value"      : 1.0,
                    "description": "Pertahankan inventory_level; prioritaskan distribusi ke Retail",
                },
                {
                    "variable"   : "pending_shipments",
                    "operation"  : "multiply",
                    "value"      : 0.40,
                    "description": "Batalkan 60% pending_shipments; fokus ke Retail kritis",
                },
            ],
            "retail": [
                {
                    "variable"   : "reorder_request",
                    "operation"  : "add",
                    "value"      : 45,
                    "condition"  : "retail_inventory < safety_stock",
                    "description": "Tambah reorder_request +45 kg — MAS coordination signal",
                },
                {
                    "variable"   : "shortage_duration",
                    "operation"  : "subtract",
                    "value"      : 0.5,
                    "condition"  : "shortage_duration > 0",
                    "description": "Kurangi shortage_duration 0.5 jam dengan distribusi darurat",
                },
            ],
        },
    },

    # ══════════════════════════════════════════════════════════════════
    # R18 — SLAUGHTERHOUSE + WHOLESALER + RETAIL TERGANGGU
    # Pattern: (0,0,1,1,1)
    # ══════════════════════════════════════════════════════════════════
    "R18": {
        "pattern"     : (0, 0, 1, 1, 1),
        "decision"    : "Disruption",
        "urgency"     : "high",
        "justification": "Gangguan downstream langsung mengancam ketersediaan Retail",
        "instructions": {
            "supplier": [],
            "farm": [
                {
                    "variable"   : "outgoing_orders",
                    "operation"  : "multiply",
                    "value"      : 1.10,
                    "condition"  : "outgoing_orders < production_capacity * 0.8",
                    "description": "Naikkan outgoing_orders 10% untuk mengisi kekosongan RPH",
                },
            ],
            "slaughterhouse": [
                {
                    "variable"   : "processing_capacity",
                    "operation"  : "multiply",
                    "value"      : 0.75,
                    "description": "Operasikan kapasitas darurat 75%",
                },
                {
                    "variable"   : "processing_delay",
                    "operation"  : "subtract",
                    "value"      : 1.5,
                    "condition"  : "processing_delay > 1.5",
                    "description": "Kurangi processing_delay 1.5 jam dengan lembur",
                },
                {
                    "variable"   : "output_stock",
                    "operation"  : "multiply",
                    "value"      : 1.15,
                    "condition"  : "output_stock < max_output * 0.5",
                    "description": "Tingkatkan output_stock 15% jika stok di bawah 50%",
                },
            ],
            "wholesaler": [
                {
                    "variable"   : "inventory_level",
                    "operation"  : "multiply",
                    "value"      : 1.0,
                    "description": "Gunakan stok darurat; pertahankan inventory_level",
                },
                {
                    "variable"   : "pending_shipments",
                    "operation"  : "multiply",
                    "value"      : 0.50,
                    "description": "Batalkan 50% pending_shipments; fokus ke Retail kritis",
                },
                {
                    "variable"   : "delivery_schedule",
                    "operation"  : "flag",
                    "value"      : "rerouted",
                    "description": "Aktifkan jalur distribusi alternatif",
                },
            ],
            "retail": [
                {
                    "variable"   : "reorder_request",
                    "operation"  : "add",
                    "value"      : 35,
                    "condition"  : "retail_inventory < safety_stock",
                    "description": "Tambah reorder_request +35 kg — MAS coordination signal",
                },
                {
                    "variable"   : "safety_stock",
                    "operation"  : "multiply",
                    "value"      : 1.15,
                    "description": "Naikkan safety_stock 15% sebagai buffer",
                },
            ],
        },
    },
}

# ════════════════════════════════════════════════════════════════════
# INSTRUCTION EXECUTOR
# Menerapkan instruksi orchestrator ke state DB node
# ════════════════════════════════════════════════════════════════════

PATTERN_TO_RULE = {v["pattern"]: k for k, v in ORCHESTRATOR_RULES.items()}


def match_rule(pattern: tuple) -> tuple[str, dict]:
    rule_id = PATTERN_TO_RULE.get(pattern, "R1")
    return rule_id, ORCHESTRATOR_RULES[rule_id]


def apply_instructions(node_type: str, db_state: dict,
                        instructions: list[dict]) -> dict:
    """
    Terapkan instruksi orchestrator ke state DB node.
    Kembalikan state yang sudah diperbarui + log perubahan.
    """
    updated = dict(db_state)
    changes = []

    for inst in instructions:
        var       = inst["variable"]
        operation = inst["operation"]
        value     = inst["value"]
        condition = inst.get("condition")

        if var not in updated:
            continue

        # Evaluasi kondisi prasyarat (jika ada)
        if condition:
            try:
                if not eval(condition, {}, updated):
                    continue
            except Exception:
                continue

        old_val = updated[var]

        # Terapkan operasi
        if   operation == "set"      : new_val = value
        elif operation == "flag"     : new_val = value
        elif operation == "multiply" : new_val = old_val * value
        elif operation == "add"      : new_val = old_val + value
        elif operation == "subtract" : new_val = max(0, old_val - value) \
                                        if isinstance(old_val, (int, float)) \
                                        else old_val
        else:
            continue

        # Clamp nilai numerik (tidak boleh negatif)
        if isinstance(new_val, float):
            new_val = round(new_val, 4)

        updated[var] = new_val
        changes.append({
            "variable"   : var,
            "old_value"  : old_val,
            "new_value"  : new_val,
            "operation"  : operation,
            "description": inst.get("description", ""),
        })

    return updated, changes


def execute_rule(pattern: tuple,
                 all_states: dict[str, dict]) -> dict:
    """
    Eksekusi rule berdasarkan pola biner.
    all_states: {node_type: db_state}
    Kembalikan: {node_type: (updated_state, changes)}
    """
    rule_id, rule = match_rule(pattern)
    results = {}

    for node_type, instructions in rule["instructions"].items():
        if node_type not in all_states or not instructions:
            continue
        updated, changes = apply_instructions(
            node_type, all_states[node_type], instructions)
        results[node_type] = {
            "updated_state": updated,
            "changes"      : changes,
        }

    return {
        "rule_id"  : rule_id,
        "decision" : rule["decision"],
        "urgency"  : rule["urgency"],
        "results"  : results,
    }


if __name__ == "__main__":
    # Demo: eksekusi R9 (Wholesaler + Retail disrupted)
    import sys, os
    import sys, os; sys.path.insert(0, ".")
    from agent_database import init_node_state
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

    pattern = (0, 0, 0, 1, 1)
    all_states = {
        "wholesaler": init_node_state("wholesaler", {"inventory_level": 60, "pending_shipments": 80}),
        "retail"    : init_node_state("retail",     {"retail_inventory": 20, "safety_stock": 30}),
    }

    print("=== ORCHESTRATOR RULE EXECUTOR DEMO ===")
    print(f"  Pattern: {pattern}")
    result = execute_rule(pattern, all_states)
    print(f"  Rule   : {result['rule_id']} | {result['decision']} | Urgency: {result['urgency']}\n")

    for node, res in result["results"].items():
        print(f"  [{node.upper()}] Changes:")
        for c in res["changes"]:
            print(f"    {c['variable']}: {c['old_value']} → {c['new_value']}  ({c['operation']})")
