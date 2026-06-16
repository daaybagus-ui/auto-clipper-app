import streamlit as st
from moviepy import VideoFileClip
import librosa
import numpy as np
import os

st.set_page_config(page_title="AI Auto Clipper", page_icon="✂️")
st.title("✂️ AI Auto-Clipper Bola & Game")

uploaded_file = st.file_uploader("Upload Video (MP4)", type=["mp4"])

if uploaded_file is not None:
    with open("temp_video.mp4", "wb") as f:
        f.write(uploaded_file.getbuffer())
    
    if st.button("Mulai Auto-Clip! 🚀"):
        try:
            video = VideoFileClip("temp_video.mp4")
            # Gunakan .subclipped untuk versi MoviePy 2.x
            # Contoh pemotongan (misal 10 detik pertama)
            final_clip = video.subclipped(0, 10) 
            
            output_filename = "hasil_clip.mp4"
            final_clip.write_videofile(output_filename, codec="libx264", audio_codec="aac")
            
            st.video(output_filename)
            video.close()
        except Exception as e:
            st.error(f"Terjadi kesalahan: {e}")
