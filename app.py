import streamlit as st
import cv2
import numpy as np
from PIL import Image
import piexif
import io
import zipfile
import tempfile
import os
from datetime import datetime, timedelta, time

# --- CONFIGURATION ---
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

# --- HELPER FUNCTIONS ---
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

def remove_image(index):
    if 0 <= index < len(st.session_state.generated_images):
        del st.session_state.generated_images[index]

# --- MAIN APP ---
if check_password():
    st.set_page_config(page_title="Video-to-SEO Photos", layout="wide")
    st.title("🏠 Job Site Video-to-Photo Tool")

    if 'generated_images' not in st.session_state:
        st.session_state.generated_images = []

    # --- SETTINGS SECTION ---
    with st.expander("🛠️ Job Settings", expanded=True):
        col1, col2 = st.columns(2)
        
        # LEFT COLUMN
        with col1:
            uploaded_video = st.file_uploader("1. Upload Video", type=['mp4', 'mov', 'avi'])
            seo_filename = st.text_input("2. SEO Keywords (Filename)", value="house-washing-service")
            
            # --- CUSTOM 12-HOUR TIME PICKER ---
            st.markdown("**Job Start Time**")
            t_c1, t_c2, t_c3 = st.columns(3)
            with t_c1:
                hour = st.selectbox("Hour", range(1, 13), index=8) # Default 9 AM
            with t_c2:
                minute = st.selectbox("Min", ["00", "05", "10", "15", "20", "25", "30", "35", "40", "45", "50", "55"])
            with t_c3:
                ampm = st.selectbox("AM/PM", ["AM", "PM"], index=0)
            
            # Convert 12h to 24h for Logic
            hour_24 = hour
            if ampm == "PM" and hour != 12:
                hour_24 += 12
            elif ampm == "AM" and hour == 12:
                hour_24 = 0
            
            # Create the time object
            time_input = time(hour_24, int(minute))
        
        # RIGHT COLUMN
        with col2:
            loc_mode = st.radio("Location:", ["Preset", "Manual"], horizontal=True)
            if loc_mode == "Preset":
                sel_loc = st.selectbox("Select Area", list(PRESET_LOCATIONS.keys()))
                lat_input, lng_input = PRESET_LOCATIONS[sel_loc]
            else:
                c_a, c_b = st.columns(2)
                lat_input = c_a.number_input("Lat", value=38.8126, format="%.6f")
                lng_input = c_b.number_input("Lng", value=-90.8554, format="%.6f")
            
            date_input = st.date_input("Date", datetime.now())

    # --- PROCESS BUTTON ---
    if uploaded_video is not None:
        if st.button("🚀 Process Video & Generate Previews", type="primary"):
            st.session_state.generated_images = []
            
            with st.spinner("Extracting frames..."):
                tfile = tempfile.NamedTemporaryFile(delete=False, suffix='.mp4')
                tfile.write(uploaded_video.read())
                tfile.close()
                
                cap = cv2.VideoCapture(tfile.name)
                total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
                
                if total_frames > 0:
                    frame_indices = np.linspace(0, total_frames - 1, 10, dtype=int)
                    base_dt = datetime.combine(date_input, time_input)
                    
                    for i, idx in enumerate(frame_indices):
                        cap.set(cv2.CAP_PROP_POS_FRAMES, idx)
                        ret, frame = cap.read()
                        if ret:
                            # Process Image
                            rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                            pil_img = Image.fromarray(rgb_frame)
                            img_byte_arr = io.BytesIO()
                            pil_img.save(img_byte_arr, format='JPEG', quality=95)
                            
                            # Add time drift (5 mins per photo)
                            current_photo_time = base_dt + timedelta(minutes=i*5)
                            
                            # Inject Metadata
                            final_bytes = set_image_metadata(img_byte_arr.getvalue(), lat_input, lng_input, current_photo_time)
                            
                            # Naming
                            if i == 0: suffix = "before"
                            elif i == 9: suffix = "after"
                            else: suffix = f"action-{i}"
                            filename = f"{seo_filename.replace(' ', '-').lower()}-{i+1:02d}-{suffix}.jpg"
                            
                            st.session_state.generated_images.append({
                                "name": filename,
                                "data": final_bytes,
                                "preview": pil_img,
                                "key": f"img_{i}_{int(datetime.now().timestamp())}" # Unique key for buttons
                            })
                    
                cap.release()
                os.unlink(tfile.name)
            st.rerun()

    # --- REVIEW GALLERY ---
    if len(st.session_state.generated_images) > 0:
        st.divider()
        st.subheader(f"📸 Review Photos ({len(st.session_state.generated_images)} remaining)")
        
        # Grid Layout
        cols = st.columns(3)
        for i, img_obj in enumerate(st.session_state.generated_images):
            col = cols[i % 3]
            with col:
                st.image(img_obj["preview"], caption=img_obj["name"], width='stretch')
                if st.button(f"🗑️ Discard", key=img_obj["key"]):
                    remove_image(i)
                    st.rerun()

        st.divider()

        # --- FINAL DOWNLOAD ---
        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, "w") as zf:
            for img_obj in st.session_state.generated_images:
                zf.writestr(img_obj["name"], img_obj["data"])
        
        st.download_button(
            label=f"📥 Download {len(st.session_state.generated_images)} Photos (ZIP)",
            data=zip_buffer.getvalue(),
            file_name=f"{seo_filename}-final-set.zip",
            mime="application/zip",
            type="primary"
        )
