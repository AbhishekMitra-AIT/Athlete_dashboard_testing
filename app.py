from flask import Flask, render_template, request, redirect, url_for, session, flash
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy import Integer, String, Float
from werkzeug.security import generate_password_hash, check_password_hash
from functools import wraps
import datetime as dt
from collections import defaultdict
import requests
import os
from dotenv import load_dotenv
from authlib.integrations.flask_client import OAuth

load_dotenv()

class Base(DeclarativeBase):
    pass

db = SQLAlchemy(model_class=Base)
# Initialize Flask App
app = Flask(__name__)

# Configuration
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///athlete_data.db"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
app.secret_key = os.environ.get('FLASK_SECRET_KEY', 'super-secret-key')

# OAuth Configuration
app.config['GOOGLE_CLIENT_ID'] = os.environ.get('GOOGLE_CLIENT_ID')
app.config['GOOGLE_CLIENT_SECRET'] = os.environ.get('GOOGLE_CLIENT_SECRET')
app.config['GITHUB_CLIENT_ID'] = os.environ.get('GITHUB_CLIENT_ID')
app.config['GITHUB_CLIENT_SECRET'] = os.environ.get('GITHUB_CLIENT_SECRET')

db = SQLAlchemy(app)

# Initialize OAuth
oauth = OAuth(app)

# Register Google
google = oauth.register(
    name='google',
    client_id=app.config['GOOGLE_CLIENT_ID'],
    client_secret=app.config['GOOGLE_CLIENT_SECRET'],
    access_token_url='https://accounts.google.com/o/oauth2/token',
    access_token_params=None,
    authorize_url='https://accounts.google.com/o/oauth2/auth',
    authorize_params=None,
    api_base_url='https://www.googleapis.com/oauth2/v1/',
    client_kwargs={'scope': 'openid email profile'},
    server_metadata_url='https://accounts.google.com/.well-known/openid-configuration'
)

# Register GitHub
github = oauth.register(
    name='github',
    client_id=app.config['GITHUB_CLIENT_ID'],
    client_secret=app.config['GITHUB_CLIENT_SECRET'],
    access_token_url='https://github.com/login/oauth/access_token',
    access_token_params=None,
    authorize_url='https://github.com/login/oauth/authorize',
    authorize_params=None,
    api_base_url='https://api.github.com/',
    client_kwargs={'scope': 'user:email'}
)

# Strava API Configuration
STRAVA_CLIENT_ID = os.environ.get("STRAVA_CLIENT_ID")
STRAVA_CLIENT_SECRET = os.environ.get("STRAVA_CLIENT_SECRET")
STRAVA_REDIRECT_URI = os.environ.get("STRAVA_REDIRECT_URI", "http://localhost:5000/strava/callback")

db.init_app(app)

class Athlete_Data(db.Model):
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    date: Mapped[str] = mapped_column(String(250), nullable=True)
    activity_type: Mapped[str] = mapped_column(String(100), nullable=True)
    distance: Mapped[float] = mapped_column(Float, nullable=True)
    time: Mapped[str] = mapped_column(String(50), nullable=True)
    pace: Mapped[str] = mapped_column(String(50), nullable=True)
    calories: Mapped[float] = mapped_column(Float, nullable=True)
    month_year: Mapped[str] = mapped_column(String(50), nullable=True)
    strava_id: Mapped[int] = mapped_column(Integer, nullable=True, unique=True)  # Track Strava activity ID

class StravaToken(db.Model):
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    access_token: Mapped[str] = mapped_column(String(500), nullable=False)
    refresh_token: Mapped[str] = mapped_column(String(500), nullable=False)
    expires_at: Mapped[int] = mapped_column(Integer, nullable=False)
    athlete_id: Mapped[int] = mapped_column(Integer, nullable=False)

