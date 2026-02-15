import streamlit as st
import cv2
import numpy as np
from PIL import Image
import piexif
import io
import zipfile
import tempfile
import os
from datetime import datetime, timedelta

# --- PASSWORD AUTHENTICATION ---
def check_password():
    """Returns `True` if the user had the correct password."""
    def password_entered():
        if st.session_state["password"] == st.secrets["password"]:
            st.session_state["password_correct"] = True
            del st.session_state["password"]  # don't store password
        else:
            st.session_state["password_correct"] = False

    if "password_correct" not in st.session_state:
        st.text_input("Enter Password", type="password", on_change=password_entered, key="password")
        return False
    elif not st.session_state["password_correct"]:
        st.text_input("Enter Password", type="password", on_change=password_entered, key="password")
        st.error("😕 Password incorrect")
        return False
    else:
        return True

if check_password():
    # --- YOUR APP STARTS HERE ---
    
    # --- CONFIGURATION: EDIT YOUR LOCATIONS HERE ---
    PRESET_LOCATIONS = {
        "Wentzville (Default)": (38.8126, -90.8554),
        "O'Fallon, MO": (38.8106, -90.6998),
        "Chesterfield, MO": (38.6631, -90.5771),
        "St. Charles, MO": (38.7881, -90.4882),
        "Town and Country, MO": (38.6465, -90.4548),
        "Lake St. Louis, MO": (38.7909, -90.7854),
        "Wildwood, MO": (38.5828, -90.6629),
        "St. Peters, MO": (38.7998, -90.6265),
        "Ballwin, MO": (38.5937, -90.5476),
        "Cottleville, MO": (38.7467, -90.6479),
        "Dardenne Prairie, MO": (38.7928, -90.7282),
        "Ellisville, MO": (38.5931, -90.5901),
        "Manchester, MO": (38.5912, -90.5054),
        "Des Peres, MO": (38.6012, -90.4287),
        "Weldon Spring, MO": (38.7126, -90.6865),
        "Clarkson Valley, MO": (38.6384, -90.6054),
        "Troy, MO": (38.9792, -90.9807),
        "Warrenton, MO": (38.8131, -91.1399),
        "Foristell, MO": (38.8170, -90.9387),
        "St. Charles County, MO": (38.7842, -90.6798),
        "Columbia, MO": (38.9517, -92.3341),
    }

    def to_deg(value, loc):
        if value < 0: loc_value = loc[1]
        else: loc_value = loc[0]
        abs_value = abs(value)
        deg = int(abs_value)
        t1 = (abs_value - deg) * 60
        min = int(t1)
        sec = round((t1 - min) * 60, 10000)
        return (deg, 1), (min, 1), (int(sec * 10000), 10000), loc_value

    def set_image_metadata(image_bytes, lat, lng, date_time):
        exif_dict = {"0th": {}, "Exif": {}, "GPS": {}, "1st": {}, "thumbnail": None}
        if date_time:
            dt_str = date_time.strftime("%Y:%m:%d %H:%M:%S")
            exif_dict["0th"][piexif.ImageIFD.DateTime] = dt_str
            exif_dict["Exif"][piexif.ExifIFD.DateTimeOriginal] = dt_str
            exif_dict["Exif"][piexif.ExifIFD.DateTimeDigitized] = dt_str
        if lat is not None and lng is not None:
            lat_deg = to_deg(lat, ["N", "S"])
            lng_deg = to_deg(lng, ["E", "W"])
            exif_dict["GPS"][piexif.GPSIFD.GPSLatitudeRef] = lat_deg[3]
            exif_dict["GPS"][piexif.GPSIFD.GPSLatitude] = lat_deg[0:3]
            exif_dict["GPS"][piexif.GPSIFD.GPSLongitudeRef] = lng_deg[3]
            exif_dict["GPS"][piexif.GPSIFD.GPSLongitude] = lng_deg[0:3]
        exif_bytes = piexif.dump(exif_dict)
        img = Image.open(io.BytesIO(image_bytes))
        out_bytes = io.BytesIO()
        img.save(out_bytes, format="JPEG", exif=exif_bytes)
        return out_bytes.getvalue()

    st.set_page_config(page_title="Video-to-SEO Photos", layout="wide")
    st.title("🏠 Job Site Video-to-Photo Tool")

    col1, col2 = st.columns([1, 2])

    with col1:
        st.header("1. Settings")
        uploaded_video = st.file_uploader("Upload Video", type=['mp4', 'mov', 'avi'])
        st.divider()
        seo_filename = st.text_input("SEO Filename (Keywords)", value="house-washing-service")
        st.divider()
        location_mode = st.radio("Location Method:", ["Select from Preset", "Enter Manually"])
        if location_mode == "Select from Preset":
            selected_loc_name = st.selectbox("Area", list(PRESET_LOCATIONS.keys()))
            lat_input, lng_input = PRESET_LOCATIONS[selected_loc_name]
        else:
            lat_input = st.number_input("Lat", value=38.9517, format="%.6f")
            lng_input = st.number_input("Lng", value=-92.3341, format="%.6f")
        st.divider()
        date_input = st.date_input("Date", datetime.now())
        time_input = st.time_input("Start Time", datetime.now())

    with col2:
        st.header("2. Process")
        if uploaded_video is not None:
            # Create a temp file
            tfile = tempfile.NamedTemporaryFile(delete=False, suffix='.mp4')
            tfile.write(uploaded_video.read())
            tfile.close() # Close so OpenCV can open it
            
            cap = cv2.VideoCapture(tfile.name)
            total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
            
            if total_frames > 0:
                if st.button("Generate Images", type="primary"):
                    frame_indices = np.linspace(0, total_frames - 1, 10, dtype=int)
                    processed_images = []
                    progress_bar = st.progress(0)
                    base_dt = datetime.combine(date_input, time_input)
                    
                    for i, idx in enumerate(frame_indices):
                        cap.set(cv2.CAP_PROP_POS_FRAMES, idx)
                        ret, frame = cap.read()
                        if ret:
                            rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                            pil_img = Image.fromarray(rgb_frame)
                            img_byte_arr = io.BytesIO()
                            pil_img.save(img_byte_arr, format='JPEG', quality=95)
                            
                            # Time & Metadata
                            current_photo_time = base_dt + timedelta(minutes=i*5)
                            final_bytes = set_image_metadata(img_byte_arr.getvalue(), lat_input, lng_input, current_photo_time)
                            
                            # Naming
                            if i == 0: suffix = "before"
                            elif i == 9: suffix = "after"
                            else: suffix = f"action-{i}"
                            filename = f"{seo_filename.replace(' ', '-').lower()}-{i+1:02d}-{suffix}.jpg"
                            
                            processed_images.append((filename, final_bytes))
                        progress_bar.progress((i + 1) / 10)
                    
                    # Preview
                    c1, c2, c3 = st.columns(3)
                    if len(processed_images) > 9:
                        c1.image(processed_images[0][1], caption="Before")
                        c2.image(processed_images[5][1], caption="Action")
                        c3.image(processed_images[9][1], caption="After")
                    
                    # Zip
                    zip_buffer = io.BytesIO()
                    with zipfile.ZipFile(zip_buffer, "w") as zf:
                        for fname, data in processed_images:
                            zf.writestr(fname, data)
                    
                    st.download_button(
                        label="Download Photos (ZIP)",
                        data=zip_buffer.getvalue(),
                        file_name=f"{seo_filename}-photos.zip",
                        mime="application/zip",
                        type="primary"
                    )
            cap.release()
            # Clean up temp file immediately
            try:
                os.unlink(tfile.name)
            except:
                pass