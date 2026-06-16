# app.py
# GitHub Copilot Chat Assistant
import os
import sys
import logging
import tempfile
import shutil
from pathlib import Path
from typing import Optional

import streamlit as st
import yt_dlp
from moviepy.editor import VideoFileClip
from moviepy.video.fx.all import crop

# Configure logging
logging.basicConfig(stream=sys.stdout, level=logging.INFO, format="%(asctime)s %(levelname)s: %(message)s")
logger = logging.getLogger("autoclipper")

# ----------
# Helpers
# ----------
def parse_time_to_seconds(t: str) -> int:
    """Parse hh:mm:ss, mm:ss, or seconds -> int seconds"""
    if not t:
        return 0
    parts = t.split(":")
    parts = [int(p) for p in parts]
    if len(parts) == 1:
        return parts[0]
    elif len(parts) == 2:
        return parts[0] * 60 + parts[1]
    elif len(parts) == 3:
        return parts[0] * 3600 + parts[1] * 60 + parts[2]
    else:
        raise ValueError("Format waktu tidak dikenali")

def center_crop_to_aspect(clip: VideoFileClip, target_aspect: float):
    """Center-crop clip to target_aspect (width/height). Returns cropped clip."""
    w, h = clip.size
    current_aspect = w / h
    if abs(current_aspect - target_aspect) < 1e-6:
        return clip  # already correct
    # If current is wider than needed -> crop width
    if current_aspect > target_aspect:
        # new width based on full height
        new_w = int(h * target_aspect)
        x_center = w / 2
        y_center = h / 2
        return crop(clip, x_center=x_center, y_center=y_center, width=new_w, height=h)
    else:
        # current is taller -> crop height
        new_h = int(w / target_aspect)
        x_center = w / 2
        y_center = h / 2
        return crop(clip, x_center=x_center, y_center=y_center, width=w, height=new_h)

# ----------
# YT-DLP download with progress
# ----------
class YTDLPDownloader:
    def __init__(self, temp_dir: str, progress_callback=None):
        self.temp_dir = temp_dir
        self.progress_callback = progress_callback

    def _make_ydl_opts(self, outtmpl):
        # User-Agent set to mimic Android mobile client; also add Referer
        # You can switch to an iOS UA if desired.
        android_ua = "Mozilla/5.0 (Linux; Android 10; SM-G975F) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0 Mobile Safari/537.36"
        opts = {
            "format": "bestvideo[ext=mp4]+bestaudio[ext=m4a]/best",
            "outtmpl": outtmpl,
            "noplaylist": True,
            "merge_output_format": "mp4",
            "no_warnings": True,
            "quiet": True,
            "skip_download": False,
            "retries": 3,
            # throttle helpers to reduce rate-limiting risk
            "sleep_interval_requests": 0.5,
            "max_sleep_interval_requests": 2.0,
            "http_headers": {
                "User-Agent": android_ua,
                "Referer": "https://m.youtube.com/",
            },
            # avoid fatal on minor errors so we can present friendly message
            "ignoreerrors": False,
            # progress hook
            "progress_hooks": [self._progress_hook] if self.progress_callback else [],
        }
        return opts

    def _progress_hook(self, d):
        try:
            if d.get("status") == "downloading":
                # percent string like "12.3%"
                p = d.get("_percent_str", "").strip()
                speed = d.get("_speed_str", "")
                eta = d.get("_eta_str", "")
                # call callback with structured info
                if self.progress_callback:
                    self.progress_callback(status="downloading", percent=p, speed=speed, eta=eta)
            elif d.get("status") == "finished":
                if self.progress_callback:
                    self.progress_callback(status="finished", filename=d.get("filename"))
        except Exception:
            logger.exception("progress_hook failed")

    def fetch_info(self, url: str):
        """Get metadata (no download)"""
        outtmpl = os.path.join(self.temp_dir, "%(id)s.%(ext)s")
        opts = self._make_ydl_opts(outtmpl)
        opts["skip_download"] = True
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(url, download=False)
            return info

    def download(self, url: str):
        outtmpl = os.path.join(self.temp_dir, "%(id)s.%(ext)s")
        opts = self._make_ydl_opts(outtmpl)
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(url, download=False)
            # choose best format (use same opts)
            result = ydl.extract_info(url, download=True)
            # yt-dlp returns info dict for download
            if isinstance(result, dict) and result.get("requested_formats"):
                # merged path is in result['requested_formats'] elements or 'url' - safer to search output filename
                # However progress_hook already reported filename on finished
                pass
            return result

