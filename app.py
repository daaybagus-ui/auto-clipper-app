import streamlit as st
import os
import subprocess

# Menginstal moviepy secara paksa melalui kode (jika gagal di requirements)
try:
    from moviepy.editor import VideoFileClip
except ImportError:
    subprocess.check_call(["pip", "install", "moviepy"])
    from moviepy.editor import VideoFileClip

st.title("✂️ Auto-Clipper")

uploaded_file = st.file_uploader("Upload Video", type=["mp4"])

if uploaded_file is not None:
    with open("temp_video.mp4", "wb") as f:
        f.write(uploaded_file.getbuffer())
    
    st.video("temp_video.mp4")
    
    if st.button("Proses"):
        try:
            st.info("Sedang memproses...")
            video = VideoFileClip("temp_video.mp4")
            final_clip = video.subclip(0, 5) # 5 detik pertama
            final_clip.write_videofile("hasil.mp4", codec="libx264")
            st.video("hasil.mp4")
            video.close()
        except Exception as e:
            st.error(f"Error: {e}")
