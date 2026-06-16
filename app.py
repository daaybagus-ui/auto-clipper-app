import streamlit as st
import yt_dlp
from moviepy.editor import VideoFileClip
import os

st.set_page_config(page_title="Auto-Clipper Shorts", page_icon="✂️")

st.title("✂️ YouTube to Shorts Auto-Clipper")
st.write("Aplikasi sederhana untuk memotong video YouTube (Podcast/Game/Bola) menjadi format Vertikal (9:16).")

# 1. Input dari User
url = st.text_input("🔗 Masukkan Link YouTube:")
col1, col2 = st.columns(2)
with col1:
    start_time = st.number_input("⏱️ Mulai dari detik ke:", min_value=0, value=60)
with col2:
    duration = st.number_input("⏳ Durasi Clip (detik):", min_value=5, max_value=120, value=30)

if st.button("🚀 Buat Video Pendek!"):
    if url:
        with st.spinner("⬇️ Mengunduh video dari YouTube... (Mungkin butuh beberapa saat)"):
            ydl_opts = {
                'format': 'bestvideo[height<=1080][ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]',
                'outtmpl': 'temp_video.%(ext)s',
                'merge_output_format': 'mp4',
                'quiet': True
            }
            
            try:
                # Proses Download
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    ydl.download([url])
                st.success("✅ Download Selesai! Memulai proses editing...")

                with st.spinner("✂️ Memotong dan menyesuaikan ukuran menjadi Vertikal (9:16)..."):
                    # Load video
                    clip = VideoFileClip("temp_video.mp4")
                    
                    if start_time + duration > clip.duration:
                        st.warning("Durasi melebihi panjang video. Dipotong sampai akhir video saja.")
                        end_time = clip.duration
                    else:
                        end_time = start_time + duration

                    # Potong video berdasarkan waktu
                    subclip = clip.subclip(start_time, end_time)

                    # Logika Auto-Crop Center (Mengubah Landscape 16:9 jadi Portrait 9:16)
                    w, h = subclip.size
                    target_w = h * 9 / 16
                    x_center = w / 2
                    
                    # Proses Crop
                    cropped_clip = subclip.crop(x1=x_center - target_w/2, y1=0, x2=x_center + target_w/2, y2=h)

                    # Render hasil akhir
                    output_name = "hasil_shorts.mp4"
                    cropped_clip.write_videofile(output_name, codec="libx264", audio_codec="aac", fps=30, preset="ultrafast")

                # Tampilkan hasil di Website
                st.success("🎉 Video berhasil dibuat!")
                st.video(output_name)
                
                # Tombol Download
                with open(output_name, "rb") as file:
                    st.download_button(
                        label="📥 Download Video Hasil Clip",
                        data=file,
                        file_name="auto_clip_shorts.mp4",
                        mime="video/mp4"
                    )

                # Bersihkan file temporary
                clip.close()
                subclip.close()
                cropped_clip.close()
                os.remove("temp_video.mp4")

            except Exception as e:
                st.error(f"❌ Terjadi kesalahan: {e}")
    else:
        st.warning("⚠️ Harap masukkan link YouTube terlebih dahulu!")
