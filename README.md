<div align="center">

# ⚡ Qoder Automation

**Full Automation dengan UI Interaction — Auto-claim Pro Trial + 300 Credits untuk Qoder**

![Version](https://img.shields.io/badge/version-5.0.0-blue)
![Python](https://img.shields.io/badge/Python-3.8%2B-yellow?logo=python&logoColor=white)
![Platform](https://img.shields.io/badge/platform-macOS%20%7C%20Windows%20%7C%20Linux-lightgrey)
![Playwright](https://img.shields.io/badge/Playwright-Stealth-2EAD33?logo=playwright&logoColor=white)
![License](https://img.shields.io/badge/license-MIT-green)

[Fitur](#-fitur) • [Instalasi](#-instalasi) • [Cara Pakai](#-cara-menggunakan) • [Menu](#-daftar-menu) • [FAQ](#-faq)

</div>

---

## 📖 Tentang

Script Python berbasis **Playwright + Stealth** yang mengotomatisasi proses login akun Qoder melalui interaksi UI penuh (klik tombol Sign In, isi form, dll.), lengkap dengan fitur patching data aplikasi, reset menyeluruh, dan logging.

> 💡 Cocok untuk kamu yang ingin mengelola banyak akun tanpa klik manual satu per satu.

---

## ✨ Fitur

| Fitur | Keterangan |
|:---:|---|
| 🤖 | **Auto Client Login** — proses semua akun otomatis dengan interaksi UI penuh (headless + stealth) |
| 🛡️ | **Stealth Mode** — `camoufox` + `playwright-stealth` untuk menghindari deteksi bot |
| 🔧 | **Patch Qoder Data** — generate identitas baru (fake MAC, machine ID, MS device ID, UMID) |
| ♻️ | **Reset & Deep Reset** — reset aplikasi Qoder, termasuk opsi hapus semua data |
| 🖥️ | **Multi-Platform** — macOS, Windows, Linux (bisa diganti saat runtime) |
| 📄 | **Logging & Hasil** — semua aktivitas tercatat, hasil sukses/gagal terpisah |
| ⏭️ | **Smart Skip** — email yang sudah sukses tidak diproses ulang |
| ⏳ | **Random Delay** — jeda acak 30–60 detik antar akun agar lebih natural |

---

## 📋 Persyaratan

- ✅ Python **3.8+**
- ✅ Aplikasi **Qoder** sudah terinstall
- ✅ **Google Chrome** terinstall (direkomendasikan — dipakai sebagai browser prioritas)

---

## 🚀 Instalasi

### ⚡ Quick Start

```bash
git clone https://github.com/okky-x0f/qoder-creator.git
cd qoder-creator
pip install -r requirements.txt
python main.py
```

<details>
<summary><b>📦 Instalasi lengkap dengan virtual environment (klik untuk membuka)</b></summary>

<br>

```bash
# 1. Clone repository
git clone https://github.com/okky-x0f/qoder-creator.git
cd qoder-creator

# 2. Buat virtual environment (opsional tapi disarankan)
python3 -m venv venv
source venv/bin/activate        # macOS/Linux
# venv\Scripts\activate         # Windows

# 3. Install dependencies
pip install -r requirements.txt

# 4. Install browser Playwright (juga dicek otomatis saat script berjalan)
playwright install
```

</details>

### 📚 Dependencies

| Package | Fungsi |
|---|---|
| [`boto3`](https://pypi.org/project/boto3/) | AWS SDK |
| [`colorama`](https://pypi.org/project/colorama/) | Output warna di terminal |
| [`fake-useragent`](https://pypi.org/project/fake-useragent/) | User-Agent acak |
| [`camoufox`](https://pypi.org/project/camoufox/) | Browser anti-deteksi |
| [`playwright`](https://pypi.org/project/playwright/) | Otomasi browser/UI |
| [`playwright-stealth`](https://pypi.org/project/playwright-stealth/) | Plugin stealth untuk Playwright |

---

## 🏃 Cara Menggunakan

### Langkah 1️⃣ — Jalankan script

```bash
python main.py
```

### Langkah 2️⃣ — Pilih platform

```text
1. macOS (Default)
2. Windows
3. Linux
```

### Langkah 3️⃣ — Siapkan file akun

Buat file `qoder_akun.txt` di folder yang sama dengan `main.py`, satu akun per baris:

```text
email1@example.com|password1
email2@example.com|password2
email3@example.com|password3|pt-xxxxxxxxxxxxxxxxxxxxxxxxxx_xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx
```

> Kolom ke-3 **opsional**: path akun Qoder (`pt-…`). Isi kalau ingin Pro Trial
> benar-benar di-claim/diverifikasi lewat API saat proses login (menu `1`/`2`).
> Tanpa kolom itu, script hanya menjalankan login desktop dan **tidak** bisa
> membuktikan claim — hasil lama yang selalu melaporkan "300 credits" adalah
> nilai default lokal, bukan hasil claim.

> ⚠️ **Format wajib:** `EMAIL|PASSWORD` dipisahkan karakter `|`

### Langkah 4️⃣ — Pilih menu dan biarkan script bekerja 🎉

---

## 📜 Daftar Menu

| No | Menu | Kategori | Keterangan |
|:--:|---|---|---|
| `1` | Process All Accounts | 🔐 Login | Proses semua akun di `qoder_akun.txt` + claim Pro Trial lewat account path |
| `2` | Process Single Account | 🔐 Login | Login satu akun (input email & password manual) |
| `10` | Register via Invite Path | 📝 Register | Buat akun baru via `referral_code` (auto email + captcha + OTP) |
| `11` | Register Batch (Invite Path) | 📝 Register | Register banyak akun sekaligus via invite path |
| `12` | Claim Pro Trial (account path) | 🎁 Claim | Claim Pro Trial pakai **path akun** Qoder (`pt-…` / PAT) |
| `3` | Patch Qoder Data | 🔧 Patch | Generate identitas baru & patch data aplikasi |
| `4` | Reset Qoder Completely | 🔧 Patch | Reset aplikasi Qoder (dengan konfirmasi) |
| `9` | Deep Reset (All Data) | 🔧 Patch | Hapus **SEMUA** data Qoder (dengan konfirmasi) |
| `5` | Change Platform | 🖥️ Platform | Ganti target platform saat runtime |
| `6` | View Results | 🛠️ Utility | Lihat 10 hasil sukses terakhir + jumlah credits |
| `7` | View Log | 🛠️ Utility | Lihat 20 entri log terakhir |
| `8` | Check Qoder Status | 🛠️ Utility | Cek binary, data directory, dan status instalasi |
| `0` | Exit | — | Keluar dari program |

---

## 📁 File Output

File-file ini dibuat otomatis oleh script saat berjalan:

| File | Isi |
|---|---|
| 📥 `qoder_akun.txt` | Daftar akun input — format `EMAIL\|PASSWORD` |
| ✅ `qoder_sukses.txt` | Akun berhasil — format `email\|{data, credits}\|timestamp` |
| ❌ `qoder_failed.txt` | Akun gagal — format `email\|error\|timestamp` |
| 📝 `qoder_log.txt` | Log aktivitas lengkap dengan timestamp |
| ✅ `qoder_registered.txt` | Akun hasil auto-register — `email\|password\|plan\|credits\|timestamp` |
| ❌ `qoder_reg_failed.txt` | Auto-register gagal — `email\|stage\|error\|timestamp` |
| 📝 `qoder_reg_log.txt` | Log khusus auto-register |
| 🖼️ `register_debug/` | Screenshot tiap tahap (kalau gagal) |
| 🎁 `qoder_claim_result.json` | Detail panggilan claim terakhir (per endpoint) |
| 📝 `qoder_claim_log.txt` | Log claim Pro Trial |

> 🔒 **Tips:** jangan commit file-file ini ke repository. Lihat bagian [.gitignore](#-keamanan--gitignore) di bawah.

---

## 📝 Auto Register — Invite Path

Menu `10` / `11` membuat akun Qoder baru lewat **invite path** (referral code), bukan cuma login akun yang sudah ada.

**Bentuk invite path:**

```text
https://qoder.com/users/sign-up?referral_code=pt-xxxxxxxxxxxxxxxxxxxxxxxxxx_xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx
                                                    └──────────── bagian yang dipakai script ────────────┘
```

Yang diinput ke script adalah nilai `referral_code`-nya saja (diawali `pt-`). Halaman akan menampilkan
*"You've been invited to Qoder — Sign up to get free Pro trial and 300 Credits"*.

**Alur otomatis (dari bundle app `qbase/qoder 0.0.757`):**

1. Buat inbox sementara via **mail.tm** (`api.mail.tm`)
2. Buka `/users/sign-up?referral_code=<CODE>`
3. Step 1 — first name, last name, email, setuju ToS → **Continue**
4. Step 2 — password (email dibawa form) → **Continue**
5. **Aliyun slider captcha** — dipecahkan lewat template matching:
   `#aliyunCaptcha-puzzle` dicocokkan ke `#aliyunCaptcha-img`, lalu
   `#aliyunCaptcha-sliding-slider` di-drag ke posisi gap (trajectory smoothstep + jitter)
6. OTP dikirim ke inbox → dibaca dari mail.tm → diisi otomatis
7. Verifikasi sukses dengan `GET /api/v1/me` (session aktif → plan + credits tercatat)

**Endpoint yang dipakai:**

| Endpoint | Fungsi |
|---|---|
| `POST /api/v1/verificationCodes` | kirim OTP — `{channel:"email", scene, email}` |
| `POST /api/v1/users` | buat akun — `{type,email,password,code,name,invitation_code,attribution,channel_code,channel_ref,landing_id,captured_at}` |
| `GET /api/v1/me` | bukti sukses — plan + credits |

**Penggunaan langsung (tanpa menu):**

```bash
python qoder_register.py --count 1
python qoder_register.py --code pt-xxxx... --count 5
python qoder_register.py --headed --keep-open     # lihat browsernya
python qoder_register.py --proxy http://user:pass@host:port
```

> ⚠️ Captcha Aliyun dinamis — kalau gagal, script otomatis minta puzzle baru sampai 6x.
> Domain mail.tm bisa saja ditolak Qoder; ganti domain/provider di `qoder_register.py` bila perlu.
> Delay default antar akun 10s (+jitter) supaya tidak terlalu cepat.

---

## 🎁 Claim Pro Trial — Account Path (`pt-…`)

Menu `12` mengecek / mengambil Pro Trial memakai **path akun** Qoder. Path itu berbentuk
`pt-xxxxxxxxxxxxxxxxxxxxxxxxxx_xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx` — **PAT (Personal
Access Token)**, bukan referral dan bukan URL. Segmen UUID di belakangnya adalah userId akun.

**Kenapa bukan lewat web:** permukaan `pro-upgrade/*` sudah mati (404). Yang hidup adalah
family *activity claim* + campaign, semuanya lewat `*.qoder.sh`:

| Langkah | Endpoint | Auth |
|---|---|---|
| Path → identitas | `POST center.qoder.sh/algo/api/v3/user/jobToken?Encode=1` | static headers (appcode `cosy`) |
| Region table | `GET center.qoder.sh/algo/api/v2/service/region/endpoints` | COSY |
| Eligibility | `GET center.qoder.sh/api/v2/activity/claim/eligibility` | `Bearer <jobToken>` |
| Campaigns | `GET center.qoder.sh/sash/api/v1/me/campaigns` | `Bearer <jobToken>` |
| Claim activity | `POST center.qoder.sh/api/v2/activity/claim?activityId=…` | `Bearer <jobToken>` |
| Claim campaign | `POST …/sash/api/v1/me/campaigns/{id}/claim` | `Bearer <jobToken>` |
| Activity list | `GET api2.qoder.sh/algo/api/v2/activity` | COSY (sign body `""`) |

Body request ditransform dulu: base64 → rotasi sepertiga → substitusi alfabet `_doRTgHZ…`.
Header COSY dibangun dari AES-128-CBC (key = IV) + RSA-PKCS1v15 + md5 berantai.

```bash
python qoder_claim.py --path pt-xxxxxxxx                 # cek + laporan
python qoder_claim.py --path pt-xxxxxxxx --claim         # benar-benar POST claim
python qoder_claim.py --paths paths.txt --claim          # batch (1 path per baris)
python qoder_claim.py --path pt-xxxxxxxx --wait-minutes 30   # tunggu sampai claimable
python qoder_claim.py --path pt-xxxxxxxx --realm cn
python qoder_claim.py --path pt-xxxxxxxx --proxy http://user:pass@host:port
```

Mode di menu `12`:

| Mode | Fungsi |
|---|---|
| `1` | satu path — cek + laporan |
| `2` | batch file — `EMAIL\|PASSWORD\|PATH` juga diterima, kolom terakhir dipakai |
| `3` | tunggu sampai claimable — polling tiap 60s sampai batas menit |

Verdict yang mungkin:

| Verdict | Arti |
|---|---|
| `claimed` | claim POST sukses, id tercatat di `claimed` |
| `claimable-not-claimed` | ada activity yang bisa diklaim (mode cek saja) |
| `campaign-visible` | campaign kelihatan tapi belum `CLAIMABLE` |
| `no-claim-provisioned` | path valid, tapi server belum memprovisikan Pro Trial |
| `pat-invalid` | exchange PAT gagal (path salah/expired) |

Catatan: `GET /algo/api/v2/activity` di host inference menjawab `403 Signature
invalid` untuk identitas hasil PAT — desktop menandatanganinya dengan skema HMAC
shared-process, bukan COSY. Panggilan itu opsional; keputusan claim diambil dari
`eligibility` + `campaigns` yang dua-duanya jalan dengan Bearer job token.

Hasil terakhir untuk path yang diuji (`fuadi afrizalni`, userId `01a1d5f9-…`):

```text
PAT exchange            HTTP 200   identity resolved
/api/v2/activity/claim/eligibility  HTTP 200  {"code":0,"data":[]}
/sash/api/v1/me/campaigns           HTTP 200  {"claimable":false,"campaigns":[]}
/api/v2/activity/quota/reset/latest HTTP 200  {"code":0,"msg":"ok"}
verdict: no-claim-provisioned
```

Panggilan `/algo/api/v2/activity` (list activity) 403 `Signature invalid` untuk identitas
PAT — itu skema tanda tangan berbeda (HMAC shared-process milik desktop), bukan jalur
keputusan claim.

Artinya: PAT-nya valid dan bisa dipakai, tapi **belum ada Pro Trial / activity yang
diprovisikan** untuk akun itu — provisioning-nya di sisi server (cohort), bukan sesuatu yang
bisa dipaksa dari klien. Detail tiap panggilan ditulis ke `qoder_claim_result.json`.

---

## 🏗️ Struktur Kode

<details>
<summary><b>Komponen utama di <code>main.py</code> (klik untuk membuka)</b></summary>

<br>

| Komponen | Keterangan |
|---|---|
| `QoderClientAutomation` | Otomasi login client via Playwright (stealth, UI interaction) |
| `qoder_register.py` | Auto-register akun baru via invite path (mail.tm + Aliyun slider solver) |
| `qoder_claim.py` | Claim Pro Trial via path akun (`pt-…`): PAT→jobToken, COSY signing, activity/campaign claim |
| `auto_register()` / `register_menu()` | Driver + menu untuk auto-register |
| `solve_aliyun_slider()` | Pecahkan captcha slider Aliyun (template matching + drag) |
| `QoderPatcher` | Patching data aplikasi & generate identitas baru per platform |
| `get_platform_config()` | Konfigurasi path aplikasi Qoder per platform |
| `init_platform()` | Inisialisasi path berdasarkan platform yang dipilih |
| `ensure_playwright_browsers()` | Cek & pastikan browser Playwright/Chrome tersedia |
| `reset_qoder_completely()` | Reset aplikasi Qoder secara menyeluruh |
| `reset_qoder_deep()` | Deep reset — hapus semua data Qoder |

</details>

---

## ❓ FAQ

<details>
<summary><b>Browser tidak ditemukan / Playwright error?</b></summary>

<br>

Jalankan install browser secara manual:

```bash
playwright install
```

Script juga akan mencoba mengecek dan menginstall browser secara otomatis saat startup.

</details>

<details>
<summary><b>Script tidak menemukan aplikasi Qoder?</b></summary>

<br>

Pastikan Qoder terinstall di path standar:

- **macOS:** `/Applications/Qoder.app`
- **Windows:** `C:\Program Files\Qoder\` atau `%LOCALAPPDATA%\Qoder\`
- **Linux:** `/usr/bin/qoder` atau `/usr/local/bin/qoder`

Gunakan menu **8 (Check Qoder Status)** untuk memverifikasi deteksi aplikasi.

</details>

<details>
<summary><b>Akun saya tidak diproses ulang, kenapa?</b></summary>

<br>

Ini fitur **Smart Skip** — email yang sudah tercatat sukses di `qoder_sukses.txt` otomatis dilewati. Hapus baris email tersebut dari `qoder_sukses.txt` jika ingin memprosesnya lagi.

</details>

---

## 🔐 Keamanan & .gitignore

File `qoder_akun.txt` berisi **kredensial akun** — jangan pernah di-upload ke repository publik. Tambahkan `.gitignore` berikut:

```gitignore
qoder_akun.txt
qoder_sukses.txt
qoder_failed.txt
qoder_log.txt
venv/
__pycache__/
```

---

## ⚠️ Disclaimer

> Project ini dibuat untuk tujuan **edukasi dan pembelajaran otomasi** saja. Penggunaan script ini dapat melanggar Terms of Service dari Qoder. Segala risiko penggunaan sepenuhnya menjadi tanggung jawab pengguna. **Gunakan dengan bijak.**

---

## 📄 Lisensi

Dilisensikan di bawah [MIT License](LICENSE) © [okky-x0f](https://github.com/okky-x0f)

---

<div align="center">

⭐ **Suka dengan project ini? Beri bintang di repository ini!** ⭐

[🐛 Report Bug](https://github.com/okky-x0f/qoder-creator/issues) • [💡 Request Feature](https://github.com/okky-x0f/qoder-creator/issues)

</div>
