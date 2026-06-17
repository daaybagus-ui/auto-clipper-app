"""
Auto-Clipper Tool
==================
Streamlit app untuk mengunduh video YouTube, memotong durasi tertentu,
dan melakukan auto-crop 16:9 -> 9:16 agar siap upload ke TikTok/Shorts/Reels.

Dirancang untuk berjalan di Streamlit Community Cloud dengan strategi:
- yt-dlp dengan player_client alternatif (android/ios/web) untuk menghindari 403.
- Retry + backoff sederhana untuk menghindari rate-limit YouTube.
- Semua file sementara dibersihkan otomatis (saat proses selesai ATAU gagal),
  memakai direktori temp per-sesi via tempfile.TemporaryDirectory.
"""

import os
import re
import time
import shutil
import traceback
import tempfile
from pathlib import Path

import streamlit as st

# moviepy v2 menamai ulang beberapa kelas; import dibuat fleksibel.
try:
    from moviepy import VideoFileClip
except ImportError:  # fallback untuk moviepy < 2.0
    from moviepy.editor import VideoFileClip

import yt_dlp


# ----------------------------------------------------------------------------
# KONFIGURASI HALAMAN
# ----------------------------------------------------------------------------
st.set_page_config(
    page_title="Auto-Clipper Tool",
    page_icon="🎬",
    layout="centered",
)

TARGET_RATIO = 9 / 16  # lebar/tinggi untuk output vertikal


# ----------------------------------------------------------------------------
# UTIL: VALIDASI & PEMBERSIHAN
# ----------------------------------------------------------------------------
YOUTUBE_REGEX = re.compile(
    r"(https?://)?(www\.)?(youtube\.com|youtu\.be)/.+"
)


def is_valid_youtube_url(url: str) -> bool:
    return bool(YOUTUBE_REGEX.match(url.strip()))


def cleanup_dir(path: str):
    """Hapus direktori temp beserta isinya, abaikan jika sudah tidak ada."""
    try:
        if path and os.path.exists(path):
            shutil.rmtree(path, ignore_errors=True)
    except Exception:
        # Pembersihan tidak boleh membuat aplikasi crash.
        pass


# ----------------------------------------------------------------------------
# DOWNLOAD: yt-dlp dengan strategi anti-403 + retry
# ----------------------------------------------------------------------------
def build_ydl_opts(output_path: str, player_client: str, cookiefile: str | None = None) -> dict:
    """
    player_client menentukan 'penyamaran' yt-dlp: android, ios, web, mweb, dll.
    Sejak akhir 2025, yt-dlp memerlukan JavaScript runtime eksternal (Deno/Node)
    untuk memecahkan signature YouTube. Streamlit Cloud tidak punya Deno secara
    default, jadi kita arahkan ke 'node' (dipasang via packages.txt) sebagai
    runtime fallback.
    """
    opts = {
        "format": "bestvideo[ext=mp4][height<=1080]+bestaudio[ext=m4a]/best[ext=mp4]/best",
        "outtmpl": os.path.join(output_path, "%(id)s.%(ext)s"),
        "merge_output_format": "mp4",
        "noplaylist": True,
        "quiet": True,
        "no_warnings": True,
        "retries": 5,
        "fragment_retries": 5,
        "concurrent_fragment_downloads": 1,  # hindari pola request paralel yang memicu rate-limit
        "sleep_interval_requests": 1,        # jeda antar request metadata
        "sleep_interval": 1,                 # jeda antar fragment/percobaan
        "max_sleep_interval": 5,
        "js_runtimes": {"node": {}},  # format harus dict: {runtime: {config}}; Deno tak ada di Streamlit Cloud
        "remote_components": ["ejs:github"],  # fallback unduh solver EJS jika komponen lokal tak lengkap
        "extractor_args": {
            "youtube": {
                "player_client": [player_client],
            }
        },
        "http_headers": {
            # User-Agent generik; player_client di atas yang menentukan
            # endpoint player YouTube yang dipakai, bukan header ini.
            "User-Agent": "Mozilla/5.0 (Linux; Android 13; Pixel 7) AppleWebKit/537.36 "
                          "(KHTML, like Gecko) Chrome/120.0 Mobile Safari/537.36",
        },
    }
    if cookiefile and os.path.exists(cookiefile):
        opts["cookiefile"] = cookiefile
    return opts


