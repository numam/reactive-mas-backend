# Research Flow
## Autonomous Multi-Agent System for Poultry Supply Chain Resilience
### Stock Availability & Speed Recovery Under Disruption

---

## A. Latar Belakang & Motivasi

1. Rantai pasok ayam broiler bersifat perishable, rentan disrupsi, dan berdampak langsung pada ketersediaan stok di retail
2. Sistem tradisional bersifat reaktif dan tidak terkoordinasi antar tier
3. Multi-Agent System (MAS) memungkinkan koordinasi otomatis, deteksi dini, dan respons terstruktur terhadap disrupsi
4. Penelitian berfokus pada dua metrik utama: **Stock Availability Rate (SAR)** dan **Time to Recovery (TTR)**

---

## B. Tujuan Penelitian

1. Merancang arsitektur MAS berbasis rule untuk rantai pasok ayam broiler (5 tier)
2. Mendefinisikan mekanisme deteksi disrupsi per tier menggunakan if-then trigger rules
3. Mendefinisikan 18 koordinasi rules (Orchestrator) berdasarkan pola biner status disrupsi
4. Mengukur performa sistem melalui simulasi 100 skenario disrupsi cascade
5. Menganalisis SAR, TTR, SOD, SOF, dan RSI sebagai indikator keberhasilan

---

## C. Desain Sistem MAS

### C1. Struktur Rantai Pasok
- 5 tier berurutan: Supplier → Farm → Slaughterhouse → Wholesaler → Retail
- 1 node per tier (expandable)
- 1 Coordinating Agent (Orchestrator) yang memantau seluruh sistem

### C2. Database Lokal per Tier
- Setiap agent memiliki database lokal (variabel state)
- Variabel mencakup: stok, kapasitas, status operasional, indikator kinerja
- Threshold disrupsi dan threshold recovery didefinisikan per tier
- Interval monitoring berbeda per tier: Supplier 18 jam, Farm 9 jam, Slaughterhouse 3 jam, Wholesaler 2 jam, Retail 45 menit

### C3. Disruption Trigger Rules (File 02)
- Setiap tier memiliki set kondisi trigger (OR logic)
- Kondisi trigger: threshold stok + indikator operasional
- Onset trigger: salah satu terpenuhi → disrupted = 1
- Recovery trigger: semua kondisi terpenuhi (AND logic) → disrupted = 0

### C4. Orchestrator Rules (File 03)
- 18 rules berdasarkan pola biner (Supplier, Farm, Slaughterhouse, Wholesaler, Retail)
- Setiap rule mendefinisikan: decision, urgency, dan instruksi executable per tier
- Instruksi bersifat konkret: {variable, operation (set/multiply/add/subtract/flag), value, condition}
- Prioritas: retail stock availability selalu didahulukan

---

## D. Alur Simulasi (Per Skenario)

### D1. Fase Inisialisasi (t = 0)
1. Inisialisasi DB lokal semua tier dengan nilai normal (tanpa disrupsi)
2. Semua agen aktif, disrupted = 0 untuk semua tier
3. Coordinating Agent mulai memantau (event-driven)
4. Catat baseline metrics: SAR awal, inventory level semua tier

### D2. Fase Normal (Sebelum Disrupsi)
5. Setiap agent scan DB lokal sesuai interval monitoring masing-masing
6. Evaluasi disruption trigger rules → tidak ada yang terpenuhi
7. Agent tidak mengirim pesan ke Coordinating Agent
8. DB lokal diupdate: konsumsi demand, perubahan stok rutin
9. Catat data DB per interval ke simulation log

### D3. Fase Onset Disrupsi (Event E001 masuk)
10. Skenario disrupsi diinjeksikan ke DB lokal tier tertentu (seed node)
11. Agent tier melakukan scan berkutnya → trigger rule terpenuhi
12. Agent set disrupted = 1 di DB lokal
13. Agent kirim **DisruptionReport** ke Coordinating Agent
14. Catat t_disruption_start

