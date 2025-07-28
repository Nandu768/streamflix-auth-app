import streamlit as st
import sqlite3
import hashlib
import secrets
import re
from datetime import datetime, timedelta
from dotenv import load_dotenv
import os
import urllib.request
import urllib.error

# Load environment variables
load_dotenv()

# Database setup
def init_db():
    try:
        conn = sqlite3.connect('streamflix.db')
        conn.text_factory = str
        c = conn.cursor()
        
        # Create tables
        c.execute('''CREATE TABLE IF NOT EXISTS users 
                    (id INTEGER PRIMARY KEY AUTOINCREMENT,
                     username TEXT UNIQUE,
                     password_hash TEXT,
                     salt TEXT,
                     name TEXT,
                     phone TEXT,
                     email TEXT,
                     failed_attempts INTEGER DEFAULT 0,
                     locked_until TIMESTAMP)''')
        
        c.execute('''CREATE TABLE IF NOT EXISTS sessions 
                    (session_id TEXT PRIMARY KEY,
                     user_id INTEGER,
                     expiry TIMESTAMP,
                     FOREIGN KEY (user_id) REFERENCES users(id))''')
        
        c.execute('''CREATE TABLE IF NOT EXISTS mfa_codes 
                    (username TEXT PRIMARY KEY,
                     code TEXT,
                     expiry TIMESTAMP)''')
        
        c.execute('''CREATE TABLE IF NOT EXISTS movies 
                    (id INTEGER PRIMARY KEY AUTOINCREMENT,
                     title TEXT,
                     genre TEXT,
                     year INTEGER,
                     thumbnail TEXT,
                     rating REAL)''')
        
        # Verify movies table schema
        c.execute("PRAGMA table_info(movies)")
        columns = [col[1] for col in c.fetchall()]
        if 'rating' not in columns:
            c.execute('ALTER TABLE movies ADD COLUMN rating REAL')
            print(" Added rating column to movies table")
        
        # Check and populate movies with working poster URLs
        c.execute('SELECT COUNT(*) FROM movies')
        count = c.fetchone()[0]
        if count == 0:
            # Using reliable placeholder images and some working URLs
            sample_movies = [
                ("Inception", "Sci-Fi", 2010, "https://via.placeholder.com/300x450/0a0a0a/ffffff?text=INCEPTION", 8.8),
                ("The Shawshank Redemption", "Drama", 1994, "https://via.placeholder.com/300x450/1e3a8a/ffffff?text=SHAWSHANK", 9.3),
                ("The Dark Knight", "Action", 2008, "https://via.placeholder.com/300x450/000000/ffffff?text=DARK+KNIGHT", 9.0),
                ("Pulp Fiction", "Crime", 1994, "https://via.placeholder.com/300x450/8b0000/ffffff?text=PULP+FICTION", 8.9),
                ("Interstellar", "Sci-Fi", 2014, "https://via.placeholder.com/300x450/2c3e50/ffffff?text=INTERSTELLAR", 8.6),
                ("Avatar", "Sci-Fi", 2009, "https://via.placeholder.com/300x450/0066cc/ffffff?text=AVATAR", 7.8),
                ("Titanic", "Romance", 1997, "https://via.placeholder.com/300x450/006666/ffffff?text=TITANIC", 7.9),
                ("The Godfather", "Crime", 1972, "https://via.placeholder.com/300x450/800000/ffffff?text=GODFATHER", 9.2)
            ]
            c.executemany('INSERT INTO movies (title, genre, year, thumbnail, rating) VALUES (?, ?, ?, ?, ?)', sample_movies)
            conn.commit()
            print(f" Inserted {len(sample_movies)} sample movies with placeholder posters")
            for movie in sample_movies:
                print(f"  - {movie[0]}: {movie[3]}")
        else:
            print(f" Found {count} movies in database")
            c.execute('SELECT title, thumbnail FROM movies')
            for row in c.fetchall():
                print(f"  - {row[0]}: {row[1]}")
        
        conn.close()
        print(" Database initialized successfully")
        return True
    except sqlite3.Error as e:
        print(f" Database error: {e}")
        return False
    except Exception as e:
        print(f" Unexpected error initializing database: {e}")
        return False
    finally:
        if 'conn' in locals():
            conn.close()

