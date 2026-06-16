import streamlit as st
import librosa
import numpy as np
import os
from moviepy import VideoFileClip # Perhatikan: Tidak pakai .editor

st.set_page_config(page_title="AI Auto Clipper", page_icon="✂️")
st.title("✂️ AI Auto-Clipper Bola & Game")

uploaded_file = st.file_uploader("Upload Video (MP4)", type=["mp4"])

if uploaded_file is not None:
    with open("temp_video.mp4", "wb") as f:
        f.write(uploaded_file.getbuffer())
    
    st.video("temp_video.mp4")
    
    if st.button("Mulai Auto-Clip! 🚀"):
        try:
            # Load video
            video = VideoFileClip("temp_video.mp4")
            
            # Deteksi audio sederhana (menggunakan durasi video sebagai sampel)
            st.info("Memproses klip...")
            
            # Contoh potong 5 detik pertama
            final_clip = video.subclipped(0, 5)
            
            final_clip.write_videofile("hasil_clip.mp4", codec="libx264", audio_codec="aac")
            
            st.video("hasil_clip.mp4")
            video.close()
        except Exception as e:
            st.error(f"Error: {e}")
