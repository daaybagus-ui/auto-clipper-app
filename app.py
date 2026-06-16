import streamlit as st
import tempfile
import shutil
import os
from pathlib import Path

from yt_dlp import YoutubeDL
from moviepy import VideoFileClip

st.set_page_config(
    page_title="Auto Clipper Tool",
    page_icon="🎬",
    layout="centered"
)

st.title("🎬 Auto Clipper Tool")
st.caption("YouTube → Clip → Auto Crop 9:16")

# ---------------------------------------------------
# UTILITIES
# ---------------------------------------------------

def cleanup_directory(temp_dir):
    try:
        if temp_dir and os.path.exists(temp_dir):
            shutil.rmtree(temp_dir, ignore_errors=True)
    except Exception:
        pass


def center_crop_to_vertical(video):
    """
    Crop center menjadi format 9:16
    """
    w, h = video.size

    target_ratio = 9 / 16
    current_ratio = w / h

    if current_ratio > target_ratio:
        new_width = int(h * target_ratio)

        x1 = (w - new_width) // 2
        x2 = x1 + new_width

        video = video.cropped(
            x1=x1,
            y1=0,
            x2=x2,
            y2=h
        )

    return video


def download_video(url, output_dir):

    ydl_opts = {
        "format": "bestvideo+bestaudio/best",
        "outtmpl": f"{output_dir}/%(title)s.%(ext)s",
        "merge_output_format": "mp4",
        "quiet": True,
        "noplaylist": True
    }

    with YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=True)
        filename = ydl.prepare_filename(info)

    path = Path(filename)

    if path.suffix != ".mp4":
        mp4_file = list(Path(output_dir).glob("*.mp4"))
        if mp4_file:
            return str(mp4_file[0])

    return str(path)


# ---------------------------------------------------
# UI
# ---------------------------------------------------

youtube_url = st.text_input(
    "YouTube URL",
    placeholder="https://youtube.com/watch?v=..."
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

if st.button("🚀 Generate Clip"):

    if not youtube_url:
        st.error("Masukkan URL terlebih dahulu.")
        st.stop()

    temp_dir = tempfile.mkdtemp()

    try:

        with st.spinner("Mengunduh video..."):
            video_path = download_video(
                youtube_url,
                temp_dir
            )

        st.success("Video berhasil diunduh")

        output_path = os.path.join(
            temp_dir,
            "clip_vertical.mp4"
        )

        with st.spinner("Memproses video..."):

            video = VideoFileClip(video_path)

            end_time = min(
                start_time + duration,
                video.duration
            )

            clip = video.subclipped(
                start_time,
                end_time
            )

            clip = center_crop_to_vertical(clip)

            clip.write_videofile(
                output_path,
                codec="libx264",
                audio_codec="aac",
                threads=2,
                logger=None
            )

            video.close()
            clip.close()

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

        error_text = str(e)

        if "ffmpeg" in error_text.lower():
            st.error(
                "FFmpeg tidak ditemukan. "
                "Pastikan packages.txt telah berisi ffmpeg."
            )

        elif "403" in error_text:
            st.error(
                "Video tidak dapat diakses. "
                "Coba video lain atau periksa izin akses."
            )

        else:
            st.error(
                f"Terjadi kesalahan:\n{error_text}"
            )

    finally:

        cleanup_directory(temp_dir)