# Custom CSS with improved styling and pure white headings
st.markdown("""
<style>
body {
    background-color: #141414;
    font-family: 'Helvetica Neue', Helvetica, Arial, sans-serif;
    color: #fff;
}
.stApp {
    max-width: 1200px;
    margin: 0 auto;
    padding: 20px;
    background-color: #141414;
}
h1, h2, h3, h4, h5, h6 {
    color: #ffffff !important;
    text-align: center;
    font-weight: bold;
}
h1 {
    font-size: 2.8em;
    margin-bottom: 20px;
}
h2 {
    font-size: 2.2em;
    margin-bottom: 15px;
}
h3 {
    font-size: 1.8em;
    margin-bottom: 12px;
}
.stTextInput > div > input {
    background-color: #333;
    border: 1px solid #555;
    border-radius: 4px;
    padding: 10px;
    font-size: 1em;
    color: #fff;
}
.stButton > button {
    background-color: #e50914;
    color: white;
    border-radius: 4px;
    padding: 10px 20px;
    font-size: 1em;
    border: none;
    transition: background-color 0.3s;
}
.stButton > button:hover {
    background-color: #b20710;
}
.error {
    color: #e50914;
    font-size: 0.9em;
    text-align: center;
}
.success {
    color: #46d369;
    font-size: 0.9em;
    text-align: center;
}
.validation-error {
    color: #e50914;
    font-size: 0.85em;
    margin-top: 5px;
}
.validation-success {
    color: #46d369;
    font-size: 0.85em;
    margin-top: 5px;
}
.password-requirement {
    font-size: 0.85em;
    margin: 2px 0;
}
.password-requirement.met {
    color: #46d369;
}
.password-requirement.unmet {
    color: #e50914;
}
.movie-card {
    background: linear-gradient(145deg, #2d2d2d, #1a1a1a);
    border-radius: 12px;
    padding: 15px;
    margin: 15px 0;
    text-align: center;
    transition: transform 0.3s ease, box-shadow 0.3s ease;
    box-shadow: 0 4px 8px rgba(0,0,0,0.3);
    border: 1px solid #333;
}
.movie-card:hover {
    transform: translateY(-5px);
    box-shadow: 0 8px 25px rgba(229,9,20,0.3);
}
.movie-poster {
    width: 100%;
    max-width: 250px;
    height: 350px;
    object-fit: cover;
    border-radius: 8px;
    margin-bottom: 10px;
    border: 2px solid #444;
}
.movie-poster-placeholder {
    width: 100%;
    max-width: 250px;
    height: 350px;
    background: linear-gradient(135deg, #333, #555);
    border-radius: 8px;
    display: flex;
    align-items: center;
    justify-content: center;
    color: #fff;
    font-size: 18px;
    font-weight: bold;
    margin-bottom: 10px;
    border: 2px solid #666;
}
.movie-title {
    font-size: 1.2em;
    font-weight: bold;
    margin: 10px 0 5px;
    color: #fff;
}
.movie-details {
    font-size: 0.95em;
    color: #b3b3b3;
    margin: 5px 0;
}
.movie-rating {
    color: #46d369;
    font-size: 1.1em;
    margin: 8px 0;
    font-weight: bold;
}
.watch-now-btn, .download-btn {
    width: 100%;
    margin: 5px 0;
}
.nav-button {
    margin: 10px 5px;
}
.search-bar {
    margin: 20px 0;
}
.stSelectbox {
    background-color: #333;
    border-radius: 4px;
}
.stSelectbox > div > select {
    color: #fff;
    background-color: #333;
    border: none;
}
</style>
""", unsafe_allow_html=True)

# Password hashing
def hash_password(password, salt=None):
    try:
        password = password.encode('utf-8').decode('utf-8')
        if salt is None:
            salt = secrets.token_hex(16)
        salted_password = password + salt
        return hashlib.sha256(salted_password.encode('utf-8')).hexdigest(), salt
    except UnicodeEncodeError:
        print(" Password encoding error")
        return None, None

# Validate password strength
def is_strong_password(password):
    messages = []
    if len(password) < 8:
        messages.append("Password must be at least 8 characters long")
    if re.search(r'(.)\1{2,}', password):
        messages.append("No more than 2 identical characters in a row")
    conditions_met = 0
    if re.search(r'[a-z]', password):
        conditions_met += 1
    else:
        messages.append("Missing lowercase letter (a-z)")
    if re.search(r'[A-Z]', password):
        conditions_met += 1
    else:
        messages.append("Missing uppercase letter (A-Z)")
    if re.search(r'\d', password):
        conditions_met += 1
    else:
        messages.append("Missing number (0-9)")
    if re.search(r'[!@#$%^&*(),.?":{}|<>]', password):
        conditions_met += 1
    else:
        messages.append("Missing special character (e.g., !@#$%^&*)")
    if conditions_met < 3:
        messages.append(f"Must meet at least 3 of: lowercase, uppercase, number, special character (currently {conditions_met}/3)")
    return len(messages) == 0, messages

# Real-time password feedback
def display_password_feedback(password):
    length_met = len(password) >= 8
    no_repeats = not re.search(r'(.)\1{2,}', password)
    lowercase_met = bool(re.search(r'[a-z]', password))
    uppercase_met = bool(re.search(r'[A-Z]', password))
    number_met = bool(re.search(r'\d', password))
    special_met = bool(re.search(r'[!@#$%^&*(),.?":{}|<>]', password))
    conditions_count = sum([lowercase_met, uppercase_met, number_met, special_met])
    conditions_met = conditions_count >= 3
    
    st.markdown(f'<p class="password-requirement {"met" if length_met else "unmet"}">At least 8 characters: {"✔" if length_met else "✘"}</p>', unsafe_allow_html=True)
    st.markdown(f'<p class="password-requirement {"met" if no_repeats else "unmet"}">No more than 2 identical characters in a row: {"✔" if no_repeats else "✘"}</p>', unsafe_allow_html=True)
    st.markdown(f'<p class="password-requirement {"met" if lowercase_met else "unmet"}">Lowercase letter (a-z): {"✔" if lowercase_met else "✘"}</p>', unsafe_allow_html=True)
    st.markdown(f'<p class="password-requirement {"met" if uppercase_met else "unmet"}">Uppercase letter (A-Z): {"✔" if uppercase_met else "✘"}</p>', unsafe_allow_html=True)
    st.markdown(f'<p class="password-requirement {"met" if number_met else "unmet"}">Number (0-9): {"✔" if number_met else "✘"}</p>', unsafe_allow_html=True)
    st.markdown(f'<p class="password-requirement {"met" if special_met else "unmet"}">Special character (e.g., !@#$%^&*): {"✔" if special_met else "✘"}</p>', unsafe_allow_html=True)
    st.markdown(f'<p class="password-requirement {"met" if conditions_met else "unmet"}">At least 3 of lowercase, uppercase, number, special: {"✔" if conditions_met else "✘"} ({conditions_count}/3)</p>', unsafe_allow_html=True)