# ----------
# Streamlit UI
# ----------
st.set_page_config(page_title="Auto-Clipper Tool", layout="centered")
st.title("Auto-Clipper Tool — YouTube → Vertical Clip (9:16)")

with st.sidebar:
    st.header("Pengaturan")
    out_width = st.selectbox("Resolusi output (lebar x tinggi)", options=["720x1280", "1080x1920"], index=1)
    out_w, out_h = map(int, out_width.split("x"))
    max_in_memory_mb = st.number_input("Max ukuran file untuk download langsung (MB)", min_value=10, max_value=1024, value=200)
    st.write("Catatan: Jika file akhir lebih besar dari nilai ini, sebaiknya gunakan storage eksternal (S3) atau batasi durasi clip.")

st.markdown("Masukkan link YouTube, tentukan waktu mulai/akhir, lalu tekan 'Proses'.")

url = st.text_input("YouTube URL", "")
start_time_input = st.text_input("Mulai (hh:mm:ss atau mm:ss atau detik)", "00:00")
end_time_input = st.text_input("Selesai (hh:mm:ss atau mm:ss atau detik). Biarkan kosong untuk memakai durasi default 15s", "")
duration_input = st.text_input("Atau masukkan durasi clip (detik) — opsi jika tidak mengisi akhir", "15")

col1, col2 = st.columns([1, 1])
with col1:
    btn_preview = st.button("Preview Info")
with col2:
    btn_process = st.button("Proses & Download")

status_placeholder = st.empty()
progress_bar = st.empty()

if not url:
    st.info("Masukkan URL YouTube terlebih dahulu.")
    st.stop()

# Use a temp dir per session/process
tmp_root = Path(tempfile.mkdtemp(prefix="autoclip_"))
logger.info("Temp dir: %s", tmp_root)

def clean_temp_dir():
    try:
        if tmp_root.exists():
            shutil.rmtree(tmp_root)
            logger.info("Temp folder %s dihapus", tmp_root)
    except Exception:
        logger.exception("Gagal menghapus temp dir")

# Preview metadata
if btn_preview:
    status_placeholder.info("Mengambil info video...")
    try:
        downloader = YTDLPDownloader(str(tmp_root))
        info = downloader.fetch_info(url)
        title = info.get("title")
        duration = info.get("duration")
        uploader = info.get("uploader")
        # filesize estimate (may be None)
        size = info.get("filesize") or info.get("filesize_approx")
        size_mb = (size / (1024 * 1024)) if size else None
        st.markdown(f"**Judul:** {title}")
        st.markdown(f"**Uploader:** {uploader}")
        st.markdown(f"**Durasi (detik):** {duration}")
        if size_mb:
            st.markdown(f"**Perkiraan ukuran:** {size_mb:.1f} MB")
        else:
            st.markdown("**Perkiraan ukuran:** Tidak tersedia (varies by format)")
        status_placeholder.success("Selesai mengambil info.")
    except yt_dlp.utils.DownloadError as e:
        logger.exception("yt-dlp error")
        status_placeholder.error(f"Terjadi kesalahan saat mengambil info: {e}. Coba lagi atau gunakan cookie/akun jika video region-locked.")
    except Exception as e:
        logger.exception("general error")
        status_placeholder.error(f"Error: {e}")