def download_video(url: str, output_dir: str, status_placeholder, cookiefile: str | None = None) -> str:
    """
    Coba beberapa 'player_client' secara berurutan. Jika satu client
    terkena 403 / error ekstraksi, otomatis lanjut ke client berikutnya.
    Mengembalikan path file video yang berhasil diunduh.
    """
    # Urutan ini dipilih berdasarkan laporan komunitas yt-dlp per awal 2026:
    # mweb dan android sering masih berfungsi saat client 'web' biasa diblokir.
    clients_to_try = ["mweb", "android", "ios", "web", "tv_embedded"]
    last_error = None

    for attempt, client in enumerate(clients_to_try, start=1):
        try:
            status_placeholder.info(
                f"🔄 Mencoba mengunduh (mode client: **{client}**) — percobaan {attempt}/{len(clients_to_try)}..."
            )
            ydl_opts = build_ydl_opts(output_dir, client, cookiefile)

            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=True)
                filename = ydl.prepare_filename(info)

                # Karena merge_output_format=mp4, pastikan ekstensi akhir benar.
                base, _ = os.path.splitext(filename)
                mp4_path = base + ".mp4"
                final_path = mp4_path if os.path.exists(mp4_path) else filename

                if os.path.exists(final_path):
                    status_placeholder.success(f"✅ Berhasil diunduh menggunakan client '{client}'.")
                    return final_path

        except yt_dlp.utils.DownloadError as e:
            last_error = e
            msg = str(e).lower()
            if "403" in msg or "forbidden" in msg:
                status_placeholder.warning(
                    f"⚠️ Client '{client}' terkena 403 Forbidden, mencoba client lain..."
                )
            elif "sign in" in msg or "login" in msg or "cookies" in msg:
                # Beberapa video memerlukan login (age-restricted / private).
                raise RuntimeError(
                    "Video ini memerlukan login YouTube (mungkin dibatasi usia atau privat). "
                    "Coba video lain, atau sediakan cookies.txt jika ini video milik Anda sendiri."
                ) from e
            else:
                status_placeholder.warning(f"⚠️ Client '{client}' gagal: {e}. Mencoba client lain...")
            # Jeda kecil sebelum mencoba client berikutnya agar tidak memicu rate-limit.
            time.sleep(2)
            continue
        except Exception as e:
            last_error = e
            status_placeholder.warning(f"⚠️ Client '{client}' mengalami error tak terduga: {e}")
            time.sleep(2)
            continue

    # Semua client gagal.
    raise RuntimeError(
        "Gagal mengunduh video setelah mencoba semua mode client "
        f"({', '.join(clients_to_try)}). Penyebab terakhir: {last_error}\n\n"
        "Jika ini terjadi pada SEMUA video tanpa terkecuali, kemungkinan besar "
        "penyebabnya bukan video itu sendiri, melainkan alamat IP server Streamlit "
        "Cloud sedang dibatasi oleh YouTube (hal ini terjadi pada banyak aplikasi "
        "yang berjalan di infrastruktur cloud publik). Coba lagi beberapa saat "
        "kemudian, atau pertimbangkan menjalankan aplikasi ini di server/VPS "
        "dengan IP residensial sebagai alternatif jangka panjang."
    )


# ----------------------------------------------------------------------------
# PROSES VIDEO: trim + center-crop 16:9 -> 9:16
# ----------------------------------------------------------------------------
def trim_and_crop(
    input_path: str,
    output_path: str,
    start_sec: float,
    end_sec: float,
    status_placeholder,
):
    """
    Memotong durasi [start_sec, end_sec] lalu melakukan center-crop
    ke rasio 9:16. Logika crop otomatis menyesuaikan orientasi sumber:
    - Jika video lebih lebar dari 9:16 (kasus umum 16:9), crop sisi kiri-kanan.
    - Jika video lebih sempit dari 9:16, crop sisi atas-bawah.
    """
    clip = None
    try:
        status_placeholder.info("✂️ Memotong durasi video...")
        clip = VideoFileClip(input_path)

        duration = clip.duration
        start_sec = max(0, min(start_sec, duration))
        end_sec = max(start_sec, min(end_sec, duration))

        if end_sec - start_sec < 0.5:
            raise ValueError(
                f"Durasi potongan terlalu pendek (video asli hanya {duration:.1f} detik). "
                "Sesuaikan waktu mulai/selesai."
            )

        subclip = clip.subclipped(start_sec, end_sec) if hasattr(clip, "subclipped") \
            else clip.subclip(start_sec, end_sec)

        status_placeholder.info("📐 Melakukan auto center-crop ke rasio 9:16...")

        w, h = subclip.w, subclip.h
        current_ratio = w / h

        if current_ratio > TARGET_RATIO:
            # Video terlalu lebar -> potong kiri-kanan, pertahankan tinggi penuh.
            new_w = int(h * TARGET_RATIO)
            x1 = (w - new_w) // 2
            cropped = subclip.cropped(x1=x1, y1=0, x2=x1 + new_w, y2=h) \
                if hasattr(subclip, "cropped") else subclip.crop(x1=x1, y1=0, x2=x1 + new_w, y2=h)
        else:
            # Video terlalu tinggi/sempit -> potong atas-bawah, pertahankan lebar penuh.
            new_h = int(w / TARGET_RATIO)
            y1 = (h - new_h) // 2
            cropped = subclip.cropped(x1=0, y1=y1, x2=w, y2=y1 + new_h) \
                if hasattr(subclip, "cropped") else subclip.crop(x1=0, y1=y1, x2=w, y2=y1 + new_h)

        status_placeholder.info("💾 Merender video hasil (proses ini bisa beberapa menit)...")
        cropped.write_videofile(
            output_path,
            codec="libx264",
            audio_codec="aac",
            preset="medium",
            threads=2,
            logger=None,  # matikan progress bar bawaan moviepy di terminal server
        )

    finally:
        # PENTING: tutup semua handle file agar tidak ada file lock
        # tersisa sebelum direktori temp dihapus.
        if clip is not None:
            try:
                clip.close()
            except Exception:
                pass


