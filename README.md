# Welcome to Nautica

Sebuah repository serverless tunnel studi kasus Indonesia

> ## NOTES.md
>
> Kamu tidak perlu membayar untuk menggunakan kode dalam repository/layanan ini.  
> Kalau kamu membayar kepada siapapun, berarti kamu terkena scam.

# Fitur

- [x] Otomatis split protocol VLESS, Trojan, Shadowsocks, dan VMess
- [x] Support VMess AEAD (kompatibel dengan V2Ray)
- [x] Reverse proxy
- [x] Cache daftar proxy
- [x] Support TCP dan DoH
- [x] Transport Websocket CDN dan SNI
- [x] KV proxy key (proxy berdasarkan country)
- [x] Pagination
- [x] Tampilan web bagus dan minimalis (Menurut saya)
- [x] Dark mode
- [x] Auto check (ping) akun
- [x] Ambil akun dalam beberapa format (link, clash, sing-box, dll)
- [x] Registrasi wildcard
- [x] Menambahkan filter
  - [x] Negara `&cc=ID,SG,...`
- [x] Subscription API
  - [x] Country Code `&cc=ID,SG,JP,KR,...`
  - [x] Format `&format=raw|clash|vless|sfa|bfr|v2ray`
  - [x] Limit `&limit=10`
  - [x] VPN `&vpn=vless,trojan,ss,vmess`
  - [x] Port `&port=443,80`
  - [x] Domain `&domain=zoom.us`
- [x] Tombol `Deploy to workers` untuk instant deployment

# Todo (Belum Selesai)

- [x] Lebih efisien (Partial) (I hate Javascript btw, jadi males buat benerin)
- [ ] Skema URL shadowsocks

Kode ini masih perlu banyak perbaikan, jadi silahkan berkontribusi dan berikan PR kalian!

# Catatan

- Harus UUID v4 Variant 2
- Gunakan security `none`
- Gunakan DoH di aplikasi VPN kalian jika tidak bisa browsing atau membuka website
  - Contoh DoH `https://8.8.8.8/dns-query`
- **VMess Protocol:**
  - Mendukung VMess AEAD sesuai spesifikasi V2Ray
  - Enkripsi menggunakan AES-128-GCM
  - UUID default untuk testing: `00000000-0000-0000-0000-000000000000`
  - AlterID harus `0` (AEAD mode)
  - Security: `zero`

# Cara Deploy

## Instant

Klik tombol di bawah  
[![Deploy to Cloudflare Workers](https://deploy.workers.cloudflare.com/button)](https://deploy.workers.cloudflare.com/?url=https://github.com/xsvs77/Nautica)

## Manual

1. Buat akun cloudflare
2. Buat worker
3. Copy kode dari `_worker.js` ke editor cloudflare worker
4. (Optional) Masukkan link daftar proxy kalian ke dalam environemnt variable `PROXY_BANK_URL`
5. (Optional) Masukkan link target reverse proxy ke environment variable `REVERSE_PROXY_TARGET`
6. Deploy
7. Buka `https://DOMAIN_WORKER_KALIAN/sub`

- Contoh daftar proxy [proxyList.txt](https://raw.githubusercontent.com/dickymuliafiqri/Nautica/refs/heads/main/proxyList.txt)
- Contoh reverse proxy [example.com](https://example.com)

## Konfigurasi Cloudflare Worker

Kode yang digunakan untuk deployment adalah `_worker.js` (sesuai `main` pada `wrangler.toml`). Versi saat ini tidak memerlukan KV Namespace binding; daftar proxy KV dibaca dari file JSON melalui HTTPS.

Atur environment variables berikut di **Worker → Settings → Variables and Secrets**:

| Nama | Jenis | Wajib | Fungsi |
|---|---|---:|---|
| `VMESS_UUID` | Secret | Disarankan jika VMess dipakai | UUID autentikasi VMess. Nilai yang sama dipakai saat membuat subscription dan membaca header VMess. |
| `PROXY_BANK_URL` | Variable | Tidak | URL daftar proxy format `IP,port,CC,ISP`. Default: Proxy Bank Indonesia di repository ini. Alias lama: `PRX_BANK_URL`. |
| `KV_PROXY_URL` | Variable | Tidak | URL HTTPS file JSON proxy per negara. Default: `kvProxyList.json` di repository ini. |
| `REVERSE_PROXY_TARGET` | Variable | Tidak | Host/URL tujuan reverse proxy untuk path yang tidak dikenali. Default: `example.com`. Alias lama: `REVERSE_PRX_TARGET`. |

**Penting untuk VMess:** jika `VMESS_UUID` tidak diatur, kompatibilitas lama menggunakan UUID nol yang diketahui publik. Untuk penggunaan pribadi/produksi, buat UUID sendiri dan simpan sebagai Secret bernama `VMESS_UUID`. Jangan gunakan UUID nol untuk layanan publik.

Setelah mengatur variabel/secret, deploy Worker. Tidak ada langkah aktivasi API melalui variabel `rootDomain` atau `serviceName` pada kode `_worker.js` saat ini. Untuk domain sendiri, tambahkan domain melalui **Worker → Settings → Domains & Routes → Add Custom Domain** dan pastikan DNS/domain dikelola di Cloudflare.

### Catatan akses dan keamanan

- Endpoint subscription dan pemeriksaan proxy bersifat publik pada kode saat ini; gunakan Cloudflare WAF/rate limiting jika Worker dibuka untuk umum.
- Jangan memasukkan kredensial atau data sensitif ke koneksi melalui proxy publik.
- Jika tidak mengatur `PROXY_BANK_URL` atau `KV_PROXY_URL`, Worker mengambil daftar default dari repository `xsvs77/Nautica`.
- Pastikan URL daftar proxy khusus menggunakan HTTPS (Proxy Bank juga menerima HTTP untuk kompatibilitas, tetapi HTTPS lebih disarankan).

# Endpoint

- `/` -> Halaman utama reverse proxy
- `/sub/:page` -> Halaman sub/list akun
- `/api/v1/sub` -> Subscription link, [Queries](#fitur)

# Footnote

- Hal aneh lain yang saya kerjakan [FoolVPN](https://t.me/foolvpn)
- Tanya-tanya -> [Telegram](https://t.me/d_fordlalatina)


## Indonesia Proxy Bank

Nautica's default Indonesia proxy bank is:
`https://raw.githubusercontent.com/xsvs77/Nautica/main/proxyList-ID.txt`

The scheduled GitHub Actions workflow collects candidates from public country-filtered feeds, then independently tests each candidate through HTTPS and keeps only endpoints whose observed exit IP geolocates to Indonesia. It refreshes every 30 minutes and can also be run manually from **Actions → Refresh Indonesia Proxy Bank → Run workflow**.

Sources: [ProxyScrape Indonesia HTTP feed](https://github.com/ProxyScrape/free-proxy-list) and [ProxMint public proxy feed](https://github.com/proxmint/free-proxy-list). Public proxies are third-party systems and may disappear at any time. Use only for testing; never send credentials or sensitive traffic through them.
