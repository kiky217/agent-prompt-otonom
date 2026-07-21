# HERMES Bootstrap Sync V1 — Preview

Preview ini menyiapkan migrasi terkontrol untuk JENDRAL, KAPTEN, dan BRIGADIR tanpa mengubah SEVEN yang sedang bekerja.

## Kontrak keselamatan

- Hanya membaca metadata dan menghitung checksum lokal.
- Tidak menulis ke folder agen, tidak menghentikan proses, dan tidak memuat ulang runtime.
- `SEVEN` selalu `BLOCKED_PROTECTED_AGENT`.
- Agen legacy dengan PID aktif selalu `BLOCKED_AGENT_RUNNING`.
- `--apply` sengaja ditolak dengan `BLOCKED_APPLY_NOT_IMPLEMENTED`.
- Tidak mengikuti branch `main` secara otomatis; penerapan mendatang wajib memakai release/tag yang dipin dan disetujui.
- Kredensial, rahasia, memori, Task Ledger, model, endpoint, approval state, dan log tetap lokal.

## Menjalankan dry-run

```powershell
python -m bootstrap_sync.bootstrap_sync --manifest bootstrap_sync/manifest.json --agent-id jendral --agent-home C:\path\to\jendral
```

Status yang mungkin:

- `READY_DRY_RUN`: inventaris aman tersedia; belum ada perubahan.
- `BLOCKED_PROTECTED_AGENT`: target adalah SEVEN atau migrasi peran dinonaktifkan.
- `BLOCKED_AGENT_RUNNING`: target legacy masih aktif.
- `BLOCKED_HOME_NOT_FOUND`: folder target tidak ditemukan.

## Urutan migrasi mendatang

1. JENDRAL.
2. KAPTEN.
3. BRIGADIR.
4. Aktifkan delegasi SEVEN hanya setelah ketiga smoke test lulus.

SEVEN tidak termasuk target migrasi preview. Perubahan untuk SEVEN membutuhkan maintenance window dan persetujuan terpisah.
