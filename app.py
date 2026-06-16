import streamlit as st
import tempfile
import shutil
import os
from pathlib import Path

from yt_dlp import YoutubeDL
from moviepy import VideoFileClip

# =====================================
# CONFIG
# =====================================

st.set_page_config(
    page_title="Clipper Tool",
    page_icon="🎬",
    layout="centered"
)

st.title("🎬 Clipper Tool")
st.caption("YouTube → Clip → Auto Crop 9:16")

# =====================================
# CLEANUP
# =====================================

def cleanup_directory(path):
    try:
        if path and os.path.exists(path):
            shutil.rmtree(path, ignore_errors=True)
    except Exception:
        pass


# =====================================
# CENTER CROP 9:16
# =====================================

def center_crop_vertical(video):
    width, height = video.size

    target_ratio = 9 / 16
    current_ratio = width / height

    if current_ratio > target_ratio:

        new_width = int(height * target_ratio)

        x1 = (width - new_width) // 2
        x2 = x1 + new_width

        video = video.cropped(
            x1=x1,
            y1=0,
            x2=x2,
            y2=height
        )

    return video


# =====================================
# DOWNLOAD VIDEO
# =====================================

def download_video(url, output_dir):

    ydl_opts = {
        "format": "best[ext=mp4]/best",
        "outtmpl": f"{output_dir}/%(title)s.%(ext)s",
        "merge_output_format": "mp4",
        "quiet": False,
        "noplaylist": True,
        "nocheckcertificate": True
    }

    with YoutubeDL(ydl_opts) as ydl:

        info = ydl.extract_info(url, download=True)

        filename = ydl.prepare_filename(info)

    file_path = Path(filename)

    if file_path.exists():
        return str(file_path)

    mp4_files = list(Path(output_dir).glob("*.mp4"))

    if mp4_files:
        return str(mp4_files[0])

    raise Exception("File video tidak ditemukan setelah download.")


# =====================================
# UI
# =====================================

youtube_url = st.text_input(
    "YouTube URL",
    placeholder="https://youtube.com/watch?v=xxxx"
)

start_time = st.number_input(
    "Start (detik)",
    min_value=0,
    value=0
)

duration = st.number_input(
    "Durasi Clip (detik)",
    min_value=5,
    value=30
)

# =====================================
# PROCESS
# =====================================

if st.button("🚀 Generate Clip"):

    if not youtube_url:

        st.error("Masukkan URL terlebih dahulu.")
        st.stop()

    if (
        "youtube.com" not in youtube_url
        and
        "youtu.be" not in youtube_url
    ):
        st.error("URL bukan YouTube.")
        st.stop()

    temp_dir = tempfile.mkdtemp()

    try:

        progress = st.progress(0)

        # DOWNLOAD
        with st.spinner("Mengunduh video..."):

            progress.progress(10)

            video_path = download_video(
                youtube_url,
                temp_dir
            )

            progress.progress(40)

        st.success("Video berhasil diunduh")

        output_path = os.path.join(
            temp_dir,
            "clip_vertical.mp4"
        )

        # PROCESS VIDEO
        with st.spinner("Memproses video..."):

            video = VideoFileClip(video_path)

            end_time = min(
                start_time + duration,
                video.duration
            )

            # MoviePy v2
            clip = video.subclipped(
                start_time,
                end_time
            )

            progress.progress(60)

            clip = center_crop_vertical(clip)

            progress.progress(80)

            clip.write_videofile(
                output_path,
                codec="libx264",
                audio_codec="aac",
                threads=2,
                logger=None
            )

            clip.close()
            video.close()

            progress.progress(100)

        st.success("Clip berhasil dibuat")

        with open(output_path, "rb") as f:
            video_bytes = f.read()

        st.video(video_bytes)

        st.download_button(
            label="⬇ Download Clip",
            data=video_bytes,
            file_name="clip_vertical.mp4",
            mime="video/mp4"
        )

    except Exception as e:

        st.error("Terjadi kesalahan:")
        st.exception(e)

    finally:

        cleanup_directory(temp_dir)