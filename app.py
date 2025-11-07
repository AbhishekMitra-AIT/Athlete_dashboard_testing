from flask import Flask, render_template, request, redirect, url_for, session, flash
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy import Integer, String, Float, Boolean, DateTime
import datetime as dt
from collections import defaultdict
import requests, os, secrets, smtplib
from dotenv import load_dotenv
from werkzeug.security import generate_password_hash, check_password_hash
from authlib.integrations.flask_client import OAuth
from functools import wraps
from itsdangerous import URLSafeTimedSerializer
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

load_dotenv()

class Base(DeclarativeBase):
    pass

db = SQLAlchemy(model_class=Base)
app = Flask(__name__)

# Configuration
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///athlete_data.db"
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", secrets.token_hex(32))

# Strava API Configuration
STRAVA_CLIENT_ID = os.environ.get("STRAVA_CLIENT_ID")
STRAVA_CLIENT_SECRET = os.environ.get("STRAVA_CLIENT_SECRET")
STRAVA_REDIRECT_URI = os.environ.get("STRAVA_REDIRECT_URI", "http://localhost:5001/strava/callback")

# Email Configuration
SMTP_SERVER = os.environ.get("SMTP_SERVER", "smtp.gmail.com")
SMTP_PORT = int(os.environ.get("SMTP_PORT", "587"))
EMAIL_ADDRESS = os.environ.get("EMAIL_ADDRESS")
EMAIL_PASSWORD = os.environ.get("EMAIL_PASSWORD")

# OAuth Configuration
oauth = OAuth(app)

# Google OAuth
google = oauth.register(
    name='google',
    client_id=os.environ.get("GOOGLE_CLIENT_ID"),
    client_secret=os.environ.get("GOOGLE_CLIENT_SECRET"),
    server_metadata_url='https://accounts.google.com/.well-known/openid-configuration',
    client_kwargs={'scope': 'openid email profile'}
)

# GitHub OAuth
github = oauth.register(
    name='github',
    client_id=os.environ.get("GHCLIENT_ID"),
    client_secret=os.environ.get("GHCLIENT_SECRET"),
    access_token_url='https://github.com/login/oauth/access_token',
    access_token_params=None,
    authorize_url='https://github.com/login/oauth/authorize',
    authorize_params=None,
    api_base_url='https://api.github.com/',
    client_kwargs={'scope': 'user:email'},
)

db.init_app(app)

# Models
class User(db.Model):
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    email: Mapped[str] = mapped_column(String(120), unique=True, nullable=False)
    username: Mapped[str] = mapped_column(String(80), nullable=True)
    password_hash: Mapped[str] = mapped_column(String(200), nullable=True)
    oauth_provider: Mapped[str] = mapped_column(String(20), nullable=True)  # 'google', 'github', or None
    oauth_id: Mapped[str] = mapped_column(String(200), nullable=True)
    email_verified: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime, default=dt.datetime.utcnow)
    
class Athlete_Data(db.Model):
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(Integer, nullable=False)  # Link to User
    date: Mapped[str] = mapped_column(String(250), nullable=True)
    activity_type: Mapped[str] = mapped_column(String(100), nullable=True)
    distance: Mapped[float] = mapped_column(Float, nullable=True)
    time: Mapped[str] = mapped_column(String(50), nullable=True)
    pace: Mapped[str] = mapped_column(String(50), nullable=True)
    calories: Mapped[float] = mapped_column(Float, nullable=True)
    month_year: Mapped[str] = mapped_column(String(50), nullable=True)
    strava_id: Mapped[int] = mapped_column(Integer, nullable=True, unique=True)

class StravaToken(db.Model):
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(Integer, nullable=False)  # Link to User
    access_token: Mapped[str] = mapped_column(String(500), nullable=False)
    refresh_token: Mapped[str] = mapped_column(String(500), nullable=False)
    expires_at: Mapped[int] = mapped_column(Integer, nullable=False)
    athlete_id: Mapped[int] = mapped_column(Integer, nullable=False)

with app.app_context():
    db.create_all()

# Email verification token generator
def generate_verification_token(email):
    serializer = URLSafeTimedSerializer(app.config['SECRET_KEY'])
    return serializer.dumps(email, salt='email-verification')

