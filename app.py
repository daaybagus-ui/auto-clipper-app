import streamlit as st
from moviepy.editor import VideoFileClip
import os

st.title("✂️ AI Auto-Clipper")

uploaded_file = st.file_uploader("Upload Video", type=["mp4"])

if uploaded_file is not None:
    with open("temp_video.mp4", "wb") as f:
        f.write(uploaded_file.getbuffer())
    
    st.video("temp_video.mp4")
    
    if st.button("Mulai Proses"):
        try:
            video = VideoFileClip("temp_video.mp4")
            # Pemotongan sederhana 5 detik pertama
            final_clip = video.subclip(0, 5)
            final_clip.write_videofile("hasil.mp4", codec="libx264")
            st.video("hasil.mp4")
            video.close()
        except Exception as e:
            st.error(f"Error: {e}")