# ----------------------------------------------------------------------------
# UI STREAMLIT
# ----------------------------------------------------------------------------
def main():
    st.title("🎬 Auto-Clipper Tool")
    st.caption("Podcast / Berita Bola / Gaming → Klip vertikal siap upload (TikTok, Shorts, Reels)")

    with st.form("clip_form"):
        url = st.text_input("Link YouTube", placeholder="https://www.youtube.com/watch?v=...")

        col1, col2 = st.columns(2)
        with col1:
            start_min = st.number_input("Mulai (menit)", min_value=0.0, value=0.0, step=0.1)
        with col2:
            end_min = st.number_input("Selesai (menit)", min_value=0.0, value=1.0, step=0.1)

        cookiefile_upload = st.file_uploader(
            "Cookies.txt (opsional — hanya untuk video milik Anda sendiri yang age-restricted/privat)",
            type=["txt"],
        )

        submitted = st.form_submit_button("🚀 Proses Klip", use_container_width=True)

    if not submitted:
        st.info("Masukkan link YouTube dan rentang waktu, lalu klik **Proses Klip**.")
        return

    # ---- Validasi input dasar ----
    if not url or not is_valid_youtube_url(url):
        st.error("❌ Link YouTube tidak valid. Pastikan formatnya seperti `https://www.youtube.com/watch?v=...`")
        return

    if end_min <= start_min:
        st.error("❌ Waktu 'Selesai' harus lebih besar dari waktu 'Mulai'.")
        return

    if (end_min - start_min) > 10:
        st.warning("⚠️ Durasi klip lebih dari 10 menit — proses render mungkin lambat dan memakan banyak memori.")

    # ---- Direktori temp khusus sesi ini ----
    # Dibuat manual (bukan context manager) supaya bisa dibersihkan secara
    # eksplisit di blok finally, termasuk saat exception terjadi di tengah jalan.
    temp_dir = tempfile.mkdtemp(prefix="autoclipper_")
    status_placeholder = st.empty()
    progress_note = st.empty()

    cookiefile_path = None
    output_path = os.path.join(temp_dir, "clip_output.mp4")

    try:
        # Simpan cookies upload (jika ada) ke temp dir juga, biar ikut terhapus.
        if cookiefile_upload is not None:
            cookiefile_path = os.path.join(temp_dir, "cookies.txt")
            with open(cookiefile_path, "wb") as f:
                f.write(cookiefile_upload.getvalue())

        with st.spinner("Memproses video..."):
            raw_video_path = download_video(url, temp_dir, status_placeholder, cookiefile_path)

            trim_and_crop(
                input_path=raw_video_path,
                output_path=output_path,
                start_sec=start_min * 60,
                end_sec=end_min * 60,
                status_placeholder=status_placeholder,
            )

        status_placeholder.success("🎉 Klip selesai dibuat!")

        # Baca byte hasil SEBELUM direktori temp dihapus, lalu simpan di
        # session_state supaya tombol download tetap berfungsi setelah rerun,
        # tanpa perlu menyimpan file di disk lebih lama dari yang diperlukan.
        with open(output_path, "rb") as f:
            video_bytes = f.read()

        st.video(video_bytes)
        st.download_button(
            label="⬇️ Download Klip (MP4, 9:16)",
            data=video_bytes,
            file_name="clip_9x16.mp4",
            mime="video/mp4",
            use_container_width=True,
        )

    except RuntimeError as e:
        # Error yang sudah kita beri pesan ramah (403 setelah semua client, dll).
        status_placeholder.empty()
        st.error(f"❌ {e}")
        with st.expander("Detail teknis (untuk debugging)"):
            st.code(traceback.format_exc())

    except ValueError as e:
        status_placeholder.empty()
        st.error(f"❌ Input tidak valid: {e}")

    except Exception as e:
        status_placeholder.empty()
        st.error(
            "❌ Terjadi kesalahan tak terduga saat memproses video. "
            "Kemungkinan sebab: format video tidak didukung, ffmpeg gagal, "
            "atau koneksi ke YouTube terputus."
        )
        with st.expander("Detail teknis (untuk debugging)"):
            st.code(f"{type(e).__name__}: {e}\n\n{traceback.format_exc()}")

    finally:
        # ---- INI BAGIAN YANG DIMINTA: pembersihan temp storage ----
        # Dijalankan baik proses sukses maupun gagal, supaya file video
        # mentah, file hasil crop, dan cookies tidak menumpuk di server.
        cleanup_dir(temp_dir)
        progress_note.caption("🧹 File sementara di server telah dibersihkan.")


if __name__ == "__main__":
    main()
