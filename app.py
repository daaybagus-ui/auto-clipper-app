import streamlit as st
import yt_dlp
from moviepy.editor import VideoFileClip
import os

# Konfigurasi Halaman Streamlit
st.set_page_config(page_title="Video Clipper Tool", page_icon="✂️")
st.title("✂️ Video Clipper Tool")
st.write("Download dan potong video dari berbagai platform seperti YouTube, Reddit, dan lainnya.")

# Input dari pengguna
url = st.text_input("🔗 Masukkan URL Video:")

col1, col2 = st.columns(2)
with col1:
    start_time = st.number_input("Mulai (detik):", min_value=0, value=0)
with col2:
    end_time = st.number_input("Selesai (detik):", min_value=1, value=10)

# Tombol proses
if st.button("Proses Video"):
    if not url:
        st.warning("Mohon masukkan URL video terlebih dahulu.")
    elif start_time >= end_time:
        st.error("Waktu selesai harus lebih besar dari waktu mulai.")
    else:
        with st.spinner("Sedang mengunduh dan memotong video... (Ini memakan waktu beberapa saat)"):
            try:
                # Menentukan nama file sementara
                raw_file = "temp_video.mp4"
                clipped_file = "final_video.mp4"

                # Hapus sisa file lama jika ada agar memori server tidak penuh
                if os.path.exists(raw_file): os.remove(raw_file)
                if os.path.exists(clipped_file): os.remove(clipped_file)

                # 1. Konfigurasi yt-dlp untuk mengunduh video
                ydl_opts = {
                    'format': 'best', # Mengambil resolusi terbaik yang menyatukan audio & video
                    'outtmpl': raw_file,
                    'quiet': True,
                    'noplaylist': True
                }

                # Mulai mengunduh
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    ydl.download([url])

                # 2. Proses pemotongan menggunakan moviepy
                clip = VideoFileClip(raw_file).subclip(start_time, end_time)
                # Menyimpan hasil potongan
                clip.write_videofile(clipped_file, codec="libx264", audio_codec="aac", logger=None)
                clip.close()

                # 3. Menampilkan hasil di layar
                st.success("✅ Video berhasil dipotong!")
                st.video(clipped_file)

                # Tombol untuk mendownload hasil akhir
                with open(clipped_file, "rb") as file:
                    st.download_button(
                        label="⬇️ Download Video Hasil Potongan",
                        data=file,
                        file_name="video_potongan.mp4",
                        mime="video/mp4"
                    )

            except Exception as e:
                st.error(f"❌ Terjadi kesalahan: Pastikan URL valid atau coba video lain. Detail error: {e}")
