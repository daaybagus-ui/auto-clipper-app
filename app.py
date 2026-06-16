import streamlit as st
import os
# Kita impor langsung dari moviepy, bukan dari moviepy.editor
from moviepy import VideoFileClip 

st.title("✂️ AI Auto-Clipper")

uploaded_file = st.file_uploader("Upload Video", type=["mp4"])

if uploaded_file is not None:
    with open("temp_video.mp4", "wb") as f:
        f.write(uploaded_file.getbuffer())
    
    st.video("temp_video.mp4")
    
    if st.button("Proses"):
        try:
            st.info("Sedang memproses...")
            # Panggil VideoFileClip langsung
            video = VideoFileClip("temp_video.mp4")
            
            # Gunakan .subclipped (bukan .subclip) untuk versi 2.x
            final_clip = video.subclipped(0, 5) 
            
            final_clip.write_videofile("hasil.mp4", codec="libx264", audio_codec="aac")
            st.video("hasil.mp4")
            video.close()
        except Exception as e:
            st.error(f"Error: {e}")