# Enhanced email validation
def is_valid_email(email):
    """Validate email address with comprehensive regex"""
    if not email or len(email.strip()) == 0:
        return False, "Email cannot be empty"
    
    email = email.strip()
    
    # Comprehensive email regex pattern
    email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    
    if not re.match(email_pattern, email):
        return False, "Invalid email format (must be like user@domain.com)"
    
    # Additional checks
    if len(email) > 254:
        return False, "Email too long (max 254 characters)"
    
    if '..' in email:
        return False, "Email cannot contain consecutive dots"
    
    if email.startswith('.') or email.endswith('.'):
        return False, "Email cannot start or end with a dot"
    
    return True, "Valid email"

# Enhanced phone validation with country code
def is_valid_phone(phone):
    """Validate phone number with country code and exactly 10 digits after country code"""
    if not phone or len(phone.strip()) == 0:
        return False, "Phone number cannot be empty"
    
    phone = phone.strip()
    
    # Remove spaces, hyphens, and parentheses
    cleaned_phone = re.sub(r'[\s\-\(\)]', '', phone)
    
    # Check if it starts with + (country code)
    if not cleaned_phone.startswith('+'):
        return False, "Phone number must include country code (e.g., +91 for India)"
    
    # Remove the + sign for further validation
    phone_without_plus = cleaned_phone[1:]
    
    # Check if the remaining part contains only digits
    if not phone_without_plus.isdigit():
        return False, "Phone number can only contain digits after country code"
    
    # Check length - should be country code (1-4 digits) + 10 digits
    if len(phone_without_plus) < 11 or len(phone_without_plus) > 14:
        return False, "Invalid phone number length (country code + 10 digits required)"
    
    # Extract potential country code and phone number
    # Most common country codes are 1-4 digits
    valid_country_codes = ['1', '7', '20', '27', '30', '31', '32', '33', '34', '36', '39', '40', '41', '43', '44', '45', '46', '47', '48', '49', '51', '52', '53', '54', '55', '56', '57', '58', '60', '61', '62', '63', '64', '65', '66', '81', '82', '84', '86', '90', '91', '92', '93', '94', '95', '98', '212', '213', '216', '218', '220', '221', '222', '223', '224', '225', '226', '227', '228', '229', '230', '231', '232', '233', '234', '235', '236', '237', '238', '239', '240', '241', '242', '243', '244', '245', '246', '248', '249', '250', '251', '252', '253', '254', '255', '256', '257', '258', '260', '261', '262', '263', '264', '265', '266', '267', '268', '269', '290', '291', '297', '298', '299', '350', '351', '352', '353', '354', '355', '356', '357', '358', '359', '370', '371', '372', '373', '374', '375', '376', '377', '378', '380', '381', '382', '383', '385', '386', '387', '389', '420', '421', '423', '500', '501', '502', '503', '504', '505', '506', '507', '508', '509', '590', '591', '592', '593', '594', '595', '596', '597', '598', '599', '670', '672', '673', '674', '675', '676', '677', '678', '679', '680', '681', '682', '683', '684', '685', '686', '687', '688', '689', '690', '691', '692', '850', '852', '853', '855', '856', '880', '886', '960', '961', '962', '963', '964', '965', '966', '967', '968', '970', '971', '972', '973', '974', '975', '976', '977', '992', '993', '994', '995', '996', '998']
    
    found_valid_code = False
    remaining_digits = ""
    
    # Check for valid country codes
    for code in sorted(valid_country_codes, key=len, reverse=True):  # Check longer codes first
        if phone_without_plus.startswith(code):
            remaining_digits = phone_without_plus[len(code):]
            if len(remaining_digits) == 10:  # Exactly 10 digits after country code
                found_valid_code = True
                break
    
    if not found_valid_code:
        return False, "Invalid country code or phone number must have exactly 10 digits after country code"
    
    return True, "Valid phone number"

# Generate MFA code
def generate_mfa_code():
    code = str(secrets.randbelow(1000000)).zfill(6)
    print(f" Generated MFA code: {code}")
    return code