class User(db.Model):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), unique=True, nullable=False)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(256))
    google_id = db.Column(db.String(128), unique=True, nullable=True)
    github_id = db.Column(db.String(128), unique=True, nullable=True)
    created_at = db.Column(db.DateTime, default=dt.datetime.utcnow)
    is_active = db.Column(db.Boolean, default=True)

    def set_password(self, password):
        """Hash and set password"""
        self.password_hash = generate_password_hash(password)
    
    def check_password(self, password):
        """Check if provided password matches hash"""
        return check_password_hash(self.password_hash, password)
    
    def is_authenticated(self):
        return True
    
    def is_active_user(self):
        return self.is_active == 1
    
    def is_anonymous(self):
        return False
    
    def get_id(self):
        return str(self.id)

with app.app_context():
    db.create_all()

def get_month_year(date_str):
    """Extract MM-YYYY from DD-MM-YYYY date string"""
    if date_str:
        parts = date_str.split('-')
        if len(parts) == 3:
            return f"{parts[1]}-{parts[2]}"
def login_required(f):
    """Decorator to require login for routes"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash('Please log in to access this page.', 'warning')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

def get_current_user():
    """Get current logged-in user"""
    if 'user_id' in session:
        return db.session.get(User, int(session['user_id']))
    return None

def calculate_pace(distance_km, time_str):
    """Calculate pace in MM:SS format from distance and time"""
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
    """Get a valid Strava access token, refreshing if necessary"""
    token_record = db.session.query(StravaToken).first()
    
    if not token_record:
        return None
    
    # Check if token is expired
    current_time = dt.datetime.now().timestamp()
    if current_time >= token_record.expires_at:
        # Refresh the token
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
    """Fetch activities from Strava API"""
    access_token = get_valid_strava_token()
    
    if not access_token:
        return None
    
    headers = {"Authorization": f"Bearer {access_token}"}
    
    # Fetch activities (last 30 activities)
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
    """Import a single Strava activity into the database"""
    # Check if activity already exists
    existing = db.session.query(Athlete_Data).filter_by(strava_id=activity['id']).first()
    if existing:
        return False  # Already imported
    
    # Parse activity data
    activity_date = dt.datetime.strptime(activity['start_date_local'], "%Y-%m-%dT%H:%M:%SZ")
    date_str = activity_date.strftime("%d-%m-%Y")
    month_year_str = activity_date.strftime("%m-%Y")
    
    # Convert distance from meters to km
    distance = activity['distance'] / 1000
    
    # Convert moving time to HH:MM:SS
    moving_time = activity['moving_time']
    hours = moving_time // 3600
    minutes = (moving_time % 3600) // 60
    seconds = moving_time % 60
    time_str = f"{hours:02d}:{minutes:02d}:{seconds:02d}"
    
    # Calculate pace
    pace = calculate_pace(distance, time_str)
    
    # Activity type mapping
    activity_type_map = {
        'Run': 'Running',
        'Ride': 'Cycling',
        'Swim': 'Swimming',
        'Walk': 'Walking',
        'WeightTraining': 'Gym'
    }
    activity_type = activity_type_map.get(activity['type'], activity['type'])
    
    # Create new record
    new_record = Athlete_Data(
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

@app.route('/')
@login_required
def home():
    # Check if Strava is connected
    strava_connected = db.session.query(StravaToken).first() is not None
    current_user = get_current_user()
    
    with app.app_context():
        result = db.session.execute(db.select(Athlete_Data).order_by(Athlete_Data.date.desc(), Athlete_Data.id.desc()))
        athlete_data = list(result.scalars())
        
        monthly_data = defaultdict(list)
        for record in athlete_data:
            if record.month_year:
                monthly_data[record.month_year].append(record)
        
        monthly_totals = {}
        for month, records in monthly_data.items():
            total_distance = sum((r.distance or 0.0) for r in records)
            total_calories = sum((r.calories or 0.0) for r in records)
            monthly_totals[month] = {
                'distance': total_distance,
                'calories': total_calories
            }
        
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
                         current_user=current_user)

@app.route('/strava/connect')
@login_required
def strava_connect():
    """Redirect user to Strava authorization page"""
    if not STRAVA_CLIENT_ID:
        flash("Strava API credentials not configured", "error")
    @app.route('/logout')
def logout():
    """Log out the current user"""
    session.pop('user_id', None)
    flash('You have been logged out successfully.', 'success')
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    """Handle user login"""
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        
        if not email or not password:
            flash('Please provide both email and password.', 'error')
            return render_template('login.html')
        
        # Find user by email
        user = db.session.query(User).filter_by(email=email).first()
        
        if user and user.check_password(password):
            session['user_id'] = user.id
            flash('Welcome back!', 'success')
            return redirect(url_for('home'))
        else:
            flash('Invalid email or password.', 'error')
    
    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    """Handle user registration"""
    if request.method == 'POST':
        email = request.form.get('email')
        username = request.form.get('username')
        password = request.form.get('password')
        confirm_password = request.form.get('confirm_password')
        
        if not email or not username or not password:
            flash('Please fill in all fields.', 'error')
            return render_template('register.html')
        
        if password != confirm_password:
            flash('Passwords do not match.', 'error')
            return render_template('register.html')
        
        # Check if user already exists
        existing_email = db.session.query(User).filter_by(email=email).first()
        existing_username = db.session.query(User).filter_by(username=username).first()
        
        if existing_email:
            flash('Email already registered.', 'error')
            return render_template('register.html')
        
        if existing_username:
            flash('Username already taken.', 'error')
            return render_template('register.html')
        
        # Create new user
        new_user = User(email=email, username=username)
        new_user.set_password(password)
        
        db.session.add(new_user)
        db.session.commit()
        
        flash('Account created successfully! Please log in.', 'success')
        return redirect(url_for('login'))
    
    return render_template('register.html')

@app.route('/login/google')
def google_login():
    redirect_uri = url_for('google_authorize', _external=True)
    return google.authorize_redirect(redirect_uri)

@app.route('/login/google/authorize')
def google_authorize():
    token = google.authorize_access_token()
    user_info = google.get('userinfo').json()
    google_id = user_info['id']
    email = user_info['email']
    
    user = User.query.filter_by(google_id=google_id).first()
    if not user:
        user = User.query.filter_by(email=email).first()
        if not user:
            user = User(email=email, username=email.split('@')[0], google_id=google_id)
            db.session.add(user)
            db.session.commit()
        else:
            user.google_id = google_id
            db.session.commit()
            
    session['user_id'] = user.id
    flash('Logged in with Google successfully!', 'success')
    return redirect(url_for('home'))

@app.route('/login/github')
def github_login():
    redirect_uri = url_for('github_authorize', _external=True)
    return github.authorize_redirect(redirect_uri)

@app.route('/login/github/authorize')
def github_authorize():
    token = github.authorize_access_token()
    user_info = github.get('user').json()
    github_id = user_info['id']
    email = user_info.get('email')
    
    if not email:
        flash('GitHub email not public. Please make it public to log in.', 'error')
        return redirect(url_for('login'))

    user = User.query.filter_by(github_id=github_id).first()
    if not user:
        user = User.query.filter_by(email=email).first()
        if not user:
            user = User(email=email, username=user_info.get('login'), github_id=github_id)
            db.session.add(user)
            db.session.commit()
        else:
            user.github_id = github_id
            db.session.commit()
            
    session['user_id'] = user.id
    flash('Logged in with GitHub successfully!', 'success')
    return redirect(url_for('home'))

@app.route('/strava/callback')
def strava_callback():
    """Handle Strava OAuth callback"""
    code = request.args.get('code')
    
    if not code:
        flash("Authorization failed", "error")
        return redirect(url_for('home'))
    
    # Exchange code for tokens
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
        
        # Store tokens in database
        token_record = db.session.query(StravaToken).first()
        if token_record:
            token_record.access_token = data["access_token"]
            token_record.refresh_token = data["refresh_token"]
            token_record.expires_at = data["expires_at"]
            token_record.athlete_id = data["athlete"]["id"]
        else:
            token_record = StravaToken(
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
    """Import activities from Strava"""
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
    """Disconnect Strava account"""
    token_record = db.session.query(StravaToken).first()
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
        return render_template("edit.html", data=athlete_record)

@app.route('/delete')
@login_required
def delete_data():
    athlete_id = request.args.get('id')
    athlete_to_delete = db.get_or_404(Athlete_Data, int(athlete_id))
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

        with app.app_context():
            new_record = Athlete_Data(
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
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port, debug=False)