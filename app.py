import streamlit as st
import yt_dlp
from moviepy.editor import VideoFileClip
import os
import re

# Konfigurasi Halaman Streamlit
st.set_page_config(page_title="Video Clipper Tool", page_icon="✂️", layout="centered")

st.title("✂️ Video Clipper Tool")
st.write("Unduh dan potong video dari berbagai platform seperti YouTube, Reddit, dan lainnya tanpa terkendala Error 403.")

# Fungsi untuk membersihkan URL secara otomatis dari tracking parameter (?si=...)
def clean_url(url_string):
    if "youtube.com" in url_string or "youtu.be" in url_string:
        # Menghapus parameter ?si= atau &si= beserta value di belakangnya
        cleaned = re.sub(r'\?si=[a-zA-Z0-9_-]+', '', url_string)
        cleaned = re.sub(r'&si=[a-zA-Z0-9_-]+', '', cleaned)
        return cleaned
    return url_string

# Input dari pengguna
raw_url = st.text_input("🔗 Masukkan URL Video:", placeholder="https://youtu.be/...")

col1, col2 = st.columns(2)
with col1:
    start_time = st.number_input("Mulai (detik):", min_value=0, value=0, step=1)
with col2:
    end_time = st.number_input("Selesai (detik):", min_value=1, value=10, step=1)

# Tombol proses
if st.button("Proses Video", type="primary"):
    if not raw_url:
        st.warning("Mohon masukkan URL video terlebih dahulu.")
    elif start_time >= end_time:
        st.error("Waktu selesai harus lebih besar dari waktu mulai.")
    else:
        # Bersihkan URL sebelum diproses oleh yt-dlp
        url = clean_url(raw_url.strip())
        
        with st.spinner("Sedang mengunduh dan memotong video... (Proses ini memakan waktu beberapa saat)"):
            try:
                # Menentukan nama file sementara di server
                raw_file = "temp_video.mp4"
                clipped_file = "final_video.mp4"

                # Hapus sisa file lama jika ada agar penyimpanan server tidak penuh
                if os.path.exists(raw_file): 
                    try: os.remove(raw_file)
                    except: pass
                if os.path.exists(clipped_file): 
                    try: os.remove(clipped_file)
                    except: pass

                # 1. Konfigurasi yt-dlp yang diperbarui untuk mengatasi HTTP Error 403 (Forbidden)
                ydl_opts = {
                    'format': 'best[ext=mp4]/best',  # Mengutamakan format MP4 gabungan video & audio terbaik
                    'outtmpl': raw_file,
                    'quiet': True,
                    'noplaylist': True,
                    'nocheckcertificate': True,      # Mengabaikan masalah verifikasi sertifikat SSL tertentu
                    'extractor_args': {
                        'youtube': ['player_client=ios,android,web']  # Menyamarkan request sebagai aplikasi mobile resmi
                    },
                    'http_headers': {
                        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
                        'Accept-Language': 'en-US,en;q=0.9',
                    }
                }

                # Mulai mengunduh video mentah
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    ydl.download([url])

                # Pastikan file mentah berhasil diunduh sebelum memotong
                if not os.path.exists(raw_file):
                    raise FileNotFoundError("Gagal mengambil file video mentah. Server memblokir unduhan.")

                # 2. Proses pemotongan sub-klip menggunakan moviepy
                clip = VideoFileClip(raw_file).subclip(start_time, end_time)
                
                # Menyimpan hasil potongan dengan codec standar yang kompatibel di semua browser
                clip.write_videofile(
                    clipped_file, 
                    codec="libx264", 
                    audio_codec="aac", 
                    logger=None,
                    temp_audiofile='temp-audio.m4a',
                    remove_temp=True
                )
                clip.close()

                # 3. Menampilkan hasil akhir di layar aplikasi Streamlit
                st.success("✅ Video berhasil dipotong!")
                st.video(clipped_file)

                # Menyediakan tombol download untuk pengguna
                with open(clipped_file, "rb") as file:
                    st.download_button(
                        label="⬇️ Download Video Hasil Potongan",
                        data=file,
                        file_name="video_potongan.mp4",
                        mime="video/mp4"
                    )

            except Exception as e:
                st.error("❌ Terjadi kesalahan saat memproses video.")
                st.info(f"**Detail Error:** {e}")
                st.write("💡 *Tips:* Jika error berlanjut, klik menu tiga titik `⋮` di pojok kanan atas Streamlit -> Pilih *Manage App* -> Pilih *Reboot App* untuk menyegarkan koneksi IP server.")