# Mock SMS OTP (logs to console)
def send_mfa_mock_sms(phone, username, code):
    debug_log = []
    debug_log.append(f" Attempting to send mock SMS MFA to: {phone}")
    
    is_valid, message = is_valid_phone(phone)
    if not is_valid:
        debug_log.append(f" Invalid phone number: {message}")
        return False, f"Invalid phone number: {message}", debug_log
    
    try:
        print(f" Mock SMS to {phone} for user {username}: Your StreamFlix MFA code is {code}")
        debug_log.append(f" Mock SMS sent to {phone}: Your StreamFlix MFA code is {code}")
        return True, "SMS MFA sent successfully (check console for code)", debug_log
    except Exception as e:
        debug_log.append(f" Mock SMS error: {str(e)}")
        return False, f"Mock SMS failed: {str(e)}", debug_log

# Store MFA code
def store_mfa_code(username, code):
    try:
        expiry = datetime.now() + timedelta(minutes=5)
        conn = sqlite3.connect('streamflix.db')
        conn.text_factory = str
        c = conn.cursor()
        c.execute('INSERT OR REPLACE INTO mfa_codes (username, code, expiry) VALUES (?, ?, ?)',
                 (username.encode('utf-8').decode('utf-8'), code, expiry.isoformat()))
        conn.commit()
        print(f" MFA code {code} stored for user: {username}, expiry: {expiry}")
        conn.close()
        return True
    except sqlite3.Error as e:
        print(f" Error storing MFA code for {username}: {e}")
        return False
    finally:
        if 'conn' in locals():
            conn.close()

# Check if account is locked
def is_account_locked(username):
    try:
        conn = sqlite3.connect('streamflix.db')
        conn.text_factory = str
        c = conn.cursor()
        c.execute('SELECT locked_until, failed_attempts FROM users WHERE username = ?', (username.encode('utf-8').decode('utf-8'),))
        result = c.fetchone()
        conn.close()
        
        if result:
            locked_until, failed_attempts = result
            if locked_until and datetime.fromisoformat(locked_until) > datetime.now():
                return True, failed_attempts
        return False, 0
    except sqlite3.Error as e:
        print(f" Error checking account lock for {username}: {e}")
        return False, 0

# Register user with enhanced validation
def register_user(username, password, name, phone, email):
    try:
        # Validate email
        email_valid, email_message = is_valid_email(email)
        if not email_valid:
            return False, email_message
        
        # Validate phone
        phone_valid, phone_message = is_valid_phone(phone)
        if not phone_valid:
            return False, phone_message
        
        # Validate password
        is_strong, messages = is_strong_password(password)
        if not is_strong:
            return False, "; ".join(messages)
        
        password_hash, salt = hash_password(password)
        if password_hash is None:
            return False, "Invalid password encoding"
        
        conn = sqlite3.connect('streamflix.db')
        conn.text_factory = str
        c = conn.cursor()
        c.execute('INSERT INTO users (username, password_hash, salt, name, phone, email) VALUES (?, ?, ?, ?, ?, ?)',
                 (username.encode('utf-8').decode('utf-8'), password_hash, salt, name.encode('utf-8').decode('utf-8'), phone, email))
        conn.commit()
        conn.close()
        print(f" User registered successfully: {username}")
        return True, "Registration successful"
    except sqlite3.IntegrityError:
        return False, "Username already exists"
    except sqlite3.Error as e:
        print(f" Error registering user {username}: {e}")
        return False, "Database error during registration"
    finally:
        if 'conn' in locals():
            conn.close()

# Login user
def login_user(username, password):
    debug_log = []
    debug_log.append(f" Login attempt for user: {username}")
    
    try:
        username = username.encode('utf-8').decode('utf-8')
        password = password.encode('utf-8').decode('utf-8')
        
        is_locked, failed_attempts = is_account_locked(username)
        if is_locked:
            debug_log.append(f" Account is locked. Failed attempts: {failed_attempts}")
            return False, None, f"Account is locked. Try again later. Failed attempts: {failed_attempts}", debug_log
        
        conn = sqlite3.connect('streamflix.db')
        conn.text_factory = str
        c = conn.cursor()
        c.execute('SELECT id, password_hash, salt, phone FROM users WHERE username = ?', (username,))
        user = c.fetchone()
        
        if user:
            user_id, stored_hash, salt, phone = user
            debug_log.append(f" User found in database")
            debug_log.append(f" Phone: {phone}")
            
            password_hash, _ = hash_password(password, salt)
            
            if password_hash is None:
                conn.close()
                debug_log.append(f" Password encoding error")
                return False, None, "Invalid password encoding", debug_log
            
            if password_hash == stored_hash:
                debug_log.append(f" Password verification successful")
                c.execute('UPDATE users SET failed_attempts = 0, locked_until = NULL WHERE username = ?', (username,))
                conn.commit()
                conn.close()
                
                code = generate_mfa_code()
                if store_mfa_code(username, code):
                    debug_log.append(f" MFA code stored in database")
                    success, message, sms_debug = send_mfa_mock_sms(phone, username, code)
                    debug_log.extend(sms_debug)
                    if success:
                        debug_log.append(f" Mock SMS MFA sent successfully")
                        return True, None, f"Please enter the MFA code sent to your phone: {phone} (check console/logs for code)", debug_log
                    else:
                        debug_log.append(f" Mock SMS MFA failed: {message}")
                        return False, None, message, debug_log
                else:
                    debug_log.append(f" Failed to store MFA code")
                    conn.close()
                    return False, None, "Failed to store MFA code", debug_log
            else:
                debug_log.append(f" Password verification failed")
                c.execute('SELECT failed_attempts FROM users WHERE username = ?', (username,))
                current_attempts = c.fetchone()
                failed_attempts = (current_attempts[0] if current_attempts else 0) + 1
                
                locked_until = None
                if failed_attempts >= 3:
                    locked_until = (datetime.now() + timedelta(minutes=15)).isoformat()
                
                c.execute('UPDATE users SET failed_attempts = ?, locked_until = ? WHERE username = ?',
                         (failed_attempts, locked_until, username))
                conn.commit()
                conn.close()
                debug_log.append(f" Failed attempts updated: {failed_attempts}")
                return False, None, f"Invalid credentials. Failed attempts: {failed_attempts}", debug_log
        else:
            conn.close()
            debug_log.append(f" User not found in database")
            return False, None, "User not found", debug_log
            
    except sqlite3.Error as e:
        debug_log.append(f" Database error: {e}")
        if 'conn' in locals():
            conn.close()
        return False, None, "Database error during login", debug_log