def verify_token(token, expiration=3600):
    serializer = URLSafeTimedSerializer(app.config['SECRET_KEY'])
    try:
        email = serializer.loads(token, salt='email-verification', max_age=expiration)
        return email
    except:
        return None

def send_verification_email(email, token):
    """Send verification email to user"""
    if not EMAIL_ADDRESS or not EMAIL_PASSWORD:
        print("⚠️ Email credentials not configured. Verification email not sent.")
        return False
    
    verification_url = url_for('verify_email', token=token, _external=True)
    
    msg = MIMEMultipart('alternative')
    msg['Subject'] = 'Verify Your Email - Athlete Dashboard'
    msg['From'] = EMAIL_ADDRESS
    msg['To'] = email
    
    html = f"""
    <html>
      <body>
        <h2>Welcome to Athlete Training Dashboard!</h2>
        <p>Please click the link below to verify your email address:</p>
        <p><a href="{verification_url}">Verify Email</a></p>
        <p>Or copy and paste this URL into your browser:</p>
        <p>{verification_url}</p>
        <p>This link will expire in 1 hour.</p>
        <br>
        <p>If you didn't create an account, please ignore this email.</p>
      </body>
    </html>
    """
    
    part = MIMEText(html, 'html')
    msg.attach(part)
    
    try:
        with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
            server.starttls()
            server.login(EMAIL_ADDRESS, EMAIL_PASSWORD)
            server.send_message(msg)
        return True
    except Exception as e:
        print(f"Failed to send email: {e}")
        return False

# Login required decorator
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash('Please login to access this page', 'error')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

# Helper functions (same as before)
def get_month_year(date_str):
    if date_str:
        parts = date_str.split('-')
        if len(parts) == 3:
            return f"{parts[1]}-{parts[2]}"
    return None

def calculate_pace(distance_km, time_str):
    if not distance_km or distance_km <= 0 or not time_str:
        return None
    try:
        time_parts = time_str.split(':')
        if len(time_parts) == 3:
            hours, minutes, seconds = map(int, time_parts)
            total_minutes = hours * 60 + minutes + seconds / 60
        elif len(time_parts) == 2:
            minutes, seconds = map(int, time_parts)
            total_minutes = minutes + seconds / 60
        else:
            return None
        pace_minutes = total_minutes / distance_km
        pace_mins = int(pace_minutes)
        pace_secs = int((pace_minutes - pace_mins) * 60)
        return f"{pace_mins:02d}:{pace_secs:02d}"
    except (ValueError, ZeroDivisionError):
        return None

def get_valid_strava_token():
    if 'user_id' not in session:
        return None
    token_record = db.session.query(StravaToken).filter_by(user_id=session['user_id']).first()
    if not token_record:
        return None
    current_time = dt.datetime.now().timestamp()
    if current_time >= token_record.expires_at:
        response = requests.post(
            "https://www.strava.com/oauth/token",
            data={
                "client_id": STRAVA_CLIENT_ID,
                "client_secret": STRAVA_CLIENT_SECRET,
                "grant_type": "refresh_token",
                "refresh_token": token_record.refresh_token
            }
        )
        if response.status_code == 200:
            data = response.json()
            token_record.access_token = data["access_token"]
            token_record.refresh_token = data["refresh_token"]
            token_record.expires_at = data["expires_at"]
            db.session.commit()
            return data["access_token"]
        else:
            return None
    return token_record.access_token

def fetch_strava_activities():
    access_token = get_valid_strava_token()
    if not access_token:
        return None
    headers = {"Authorization": f"Bearer {access_token}"}
    response = requests.get(
        "https://www.strava.com/api/v3/athlete/activities",
        headers=headers,
        params={"per_page": 30}
    )
    if response.status_code == 200:
        return response.json()
    else:
        return None

