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
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload

# --- GOOGLE DRIVE CONFIGURATION ---
# We will load these from Streamlit Secrets later
SCOPES = ['https://www.googleapis.com/auth/drive.file']

def upload_to_drive(zip_bytes, filename, folder_id):
    """Uploads the ZIP file to the specified Google Drive folder."""
    try:
        # Load credentials from secrets
        creds_dict = st.secrets["gcp_service_account"]
        creds = service_account.Credentials.from_service_account_info(
            creds_dict, scopes=SCOPES
        )
        service = build('drive', 'v3', credentials=creds)

        file_metadata = {
            'name': filename,
            'parents': [folder_id]
        }
        
        media = MediaIoBaseUpload(io.BytesIO(zip_bytes), mimetype='application/zip')
        
        file = service.files().create(
            body=file_metadata,
            media_body=media,
            fields='id'
        ).execute()
        
        return file.get('id')
    except Exception as e:
        st.error(f"Google Drive Error: {e}")
        return None

# --- PASSWORD AUTHENTICATION ---
def check_password():
    def password_entered():
        if st.session_state["password"] == st.secrets["password"]:
            st.session_state["password_correct"] = True
            del st.session_state["password"]
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
    
    # --- LOCATIONS ---
    PRESET_LOCATIONS = {
        "Headquarters (Default)": (38.9517, -92.3341),
        "North Side": (38.9800, -92.3000),
        "South Side": (38.9000, -92.3500),
        "West End": (38.9300, -92.4000),
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
        
        # --- NEW: GOOGLE DRIVE OPTION ---
        st.subheader("Cloud Backup")
        use_drive = st.checkbox("Upload to Google Drive")
        # You can hardcode this ID here or put it in secrets. 
        # For simplicity, we will assume you put it in secrets, or paste it here.
        drive_folder_id = st.secrets["drive_folder_id"] 
        
        st.divider()
        location_mode = st.radio("Location Method:", ["Select from Preset", "Enter Manually"])
        if location_mode == "Select from Preset":
            selected_loc_name = st.selectbox("Area", list(PRESET_LOCATIONS.keys()))
            lat_input, lng_input = PRESET_LOCATIONS[selected_loc_name]
        else:
            lat_input = st.number_input("Lat", value=38.9517, format="%.6f")
            lng_input = st.number_input("Lng", value=-92.3341, format="%.6f")
        
        date_input = st.date_input("Date", datetime.now())
        time_input = st.time_input("Start Time", datetime.now())

    with col2:
        st.header("2. Process")
        if uploaded_video is not None:
            tfile = tempfile.NamedTemporaryFile(delete=False, suffix='.mp4')
            tfile.write(uploaded_video.read())
            tfile.close()
            
            cap = cv2.VideoCapture(tfile.name)
            total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
            
            if total_frames > 0:
                if st.button("Generate & Process", type="primary"):
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
                            
                            current_photo_time = base_dt + timedelta(minutes=i*5)
                            final_bytes = set_image_metadata(img_byte_arr.getvalue(), lat_input, lng_input, current_photo_time)
                            
                            if i == 0: suffix = "before"
                            elif i == 9: suffix = "after"
                            else: suffix = f"action-{i}"
                            filename = f"{seo_filename.replace(' ', '-').lower()}-{i+1:02d}-{suffix}.jpg"
                            
                            processed_images.append((filename, final_bytes))
                        progress_bar.progress((i + 1) / 10)
                    
                    # Zip
                    zip_buffer = io.BytesIO()
                    with zipfile.ZipFile(zip_buffer, "w") as zf:
                        for fname, data in processed_images:
                            zf.writestr(fname, data)
                    
                    zip_name = f"{seo_filename}-photos.zip"
                    
                    # --- DRIVE UPLOAD ---
                    if use_drive:
                        with st.spinner("Uploading to Google Drive..."):
                            file_id = upload_to_drive(zip_buffer.getvalue(), zip_name, drive_folder_id)
                            if file_id:
                                st.success(f"✅ Uploaded to Drive! (ID: {file_id})")
                    
                    st.download_button(
                        label="Download Photos (ZIP)",
                        data=zip_buffer.getvalue(),
                        file_name=zip_name,
                        mime="application/zip",
                        type="primary"
                    )
            cap.release()
            try:
                os.unlink(tfile.name)
            except:
                pass