# Verify MFA code
def verify_mfa_code(username, code):
    try:
        username = username.encode('utf-8').decode('utf-8')
        conn = sqlite3.connect('streamflix.db')
        conn.text_factory = str
        c = conn.cursor()
        c.execute('SELECT code, expiry FROM mfa_codes WHERE username = ?', (username,))
        mfa = c.fetchone()
        
        if mfa:
            stored_code, expiry_str = mfa
            expiry = datetime.fromisoformat(expiry_str)
            
            print(f"🔍 MFA Verification - User: {username}")
            print(f"🔢 Entered code: {code}")
            print(f"🔢 Stored code: {stored_code}")
            print(f"🕒 Expiry: {expiry}")
            print(f"🕒 Current time: {datetime.now()}")
            
            if expiry > datetime.now():
                if stored_code == code:
                    session_id = secrets.token_hex(32)
                    session_expiry = datetime.now() + timedelta(hours=24)
                    
                    c.execute('SELECT id FROM users WHERE username = ?', (username,))
                    user_result = c.fetchone()
                    if user_result:
                        user_id = user_result[0]
                        c.execute('INSERT INTO sessions (session_id, user_id, expiry) VALUES (?, ?, ?)',
                                 (session_id, user_id, session_expiry.isoformat()))
                        c.execute('DELETE FROM mfa_codes WHERE username = ?', (username,))
                        conn.commit()
                        conn.close()
                        print(f" MFA verification successful for user: {username}")
                        return True, session_id, "MFA verification successful"
                    else:
                        conn.close()
                        print(f" User not found during session creation: {username}")
                        return False, None, "User not found during session creation"
                else:
                    conn.close()
                    print(f" Invalid MFA code for {username}")
                    return False, None, "Invalid MFA code"
            else:
                c.execute('DELETE FROM mfa_codes WHERE username = ?', (username,))
                conn.commit()
                conn.close()
                print(f" MFA code expired for {username}")
                return False, None, "MFA code has expired"
        else:
            conn.close()
            print(f" No MFA code found for user: {username}")
            return False, None, "No MFA code found. Please login again."
            
    except sqlite3.Error as e:
        print(f" Error verifying MFA for {username}: {e}")
        if 'conn' in locals():
            conn.close()
        return False, None, "Database error during MFA verification"

# Verify session
def verify_session(session_id):
    try:
        conn = sqlite3.connect('streamflix.db')
        conn.text_factory = str
        c = conn.cursor()
        c.execute('SELECT user_id, expiry FROM sessions WHERE session_id = ?', (session_id,))
        session = c.fetchone()
        
        if session and datetime.fromisoformat(session[1]) > datetime.now():
            c.execute('SELECT username FROM users WHERE id = ?', (session[0],))
            username = c.fetchone()[0]
            conn.close()
            return True, username
        
        conn.close()
        print(f" Invalid or expired session: {session_id}")
        return False, None
    except sqlite3.Error as e:
        print(f" Error verifying session: {e}")
        if 'conn' in locals():
            conn.close()
        return False, None

# Get movies
def get_movies(search_term=None):
    try:
        conn = sqlite3.connect('streamflix.db')
        conn.text_factory = str
        c = conn.cursor()
        if search_term:
            c.execute('SELECT title, genre, year, thumbnail, rating FROM movies WHERE title LIKE ?', (f'%{search_term}%',))
        else:
            c.execute('SELECT title, genre, year, thumbnail, rating FROM movies')
        movies = [{"title": row[0], "genre": row[1], "year": row[2], "thumbnail": row[3], "rating": row[4]} for row in c.fetchall()]
        conn.close()
        print(f" Fetched {len(movies)} movies (search: {search_term if search_term else 'None'})")
        for movie in movies:
            print(f"  - {movie['title']}: {movie['thumbnail']}")
        return movies
    except sqlite3.Error as e:
        print(f" Error fetching movies: {e}")
        if 'conn' in locals():
            conn.close()
        return []