# Process (download -> crop -> export -> cleanup)
if btn_process:
    try:
        status_placeholder.info("Mulai proses...")
        # parse times
        start_s = parse_time_to_seconds(start_time_input)
        if end_time_input.strip():
            end_s = parse_time_to_seconds(end_time_input)
            if end_s <= start_s:
                raise ValueError("Waktu selesai harus lebih besar dari waktu mulai")
            clip_duration = end_s - start_s
        else:
            clip_duration = int(duration_input) if duration_input.strip() else 15

        # Create downloader with progress hook mapping to streamlit progress bar
        def progress_cb(status, percent=None, speed=None, eta=None, filename=None):
            if status == "downloading":
                text = f"Downloading... {percent} @ {speed} ETA {eta}"
                progress_bar.progress(int(float(percent.strip().replace("%", "")))) if percent and percent.strip() else None
                status_placeholder.info(text)
            elif status == "finished":
                progress_bar.progress(100)
                status_placeholder.success("Download selesai, memproses video...")

        downloader = YTDLPDownloader(str(tmp_root), progress_callback=progress_cb)

        # first fetch info to check duration & size
        info = downloader.fetch_info(url)
        vid_duration = info.get("duration")
        if vid_duration and start_s >= vid_duration:
            raise ValueError("Waktu mulai melebihi durasi video")
        if vid_duration and start_s + clip_duration > vid_duration:
            clip_duration = max(1, vid_duration - start_s)
            status_placeholder.warning(f"Durasi clip disesuaikan ke {clip_duration}s karena melebihi durasi video")

        # Download video to temp dir
        status_placeholder.info("Mengunduh video dari YouTube...")
        result = downloader.download(url)
        # find downloaded file: yt-dlp usually writes file path in 'requested_downloads' or 'filename'
        # We'll search temp dir for recent mp4
        mp4_files = list(tmp_root.glob("**/*.mp4"))
        if not mp4_files:
            # try other extensions
            mp4_files = list(tmp_root.glob("**/*.*"))
        if not mp4_files:
            raise FileNotFoundError("File hasil download tidak ditemukan di folder sementara")
        # pick largest mp4 file
        mp4_files_sorted = sorted(mp4_files, key=lambda p: p.stat().st_mtime, reverse=True)
        video_path = mp4_files_sorted[0]
        status_placeholder.info(f"File download: {video_path.name}")

        # Open with moviepy
        status_placeholder.info("Membuka file dengan moviepy...")
        clip = VideoFileClip(str(video_path))
        # Subclip (safety)
        end_s = start_s + clip_duration
        working_clip = clip.subclip(start_s, min(end_s, clip.duration))

        # Crop to 9:16 center
        status_placeholder.info("Melakukan center-crop ke rasio 9:16...")
        target_aspect = 9.0 / 16.0
        cropped = center_crop_to_aspect(working_clip, target_aspect)

        # Resize to output resolution selected
        status_placeholder.info(f"Resize ke {out_w}x{out_h}...")
        resized = cropped.resize(newsize=(out_w, out_h))

        # Export final file into temp dir
        final_name = f"{video_path.stem}_clip_{start_s}-{end_s}.mp4"
        final_path = tmp_root / final_name
        status_placeholder.info("Mengekspor video (ffmpeg sedang berjalan)...")
        # Use write_videofile with threads=1 to reduce memory spikes
        resized.write_videofile(str(final_path), codec="libx264", audio_codec="aac", threads=1, logger=None)
        status_placeholder.success("Selesai memproses video.")

        # Read final file into memory for download (watch file size)
        final_size_mb = final_path.stat().st_size / (1024 * 1024)
        if final_size_mb <= max_in_memory_mb:
            status_placeholder.info("Menyiapkan file untuk diunduh (di-memory)...")
            with open(final_path, "rb") as f:
                data = f.read()
            # Remove temp folder immediately
            clean_temp_dir()
            # Provide download button
            st.success("Video siap diunduh")
            st.download_button(label="Download Clip (MP4)", data=data, file_name=final_name, mime="video/mp4")
        else:
            # file terlalu besar untuk di-memory: simpan sementara dan tawarkan path info
            st.warning(f"File akhir {final_size_mb:.1f} MB lebih besar dari batas {max_in_memory_mb} MB.")
            st.info(f"File tersimpan sementara di server: {final_path}")
            st.markdown("Sebaiknya upload file besar ke storage eksternal (S3/GCS) dalam workflow produksi. Untuk sekarang, Anda bisa mendownload melalui file browser Streamlit jika diizinkan.")
            # Do not delete temp dir automatically in this case — show manual cleanup button
            if st.button("Hapus file sementara sekarang"):
                clean_temp_dir()
                st.success("File sementara dihapus.")

        # cleanup moviepy clips
        try:
            clip.close()
            working_clip.close()
            cropped.close()
            resized.close()
        except Exception:
            pass

    except yt_dlp.utils.DownloadError as e:
        logger.exception("Download error")
        status_placeholder.error(f"Download gagal: {e}. Coba ulang, gunakan cookies (login) atau proxy jika video dibatasi region.")
        clean_temp_dir()
    except FileNotFoundError as e:
        logger.exception("File not found")
        status_placeholder.error(f"File tidak ditemukan: {e}")
        clean_temp_dir()
    except Exception as e:
        logger.exception("Processing failed")
        status_placeholder.error(f"Terjadi kesalahan: {e}")
        clean_temp_dir()