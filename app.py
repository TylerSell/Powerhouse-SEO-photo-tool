import streamlit as st
import piexif
from PIL import Image
import io
import random
from datetime import datetime, timedelta

# --- CONSTANTS ---

PRESET_LOCATIONS = {
    "Wentzville, MO": (38.8126, -90.8554),
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
}

SERVICES_LIST = [
    "House Wash",
    "Gutter Cleaning",
    "Window Cleaning",
    "Fence Cleaning",
    "Deck Cleaning",
    "Concrete Cleaning"
]

# --- PAGE CONFIG ---
st.set_page_config(page_title="SEO Photo Batcher", layout="wide")

# --- AUTHENTICATION ---
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

if not check_password():
    st.stop()

# --- HELPER FUNCTIONS ---

def get_random_weekday_date(start, end):
    """Generate a random datetime between start and end, excluding Weekends."""
    while True:
        delta = end - start
        int_delta = (delta.days * 24 * 60 * 60) + delta.seconds
        random_second = random.randrange(int_delta)
        res = start + timedelta(seconds=random_second)
        
        # weekday(): 0=Mon, 4=Fri, 5=Sat, 6=Sun
        if res.weekday() < 5:
            # Force business hours (8 AM to 6 PM)
            return res.replace(hour=random.randint(8, 18), minute=random.randint(0, 59))

def dec_to_dms(deg):
    """Convert decimal degrees to DMS format for EXIF."""
    d = int(deg)
    m = int((deg - d) * 60)
    s = (deg - d - m/60) * 3600 * 100
    return ((d, 1), (m, 1), (int(s), 100))

def dms_to_dec(dms_ref, dms_list):
    """Helper to convert EXIF DMS to decimal for comparison."""
    if not dms_list: return 0.0
    d = dms_list[0][0] / dms_list[0][1]
    m = dms_list[1][0] / dms_list[1][1]
    s = dms_list[2][0] / dms_list[2][1]
    decimal = d + (m / 60.0) + (s / 3600.0)
    if dms_ref in ['S', 'W']:
        decimal = -decimal
    return round(decimal, 4) # Round to 4 decimals for loose grouping

def get_original_group_key(image_bytes):
    """
    Extracts original Date and GPS to form a 'Group Key'.
    Photos with the same Key will get the same random assignment.
    """
    try:
        img = Image.open(io.BytesIO(image_bytes))
        if 'exif' not in img.info:
            return None # No EXIF, treat as unique
        
        exif_dict = piexif.load(img.info['exif'])
        
        # 1. Get Date (YYYY:MM:DD)
        date_str = exif_dict.get("Exif", {}).get(piexif.ExifIFD.DateTimeOriginal)
        if date_str:
            date_str = date_str.decode('utf-8').split(' ')[0] # Just the date part
        else:
            date_str = "NoDate"

        # 2. Get GPS
        gps = exif_dict.get("GPS", {})
        lat = 0.0
        lng = 0.0
        
        if piexif.GPSIFD.GPSLatitude in gps and piexif.GPSIFD.GPSLongitude in gps:
            lat = dms_to_dec(
                gps.get(piexif.GPSIFD.GPSLatitudeRef, b'N').decode(),
                gps.get(piexif.GPSIFD.GPSLatitude)
            )
            lng = dms_to_dec(
                gps.get(piexif.GPSIFD.GPSLongitudeRef, b'E').decode(),
                gps.get(piexif.GPSIFD.GPSLongitude)
            )
        
        # If no GPS and no Date, return None (Unique)
        if date_str == "NoDate" and lat == 0.0:
            return None
            
        return f"{date_str}_{lat}_{lng}"
        
    except Exception:
        return None

def process_single_image(image_bytes, service_name, location_data, date_obj):
    img = Image.open(io.BytesIO(image_bytes))
    
    # 1. Prepare EXIF Data
    exif_dict = {"0th": {}, "Exif": {}, "GPS": {}, "1st": {}, "thumbnail": None}
    datestr = date_obj.strftime("%Y:%m:%d %H:%M:%S")
    exif_dict["0th"][piexif.ImageIFD.DateTime] = datestr
    exif_dict["Exif"][piexif.ExifIFD.DateTimeOriginal] = datestr
    exif_dict["Exif"][piexif.ExifIFD.DateTimeDigitized] = datestr

    if location_data and location_data.get('lat'):
        lat = location_data['lat']
        lng = location_data['lng']
        exif_dict["GPS"][piexif.GPSIFD.GPSLatitudeRef] = 'N' if lat >= 0 else 'S'
        exif_dict["GPS"][piexif.GPSIFD.GPSLatitude] = dec_to_dms(abs(lat))
        exif_dict["GPS"][piexif.GPSIFD.GPSLongitudeRef] = 'E' if lng >= 0 else 'W'
        exif_dict["GPS"][piexif.GPSIFD.GPSLongitude] = dec_to_dms(abs(lng))

    try:
        exif_bytes = piexif.dump(exif_dict)
    except Exception:
        exif_bytes = None

    # 2. Save Image
    output = io.BytesIO()
    if img.mode in ("RGBA", "P"):
        img = img.convert("RGB")
        
    if exif_bytes:
        img.save(output, format="JPEG", exif=exif_bytes, quality=95)
    else:
        img.save(output, format="JPEG", quality=95)
    
    # 3. Create Clean Filename
    safe_service = "".join([c if c.isalnum() else "-" for c in service_name])
    safe_loc = "".join([c if c.isalnum() else "-" for c in location_data['name']])
    safe_date = date_obj.strftime("%m-%d-%Y")
    
    while "--" in safe_service: safe_service = safe_service.replace("--", "-")
    while "--" in safe_loc: safe_loc = safe_loc.replace("--", "-")
    
    new_filename = f"{safe_service}-{safe_loc}-{safe_date}.jpg"
    
    return new_filename, output.getvalue()