# Improved image loading function
def load_movie_poster(movie):
    """Load movie poster with fallback options"""
    poster_html = ""
    
    if movie['thumbnail']:
        try:
            # Try to load the image with error handling
            poster_html = f'''
            <div class="movie-poster-container">
                <img src="{movie['thumbnail']}" 
                     class="movie-poster" 
                     alt="{movie['title']} Poster"
                     onerror="this.style.display='none'; this.nextElementSibling.style.display='flex';"
                     onload="this.nextElementSibling.style.display='none';">
                <div class="movie-poster-placeholder" style="display:none;">
                    <div>
                        <div style="font-size: 16px; margin-bottom: 5px;">{movie['title']}</div>
                        <div style="font-size: 12px; opacity: 0.7;">({movie['year']})</div>
                    </div>
                </div>
            </div>
            '''
            return poster_html
        except Exception as e:
            print(f" Error creating poster HTML for {movie['title']}: {e}")
    
    # Fallback placeholder
    return f'''
    <div class="movie-poster-placeholder">
        <div>
            <div style="font-size: 16px; margin-bottom: 5px;">{movie['title']}</div>
            <div style="font-size: 12px; opacity: 0.7;">({movie['year']})</div>
        </div>
    </div>
    '''

# Input field with validation display
def validated_text_input(label, value, key, placeholder="", validation_func=None, input_type="default"):
    """Create a text input with real-time validation feedback"""
    if input_type == "password":
        user_input = st.text_input(label, value=value, key=key, placeholder=placeholder, type="password")
    else:
        user_input = st.text_input(label, value=value, key=key, placeholder=placeholder)
    
    if validation_func and user_input:
        is_valid, message = validation_func(user_input)
        if is_valid:
            st.markdown(f'<p class="validation-success">✓ {message}</p>', unsafe_allow_html=True)
        else:
            st.markdown(f'<p class="validation-error">✗ {message}</p>', unsafe_allow_html=True)
    
    return user_input