### D4. Fase Koordinasi (Coordinating Agent aktif)
15. Coordinating Agent terima DisruptionReport
16. Update agent_status[node_id] = 1
17. Hitung global_pattern baru (tuple 5 elemen biner)
18. Lookup pattern ke 18 rules → match rule_id
19. Tentukan decision, urgency, dan instruksi per tier
20. Kirim **CoordinationSignal** ke tier agent yang terdampak
21. Catat rule_id, decision, urgency ke event_log

### D5. Fase Eksekusi Instruksi (Tier Agent bertindak)
22. Tier agent terima CoordinationSignal
23. Evaluasi kondisi prasyarat instruksi (jika ada)
24. Eksekusi operasi: update variabel DB lokal
25. Lanjutkan scan periodik
26. Jika ada eskalasi (skenario cascade) → ulangi D3–D5 untuk tier berikutnya

### D6. Fase Recovery
27. Tier agent scan DB lokal → evaluasi recovery conditions (AND logic)
28. Jika semua terpenuhi: set disrupted = 0
29. Kirim **RecoveryReport** ke Coordinating Agent
30. Coordinating Agent update agent_status[node_id] = 0
31. Hitung global_pattern baru → jika (0,0,0,0,0) = R1: catat t_recovery
32. Ulangi untuk setiap tier yang pulih (bertahap, sesuai skenario)

### D7. Fase Stabil Pasca Recovery
33. Semua tier disrupted = 0
34. Sistem kembali ke fase normal (D2)
35. Catat akhir skenario

---

## E. Pengukuran Metrik (Per Skenario)

36. **SAR** = (∑ interval retail_inventory ≥ safety_stock) / total_interval × 100%
37. **TTR** = t_recovery − t_disruption_start (dalam satuan jam)
38. **SOD** = total durasi stockout_flag == 1 (jam)
39. **SOF** = jumlah event stockout_flag berubah 0→1
40. **RSI** = 1 − (TTR / TTR_maksimum_teoritis)
41. **Min Stock** = nilai minimum retail_inventory selama disrupsi

---

## F. Eksperimen & Skenario

42. Total skenario: 100 skenario disrupsi cascade (LLM-generated, validated)
43. Jenis disrupsi: DISEASE, LOGISTICS, DEMAND, DISASTER, PRICE, COMBINED
44. Seed node: semua tier (terdistribusi)
45. Severity: low, medium, high, crisis
46. Setiap skenario memastikan pola biner yang muncul selalu ada di 18 rule valid
47. Validator Python memverifikasi kevalidan setiap skenario sebelum dijalankan

---

## G. Analisis & Output

48. Hitung mean, std, min, max, CI 95% untuk semua metrik (n=100)
49. Distribusi: plot histogram SAR, TTR, RSI
50. Analisis rule activation frequency per jenis disrupsi
51. Analisis cascade depth vs TTR
52. Tabel ringkasan metrik siap untuk paper akademik

---

## H. Kontribusi Penelitian

53. Arsitektur MAS rule-based adaptif untuk poultry supply chain
54. 18 orchestrator rules berbasis pola biner status disrupsi 5-tier
55. Mekanisme deteksi disrupsi dan recovery dengan threshold ganda (onset & recovery)
56. Instruksi koordinasi yang executable (bukan deskriptif)
57. Framework simulasi Python yang modular dan reproducible
58. Dataset 100 skenario disrupsi tervalidasi untuk benchmark MAS

---

## I. Revisi & Catatan Penting

> **Revisi dari diskusi:** Ditambahkan *recovery threshold* yang eksplisit dan berbeda dari *disruption threshold* (lebih ketat) untuk menghindari oscillation (sistem bolak-balik disrupted↔normal). Ini penting agar TTR terukur dengan akurat.

> **Catatan implementasi:** Dalam kondisi normal, agent *hanya* update DB lokal dan tidak mengirim pesan ke Coordinating Agent. Pesan dikirim hanya saat trigger onset terpenuhi atau recovery terpenuhi. Ini menjaga efisiensi komunikasi dan mencerminkan sistem MAS yang realistis.

> **Future work:** Ekstensi ke multi-node per tier, perbandingan MAS vs Non-MAS, dan implementasi MAS LLM (Coordinating Agent berbasis LLM).