def import_strava_activity(activity):
    existing = db.session.query(Athlete_Data).filter_by(strava_id=activity['id']).first()
    if existing:
        return False
    activity_date = dt.datetime.strptime(activity['start_date_local'], "%Y-%m-%dT%H:%M:%SZ")
    date_str = activity_date.strftime("%d-%m-%Y")
    month_year_str = activity_date.strftime("%m-%Y")
    distance = activity['distance'] / 1000
    moving_time = activity['moving_time']
    hours = moving_time // 3600
    minutes = (moving_time % 3600) // 60
    seconds = moving_time % 60
    time_str = f"{hours:02d}:{minutes:02d}:{seconds:02d}"
    pace = calculate_pace(distance, time_str)
    activity_type_map = {
        'Run': 'Running',
        'Ride': 'Cycling',
        'Swim': 'Swimming',
        'Walk': 'Walking',
        'WeightTraining': 'Gym'
    }
    activity_type = activity_type_map.get(activity['type'], activity['type'])
    new_record = Athlete_Data(
        user_id=session['user_id'],
        date=date_str,
        activity_type=activity_type,
        distance=round(distance, 2),
        time=time_str,
        pace=pace,
        calories=activity.get('calories'),
        month_year=month_year_str,
        strava_id=activity['id']
    )
    db.session.add(new_record)
    db.session.commit()
    return True

# Authentication Routes
@app.route('/login', methods=['GET', 'POST'])
def login():
    if 'user_id' in session:
        return redirect(url_for('home'))
    
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        
        user = db.session.query(User).filter_by(email=email).first()
        
        if user and user.password_hash and check_password_hash(user.password_hash, password):
            if not user.email_verified:
                flash('Please verify your email before logging in', 'error')
                return redirect(url_for('login'))
            session['user_id'] = user.id
            session['username'] = user.username or user.email
            flash('Login successful!', 'success')
            return redirect(url_for('home'))
        else:
            flash('Invalid email or password', 'error')
    
    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if 'user_id' in session:
        return redirect(url_for('home'))
    
    if request.method == 'POST':
        email = request.form.get('email')
        username = request.form.get('username')
        password = request.form.get('password')
        confirm_password = request.form.get('confirm_password')
        
        if password != confirm_password:
            flash('Passwords do not match', 'error')
            return redirect(url_for('register'))
        
        existing_user = db.session.query(User).filter_by(email=email).first()
        if existing_user:
            flash('Email already registered', 'error')
            return redirect(url_for('register'))
        
        new_user = User(
            email=email,
            username=username,
            password_hash=generate_password_hash(password),
            email_verified=False
        )
        db.session.add(new_user)
        db.session.commit()
        
        # Send verification email
        token = generate_verification_token(email)
        if send_verification_email(email, token):
            flash('Registration successful! Please check your email to verify your account.', 'success')
        else:
            flash('Registration successful! However, verification email could not be sent. Please contact support.', 'warning')
        
        return redirect(url_for('login'))
    
    return render_template('register.html')

@app.route('/verify-email/<token>')
def verify_email(token):
    email = verify_token(token)
    if not email:
        flash('Invalid or expired verification link', 'error')
        return redirect(url_for('login'))
    
    user = db.session.query(User).filter_by(email=email).first()
    if user:
        user.email_verified = True
        db.session.commit()
        flash('Email verified successfully! You can now login.', 'success')
    else:
        flash('User not found', 'error')
    
    return redirect(url_for('login'))

@app.route('/login/google')
def google_login():
    # redirect_uri = url_for('google_callback', _external=True)
    redirect_uri = "https://web-production-289c2.up.railway.app/callback/google"
    return google.authorize_redirect(redirect_uri)

@app.route('/callback/google')
def google_callback():
    token = google.authorize_access_token()
    user_info = token.get('userinfo')
    
    email = user_info.get('email')
    name = user_info.get('name')
    oauth_id = user_info.get('sub')
    
    user = db.session.query(User).filter_by(email=email).first()
    if not user:
        user = User(
            email=email,
            username=name,
            oauth_provider='google',
            oauth_id=oauth_id,
            email_verified=True  # OAuth emails are pre-verified
        )
        db.session.add(user)
        db.session.commit()
    
    session['user_id'] = user.id
    session['username'] = user.username or user.email
    flash('Login successful!', 'success')
    return redirect(url_for('home'))

@app.before_request
def force_https_in_production():
    if request.headers.get('X-Forwarded-Proto', 'http') == 'http':
        url = request.url.replace('http://', 'https://', 1)
        return redirect(url, code=301)

@app.route('/login/github')
def github_login():
    redirect_uri = url_for('github_callback', _external=True)
    return github.authorize_redirect(redirect_uri)