# Main Streamlit app
def main():
    # Set page config for dark background
    st.set_page_config(
        page_title="StreamFlix",
        page_icon="🎬",
        layout="wide",
        initial_sidebar_state="collapsed"
    )
    
    # Initialize session state
    if 'session_id' not in st.session_state:
        st.session_state.session_id = None
    if 'page' not in st.session_state:
        st.session_state.page = 'login'
    if 'pending_mfa_username' not in st.session_state:
        st.session_state.pending_mfa_username = None
    if 'show_success' not in st.session_state:
        st.session_state.show_success = False
    if 'success_message' not in st.session_state:
        st.session_state.success_message = ""
    if 'dashboard_page' not in st.session_state:
        st.session_state.dashboard_page = 'movies'

    # Initialize database
    if not init_db():
        st.error("Failed to initialize database. Check console logs for details.")
        return

    with st.container():
        if st.session_state.page == 'login':
            st.title("🎬 Welcome to StreamFlix")
            
            if st.session_state.show_success:
                st.markdown(f'<p class="success">{st.session_state.success_message}</p>', unsafe_allow_html=True)
                st.session_state.show_success = False
                st.session_state.success_message = ""
            
            col1, col2, col3 = st.columns([1, 2, 1])
            with col2:
                username = st.text_input("Username", placeholder="Enter your username")
                password = st.text_input("Password", type="password", placeholder="Enter your password")
                col_login, col_signup = st.columns(2)
                with col_login:
                    if st.button(" Login", use_container_width=True):
                        if username and password:
                            success, session_id, message, debug_logs = login_user(username, password)
                            if success and session_id:
                                st.session_state.session_id = session_id
                                st.session_state.page = 'dashboard'
                                st.session_state.show_success = True
                                st.session_state.success_message = "Login successful!"
                                st.rerun()
                            elif success:
                                st.session_state.pending_mfa_username = username
                                st.session_state.page = 'mfa'
                                st.info(message)
                                st.rerun()
                            else:
                                st.markdown(f'<p class="error">{message}</p>', unsafe_allow_html=True)
                                for log in debug_logs:
                                    print(log)
                        else:
                            st.markdown('<p class="error">Please enter username and password</p>', unsafe_allow_html=True)
                with col_signup:
                    if st.button(" Sign Up", use_container_width=True):
                        st.session_state.page = 'register'
                        st.rerun()
        
        elif st.session_state.page == 'register':
            st.title("Join StreamFlix")
            col1, col2, col3 = st.columns([1, 2, 1])
            with col2:
                name = st.text_input("Full Name", placeholder="Enter your full name")
                username = st.text_input("Username", placeholder="Choose a username")
                password = st.text_input("Password", type="password", placeholder="Create a strong password")
                if password:
                    display_password_feedback(password)
                
                # Enhanced phone input with validation
                phone = validated_text_input(
                    "Phone Number", 
                    "", 
                    "phone_input", 
                    "e.g., +919876543210 (country code + 10 digits)", 
                    is_valid_phone
                )
                
                # Enhanced email input with validation
                email = validated_text_input(
                    "Email", 
                    "", 
                    "email_input", 
                    "your.email@example.com", 
                    is_valid_email
                )
                
                col_reg, col_back = st.columns(2)
                with col_reg:
                    if st.button(" Register", use_container_width=True):
                        if all([name, username, password, phone, email]):
                            success, message = register_user(username, password, name, phone, email)
                            if success:
                                st.session_state.show_success = True
                                st.session_state.success_message = "Registration successful! Please log in."
                                st.session_state.page = 'login'
                                st.rerun()
                            else:
                                st.markdown(f'<p class="error">{message}</p>', unsafe_allow_html=True)
                        else:
                            st.markdown('<p class="error">Please fill in all fields</p>', unsafe_allow_html=True)
                with col_back:
                    if st.button("⬅ Back to Login", use_container_width=True):
                        st.session_state.page = 'login'
                        st.rerun()
        
        elif st.session_state.page == 'mfa':
            st.title("MFA Verification")
            col1, col2, col3 = st.columns([1, 2, 1])
            with col2:
                st.info("Please check the console or logs for the MFA code")
                username = st.session_state.pending_mfa_username
                code = st.text_input("Enter MFA Code", type="password", max_chars=6, placeholder="000000")
                col_verify, col_resend, col_back = st.columns(3)
                with col_verify:
                    if st.button(" Verify", use_container_width=True):
                        if code:
                            success, session_id, message = verify_mfa_code(username, code)
                            if success:
                                st.session_state.session_id = session_id
                                st.session_state.page = 'dashboard'
                                st.session_state.pending_mfa_username = None
                                st.session_state.show_success = True
                                st.session_state.success_message = "MFA verification successful!"
                                st.rerun()
                            else:
                                st.markdown(f'<p class="error">{message}</p>', unsafe_allow_html=True)
                        else:
                            st.markdown(f'<p class="error">Please enter the MFA code</p>', unsafe_allow_html=True)
                with col_resend:
                    if st.button(" Resend", use_container_width=True):
                        try:
                            conn = sqlite3.connect('streamflix.db')
                            conn.text_factory = str
                            c = conn.cursor()
                            c.execute('SELECT phone FROM users WHERE username = ?', (username,))
                            user_data = c.fetchone()
                            conn.close()
                            
                            if user_data and user_data[0]:
                                code = generate_mfa_code()
                                if store_mfa_code(username, code):
                                    success, message, debug_logs = send_mfa_mock_sms(user_data[0], username, code)
                                    if success:
                                        st.markdown(f'<p class="success">New MFA code sent to {user_data[0]} (check console/logs)</p>', unsafe_allow_html=True)
                                    else:
                                        st.markdown(f'<p class="error">Failed to send MFA code: {message}</p>', unsafe_allow_html=True)
                                    for log in debug_logs:
                                        print(log)
                                else:
                                    st.markdown(f'<p class="error">Failed to generate new MFA code</p>', unsafe_allow_html=True)
                            else:
                                st.markdown(f'<p class="error">No phone number found for user</p>', unsafe_allow_html=True)
                        except sqlite3.Error as e:
                            st.markdown(f'<p class="error">Error resending MFA: {e}</p>', unsafe_allow_html=True)
                with col_back:
                    if st.button("⬅ Back", use_container_width=True):
                        st.session_state.pending_mfa_username = None
                        st.session_state.page = 'login'
                        st.rerun()
        
        elif st.session_state.page == 'dashboard':
            is_valid, username = verify_session(st.session_state.session_id)
            if is_valid:
                if st.session_state.show_success:
                    st.markdown(f'<p class="success">{st.session_state.success_message}</p>', unsafe_allow_html=True)
                    st.session_state.show_success = False
                    st.session_state.success_message = ""
                
                try:
                    conn = sqlite3.connect('streamflix.db')
                    conn.text_factory = str
                    c = conn.cursor()
                    c.execute('SELECT name FROM users WHERE username = ?', (username,))
                    name = c.fetchone()[0]
                    conn.close()
                except sqlite3.Error as e:
                    st.markdown(f'<p class="error">Database error: {e}</p>', unsafe_allow_html=True)
                    return
                
                st.title(f"Welcome to StreamFlix, {name}!")
                
                # Navigation buttons
                col1, col2, col3, col4 = st.columns(4)
                with col1:
                    if st.button(" Movies", key="nav_movies", help="View movies", use_container_width=True):
                        st.session_state.dashboard_page = 'movies'
                with col2:
                    if st.button(" Settings", key="nav_settings", help="Update profile", use_container_width=True):
                        st.session_state.dashboard_page = 'settings'
                with col3:
                    if st.button(" Payment", key="nav_payment", help="Manage payment", use_container_width=True):
                        st.session_state.dashboard_page = 'payment'
                with col4:
                    if st.button(" Logout", key="logout", use_container_width=True):
                        try:
                            conn = sqlite3.connect('streamflix.db')
                            conn.text_factory = str
                            c = conn.cursor()
                            c.execute('DELETE FROM sessions WHERE session_id = ?', (st.session_state.session_id,))
                            conn.commit()
                            conn.close()
                            st.session_state.session_id = None
                            st.session_state.page = 'login'
                            st.session_state.show_success = True
                            st.session_state.success_message = "Logged out successfully!"
                            st.rerun()
                        except sqlite3.Error as e:
                            st.markdown(f'<p class="error">Error logging out: {e}</p>', unsafe_allow_html=True)
                
                st.markdown("---")
                
                # Dashboard content
                if st.session_state.dashboard_page == 'movies':
                    st.markdown("### Trending Movies")
                    
                    # Search functionality
                    search_col1, search_col2 = st.columns([3, 1])
                    with search_col1:
                        search_term = st.text_input("Search Movies by Title", key="movie_search", placeholder="Enter movie title to filter")
                    with search_col2:
                        if st.button("Clear Search", use_container_width=True):
                            st.session_state.movie_search = ""
                            st.rerun()
                    
                    movies = get_movies(search_term)
                    if movies:
                        # Display movies in a grid
                        cols = st.columns(3)
                        for idx, movie in enumerate(movies):
                            with cols[idx % 3]:
                                with st.container():
                                    st.markdown('<div class="movie-card">', unsafe_allow_html=True)
                                    
                                    # Display poster with improved error handling
                                    poster_html = load_movie_poster(movie)
                                    st.markdown(poster_html, unsafe_allow_html=True)
                                    
                                    # Movie details
                                    st.markdown(f'<p class="movie-title">{movie["title"]}</p>', unsafe_allow_html=True)
                                    st.markdown(f'<p class="movie-details">{movie["genre"]} | {movie["year"]}</p>', unsafe_allow_html=True)
                                    st.markdown(f'<p class="movie-rating">⭐ {movie["rating"]}/10</p>', unsafe_allow_html=True)
                                    
                                    # Action buttons
                                    if st.button("▶️ Watch Now", key=f"watch_{movie['title']}_{idx}", help="Start streaming", use_container_width=True):
                                        st.success(f"🎥 Starting stream for {movie['title']}...")
                                        st.balloons()
                                    if st.button("⬇ Download", key=f"download_{movie['title']}_{idx}", help="Download movie", use_container_width=True):
                                        st.info(f" Download started for {movie['title']}...")
                                    
                                    st.markdown('</div>', unsafe_allow_html=True)
                                    st.markdown("<br>", unsafe_allow_html=True)
                    else:
                        st.markdown('<div style="text-align: center; padding: 50px;">', unsafe_allow_html=True)
                        st.markdown('<p class="error"> No movies found. Please check console logs for database issues.</p>', unsafe_allow_html=True)
                        st.markdown('</div>', unsafe_allow_html=True)
                
                elif st.session_state.dashboard_page == 'settings':
                    st.markdown("### Profile Settings")
                    with st.form("profile_form"):
                        st.markdown("Update your profile information:")
                        
                        # Enhanced phone input with validation
                        new_phone = validated_text_input(
                            " Phone Number", 
                            "", 
                            "new_phone_input", 
                            "e.g., +919876543210 (country code + 10 digits)", 
                            is_valid_phone
                        )
                        
                        # Enhanced email input with validation
                        new_email = validated_text_input(
                            " Email", 
                            "", 
                            "new_email_input", 
                            "your.email@example.com", 
                            is_valid_email
                        )
                        
                        if st.form_submit_button(" Update Profile", use_container_width=True):
                            phone_valid, phone_message = is_valid_phone(new_phone) if new_phone else (False, "Phone number required")
                            email_valid, email_message = is_valid_email(new_email) if new_email else (False, "Email required")
                            
                            if phone_valid and email_valid:
                                try:
                                    conn = sqlite3.connect('streamflix.db')
                                    conn.text_factory = str
                                    c = conn.cursor()
                                    c.execute('UPDATE users SET phone = ?, email = ? WHERE username = ?', (new_phone, new_email, username))
                                    conn.commit()
                                    conn.close()
                                    st.success("✅ Profile updated successfully!")
                                    st.balloons()
                                except sqlite3.Error as e:
                                    st.error(f"❌ Error updating profile: {e}")
                            else:
                                if not phone_valid:
                                    st.error(f"❌ Phone: {phone_message}")
                                if not email_valid:
                                    st.error(f"❌ Email: {email_message}")
                
                elif st.session_state.dashboard_page == 'payment':
                    st.markdown("### Payment Options")
                    with st.form("payment_form"):
                        st.markdown("Complete your payment to continue enjoying StreamFlix:")
                        account_number = st.text_input(" Account Number", placeholder="Enter your account number")
                        payment_mode = st.selectbox(" Payment Mode", ["Credit Card", "Debit Card", "UPI", "Net Banking"])
                        password = st.text_input(" Password", type="password", placeholder="Enter your payment password")
                        
                        col1, col2 = st.columns(2)
                        with col1:
                            amount = st.number_input(" Amount (₹)", min_value=1.0, value=299.0, step=1.0)
                        with col2:
                            st.markdown("<br>", unsafe_allow_html=True)
                            st.info(f" Total: ₹{amount}")
                        
                        if st.form_submit_button(" Pay Now", use_container_width=True):
                            if account_number and payment_mode and password:
                                st.success(f" Payment of ₹{amount} processed successfully via {payment_mode}! (Mock Transaction)")
                                st.balloons()
                                st.info("🎉 Your StreamFlix subscription is now active!")
                            else:
                                st.error(" Please fill in all payment fields")
                
            else:
                st.session_state.session_id = None
                st.session_state.page = 'login'
                st.rerun()

if __name__ == "__main__":
    main()