# --- MAIN APP UI ---

st.title("📸 Private SEO Photo Optimizer")
st.markdown("Features: Batch Processing, Group by Origin, Weekdays Only.")

# Sidebar Configuration
with st.sidebar:
    st.header("⚙️ Configuration")
    
    col1, col2 = st.columns(2)
    start_date = col1.date_input("Start Date", datetime.now() - timedelta(days=7))
    end_date = col2.date_input("End Date", datetime.now())
    
    default_service = st.selectbox("Default Service", SERVICES_LIST)
    
    st.info(f"Loaded {len(PRESET_LOCATIONS)} Missouri Locations.")

# File Uploader
uploaded_files = st.file_uploader("Upload Photos", accept_multiple_files=True, type=['jpg','jpeg','png'])

# Session State for assignments
if "assignments" not in st.session_state:
    st.session_state.assignments = {} # Key: filename -> data
if "group_cache" not in st.session_state:
    st.session_state.group_cache = {} # Key: origin_group_key -> {date, loc}

if uploaded_files:
    st.divider()
    
    location_list = [{"name": k, "lat": v[0], "lng": v[1]} for k, v in PRESET_LOCATIONS.items()]
    
    for uploaded_file in uploaded_files:
        file_key = f"{uploaded_file.name}_{uploaded_file.size}"
        
        # Only process if we haven't assigned this specific file yet
        if file_key not in st.session_state.assignments:
            
            # 1. Analyze Original EXIF to see if it belongs to a group
            origin_group_key = get_original_group_key(uploaded_file.getvalue())
            
            assigned_date = None
            assigned_loc = None
            
            # 2. Check if this group already has an assignment
            if origin_group_key and origin_group_key in st.session_state.group_cache:
                # Reuse the group's assignment!
                cached = st.session_state.group_cache[origin_group_key]
                assigned_date = cached['date']
                assigned_loc = cached['loc']
            else:
                # Generate NEW randoms
                assigned_date = get_random_weekday_date(
                    datetime.combine(start_date, datetime.min.time()),
                    datetime.combine(end_date, datetime.min.time())
                )
                assigned_loc = random.choice(location_list)
                
                # If this file has a valid group key, save these randoms for the next file in the group
                if origin_group_key:
                    st.session_state.group_cache[origin_group_key] = {
                        "date": assigned_date,
                        "loc": assigned_loc
                    }

            # 3. Store Final Assignment
            st.session_state.assignments[file_key] = {
                "date": assigned_date,
                "loc": assigned_loc,
                "service": default_service
            }

    # Display Gallery
    for i, uploaded_file in enumerate(uploaded_files):
        file_key = f"{uploaded_file.name}_{uploaded_file.size}"
        data = st.session_state.assignments.get(file_key)
        
        if data:
            with st.container():
                c1, c2 = st.columns([1, 2])
                with c1:
                    st.image(uploaded_file, use_container_width=True)
                
                with c2:
                    st.markdown(f"**Photo {i+1}**")
                    
                    new_service = st.selectbox(
                        "Service Type", 
                        SERVICES_LIST, 
                        index=SERVICES_LIST.index(data['service']) if data['service'] in SERVICES_LIST else 0,
                        key=f"svc_{file_key}"
                    )
                    
                    if new_service != data['service']:
                        st.session_state.assignments[file_key]['service'] = new_service
                        st.rerun()

                    st.caption(f"📍 **{data['loc']['name']}**")
                    st.caption(f"📅 **{data['date'].strftime('%A, %m-%d-%Y')}**") # Added Day Name to verify No Weekends

                    final_name, final_bytes = process_single_image(
                        uploaded_file.getvalue(),
                        new_service,
                        data['loc'],
                        data['date']
                    )
                    
                    st.markdown(f"File: `{final_name}`")

                    st.download_button(
                        label="⬇️ Download Image",
                        data=final_bytes,
                        file_name=final_name,
                        mime="image/jpeg",
                        key=f"btn_{file_key}",
                        use_container_width=True
                    )
                st.divider()