@app.route('/callback/github')
def github_callback():
    token = github.authorize_access_token()
    resp = github.get('user', token=token)
    user_info = resp.json()
    
    email = user_info.get('email')
    if not email:
        # GitHub might not return email, fetch from emails endpoint
        emails_resp = github.get('user/emails', token=token)
        emails = emails_resp.json()
        for email_obj in emails:
            if email_obj.get('primary'):
                email = email_obj.get('email')
                break
    
    name = user_info.get('name') or user_info.get('login')
    oauth_id = str(user_info.get('id'))
    
    user = db.session.query(User).filter_by(email=email).first()
    if not user:
        user = User(
            email=email,
            username=name,
            oauth_provider='github',
            oauth_id=oauth_id,
            email_verified=True
        )
        db.session.add(user)
        db.session.commit()
    
    session['user_id'] = user.id
    session['username'] = user.username or user.email
    flash('Login successful!', 'success')
    return redirect(url_for('home'))

@app.route('/logout')
def logout():
    session.clear()
    flash('Logged out successfully', 'success')
    return redirect(url_for('login'))

# Protected Routes
@app.route('/')
@login_required
def home():
    strava_connected = db.session.query(StravaToken).filter_by(user_id=session['user_id']).first() is not None
    
    result = db.session.execute(
        db.select(Athlete_Data)
        .filter_by(user_id=session['user_id'])
        .order_by(Athlete_Data.date.desc(), Athlete_Data.id.desc())
    )
    athlete_data = list(result.scalars())
    
    monthly_data = defaultdict(list)
    for record in athlete_data:
        if record.month_year:
            monthly_data[record.month_year].append(record)
    
    monthly_totals = {}
    for month, records in monthly_data.items():
        total_distance = sum((r.distance or 0.0) for r in records)
        total_calories = sum((r.calories or 0.0) for r in records)
        monthly_totals[month] = {'distance': total_distance, 'calories': total_calories}
    
    sorted_months = sorted(monthly_data.keys(), key=lambda x: dt.datetime.strptime(x, "%m-%Y"), reverse=True)
    total_distance = sum((m.distance or 0.0) for m in athlete_data)
    total_calories = sum((m.calories or 0.0) for m in athlete_data)
    
    return render_template("index.html", 
                         monthly_data=monthly_data, 
                         sorted_months=sorted_months,
                         monthly_totals=monthly_totals,
                         total_distance=total_distance,
                         total_calories=total_calories,
                         strava_connected=strava_connected,
                         username=session.get('username'))

@app.route('/strava/connect')
@login_required
def strava_connect():
    if not STRAVA_CLIENT_ID:
        flash("Strava API credentials not configured", "error")
        return redirect(url_for('home'))
    auth_url = (
        f"https://www.strava.com/oauth/authorize"
        f"?client_id={STRAVA_CLIENT_ID}"
        f"&redirect_uri={STRAVA_REDIRECT_URI}"
        f"&response_type=code"
        f"&scope=activity:read_all"
    )
    return redirect(auth_url)

@app.route('/strava/callback')
@login_required
def strava_callback():
    code = request.args.get('code')
    if not code:
        flash("Authorization failed", "error")
        return redirect(url_for('home'))
    response = requests.post(
        "https://www.strava.com/oauth/token",
        data={
            "client_id": STRAVA_CLIENT_ID,
            "client_secret": STRAVA_CLIENT_SECRET,
            "code": code,
            "grant_type": "authorization_code"
        }
    )
    if response.status_code == 200:
        data = response.json()
        token_record = db.session.query(StravaToken).filter_by(user_id=session['user_id']).first()
        if token_record:
            token_record.access_token = data["access_token"]
            token_record.refresh_token = data["refresh_token"]
            token_record.expires_at = data["expires_at"]
            token_record.athlete_id = data["athlete"]["id"]
        else:
            token_record = StravaToken(
                user_id=session['user_id'],
                access_token=data["access_token"],
                refresh_token=data["refresh_token"],
                expires_at=data["expires_at"],
                athlete_id=data["athlete"]["id"]
            )
            db.session.add(token_record)
        db.session.commit()
        flash("Strava connected successfully!", "success")
    else:
        flash("Failed to connect to Strava", "error")
    return redirect(url_for('home'))

