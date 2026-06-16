import streamlit as st
import yt_dlp
from moviepy.editor import VideoFileClip
import os

st.set_page_config(page_title="Auto-Clipper Shorts", page_icon="✂️")

st.title("✂️ YouTube to Shorts Auto-Clipper")
st.write("Aplikasi sederhana untuk memotong video YouTube (Podcast/Game/Bola) menjadi format Vertikal (9:16).")

url = st.text_input("🔗 Masukkan Link YouTube:")
col1, col2 = st.columns(2)
with col1:
    start_time = st.number_input("⏱️ Mulai dari detik ke:", min_value=0, value=60)
with col2:
    duration = st.number_input("⏳ Durasi Clip (detik):", min_value=5, max_value=120, value=30)

if st.button("🚀 Buat Video Pendek!"):
    if url:
        with st.spinner("⬇️ Mengunduh video (Mencoba jalur khusus iOS)..."):
            
            # Konfigurasi Trik iOS & IPv4
            ydl_opts = {
                'format': 'best',
                'outtmpl': 'temp_video.mp4',
                'quiet': True,
                'nocheckcertificate': True,
                'force_ipv4': True,
                'extractor_args': {'youtube': {'player_client': ['ios']}}
            }
            
            try:
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    ydl.download([url])
                st.success("✅ Download Selesai! Memulai proses editing...")

                with st.spinner("✂️ Memotong ke Vertikal (9:16)..."):
                    clip = VideoFileClip("temp_video.mp4")
                    
                    if start_time + duration > clip.duration:
                        end_time = clip.duration
                    else:
                        end_time = start_time + duration

                    subclip = clip.subclip(start_time, end_time)

                    w, h = subclip.size
                    target_w = h * 9 / 16
                    x_center = w / 2
                    
                    cropped_clip = subclip.crop(x1=x_center - target_w/2, y1=0, x2=x_center + target_w/2, y2=h)

                    output_name = "hasil_shorts.mp4"
                    cropped_clip.write_videofile(output_name, codec="libx264", audio_codec="aac", fps=30, preset="ultrafast")

                st.success("🎉 Video berhasil dibuat!")
                st.video(output_name)
                
                with open(output_name, "rb") as file:
                    st.download_button(
                        label="📥 Download Video",
                        data=file,
                        file_name="auto_clip_shorts.mp4",
                        mime="video/mp4"
                    )

                clip.close()
                subclip.close()
                cropped_clip.close()
                if os.path.exists("temp_video.mp4"):
                    os.remove("temp_video.mp4")

            except Exception as e:
                st.error(f"❌ ERROR: {e}")
    else:
        st.warning("⚠️ Harap masukkan link YouTube!")