@app.route('/strava/import')
@login_required
def strava_import():
    activities = fetch_strava_activities()
    if not activities:
        flash("Failed to fetch Strava activities. Please reconnect.", "error")
        return redirect(url_for('home'))
    imported_count = 0
    for activity in activities:
        if import_strava_activity(activity):
            imported_count += 1
    if imported_count > 0:
        flash(f"Successfully imported {imported_count} activities from Strava!", "success")
    else:
        flash("No new activities to import", "info")
    return redirect(url_for('home'))

@app.route('/strava/disconnect')
@login_required
def strava_disconnect():
    token_record = db.session.query(StravaToken).filter_by(user_id=session['user_id']).first()
    if token_record:
        db.session.delete(token_record)
        db.session.commit()
        flash("Strava disconnected successfully", "success")
    return redirect(url_for('home'))

@app.route("/edit", methods=["GET", "POST"])
@login_required
def edit():
    if request.method == "POST":
        athlete_id = int(request.form.get("id"))
        athlete_record = db.get_or_404(Athlete_Data, athlete_id)
        if athlete_record.user_id != session['user_id']:
            flash("Unauthorized access", "error")
            return redirect(url_for('home'))
        new_date_raw = request.form.get("date")
        if new_date_raw:
            try:
                parsed = dt.datetime.strptime(new_date_raw, "%Y-%m-%d")
                athlete_record.date = parsed.strftime("%d-%m-%Y")
                athlete_record.month_year = parsed.strftime("%m-%Y")
            except (ValueError, TypeError):
                pass
        athlete_record.activity_type = request.form.get("activity_type", "Running")
        try:
            athlete_record.distance = float(request.form.get("distance", 0))
        except (ValueError, TypeError):
            athlete_record.distance = 0
        athlete_record.time = request.form.get("time", "00:00:00")
        athlete_record.pace = calculate_pace(athlete_record.distance, athlete_record.time)
        try:
            athlete_record.calories = float(request.form.get("calories", 0))
        except (ValueError, TypeError):
            athlete_record.calories = 0
        db.session.commit()
        flash("Record updated successfully!", "success")
        return redirect(url_for("home"))
    else:
        athlete_id = request.args.get("id")
        athlete_record = db.get_or_404(Athlete_Data, int(athlete_id))
        if athlete_record.user_id != session['user_id']:
            flash("Unauthorized access", "error")
            return redirect(url_for('home'))
        return render_template("edit.html", data=athlete_record)

@app.route('/delete')
@login_required
def delete_data():
    athlete_id = request.args.get('id')
    athlete_to_delete = db.get_or_404(Athlete_Data, int(athlete_id))
    if athlete_to_delete.user_id != session['user_id']:
        flash("Unauthorized access", "error")
        return redirect(url_for('home'))
    db.session.delete(athlete_to_delete)
    db.session.commit()
    flash("Record deleted successfully!", "success")
    return redirect(url_for('home'))

@app.route("/add", methods=["GET", "POST"])
@login_required
def add():
    if request.method == "POST":
        activity_type = request.form.get("activity_type", "Running")
        try:
            distance = float(request.form.get("distance", 0))
        except (ValueError, TypeError):
            distance = 0
        time_str = request.form.get("time", "00:00:00")
        pace = calculate_pace(distance, time_str)
        try:
            calories = float(request.form.get("calories", 0))
        except (ValueError, TypeError):
            calories = 0
        date_raw = request.form.get("date")
        if date_raw:
            try:
                parsed = dt.datetime.strptime(date_raw, "%Y-%m-%d")
                date_str = parsed.strftime("%d-%m-%Y")
                month_year_str = parsed.strftime("%m-%Y")
            except (ValueError, TypeError):
                now = dt.datetime.now()
                date_str = now.strftime("%d-%m-%Y")
                month_year_str = now.strftime("%m-%Y")
        else:
            now = dt.datetime.now()
            date_str = now.strftime("%d-%m-%Y")
            month_year_str = now.strftime("%m-%Y")
        new_record = Athlete_Data(
            user_id=session['user_id'],
            date=date_str,
            activity_type=activity_type,
            distance=distance,
            time=time_str,
            pace=pace,
            calories=calories,
            month_year=month_year_str
        )
        db.session.add(new_record)
        db.session.commit()
        flash("Record added successfully!", "success")
        return redirect(url_for('home'))
    else:
        return render_template("add.html")

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5001))
    app.run(host='0.0.0.0', port=port, debug=False)