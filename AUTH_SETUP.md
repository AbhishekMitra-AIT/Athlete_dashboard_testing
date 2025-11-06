# Authentication System Setup Guide

## 🔐 Overview

This guide will help you set up the complete authentication system with:
- ✅ Email/Password registration with email verification
- ✅ Google OAuth login
- ✅ GitHub OAuth login
- ✅ User-specific data isolation
- ✅ Session management

---

## 📋 Prerequisites

1. Python 3.8+
2. Gmail account (for sending verification emails)
3. Google Cloud account (for Google OAuth)
4. GitHub account (for GitHub OAuth)

---

## 🚀 Step-by-Step Setup

### Step 1: Update Requirements

Add to `requirements.txt`:
```
Flask==3.0.3
Flask-SQLAlchemy==3.1.1
Werkzeug==3.0.6
gunicorn==21.2.0
requests==2.31.0
python-dotenv==1.0.0
Authlib==1.3.0
itsdangerous==2.2.0
```

Install:
```bash
pip install -r requirements.txt
```

### Step 2: Set Up Google OAuth

1. **Go to Google Cloud Console**: https://console.cloud.google.com/
2. **Create a new project** or select existing
3. **Enable Google+ API**:
   - Go to "APIs & Services" → "Library"
   - Search for "Google+ API" and enable it
4. **Create OAuth Credentials**:
   - Go to "APIs & Services" → "Credentials"
   - Click "Create Credentials" → "OAuth client ID"
   - Application type: "Web application"
   - Name: "Athlete Dashboard"
   - **Authorized redirect URIs**:
     - `http://localhost:5000/callback/google` (for local)
     - `https://your-domain.com/callback/google` (for production)
5. **Copy your credentials**:
   - Client ID (203108127966-p95iflppu2jfsbd8fk4mnttnr6ocfonp.apps.googleusercontent.com)
   - Client Secret (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)

### Step 3: Set Up GitHub OAuth

1. **Go to GitHub Settings**: https://github.com/settings/developers
2. **Click "New OAuth App"**
3. **Fill in details**:
   - Application name: "Athlete Dashboard"
   - Homepage URL: `http://localhost:5000` (for local)
   - Authorization callback URL: `http://localhost:5000/callback/github`
4. **Register application**
5. **Copy your credentials**:
   - Client ID (Ov23liiGeoG4VDvUEPeF)
   - Client Secret (d5178407f79167f928cd0c9c4af7dbbdcddd3f1a)

### Step 4: Set Up Email for Verification

#### For Gmail:

**Option A: App Password (Recommended)**
1. Enable 2-Factor Authentication on your Google account
2. Go to: https://myaccount.google.com/apppasswords
3. Generate an app password for "Mail" (kkqi htkj kbhf pqqp) 
4. Use this password in your .env file

**Option B: Less Secure Apps (Not Recommended)**
1. Go to: https://myaccount.google.com/lesssecureapps
2. Turn on "Allow less secure apps"
3. Use your regular Gmail password

### Step 5: Configure Environment Variables

Create `.env` file:
```bash
# Flask
SECRET_KEY=your-super-secret-key-change-this

# Strava API
STRAVA_CLIENT_ID=your_strava_client_id
STRAVA_CLIENT_SECRET=your_strava_client_secret
STRAVA_REDIRECT_URI=http://localhost:5000/strava/callback

# Google OAuth
GOOGLE_CLIENT_ID=your-google-client-id.apps.googleusercontent.com
GOOGLE_CLIENT_SECRET=your-google-client-secret

# GitHub OAuth
GITHUB_CLIENT_ID=your-github-client-id
GITHUB_CLIENT_SECRET=your-github-client-secret

# Email Configuration
EMAIL_ADDRESS=your-email@gmail.com
EMAIL_PASSWORD=your-app-password-or-password
SMTP_SERVER=smtp.gmail.com
SMTP_PORT=587
```

### Step 6: Run Database Migration

```bash
python migrate_add_auth.py
```

This will:
- Create the `user` table
- Add `user_id` columns to existing tables
- Create a default user for existing data

### Step 7: Create Template Files

Create these files in `templates/` folder:
- `login.html` (use the provided template)
- `register.html` (use the provided template)

### Step 8: Update app.py

Replace your `app.py` with the new authentication-enabled version.

### Step 9: Test the Application

```bash
python app.py
```

Visit: http://localhost:5000/login

---

## 🧪 Testing the Features

### 1. Email Registration
1. Click "Sign Up"
2. Enter email, username, password
3. Check your email for verification link
4. Click verification link
5. Login with email and password

### 2. Google Login
1. Click "Google" button on login page
2. Authorize the application
3. You'll be automatically logged in

### 3. GitHub Login
1. Click "GitHub" button on login page
2. Authorize the application
3. You'll be automatically logged in

---

## 🔒 Security Best Practices

1. **Never commit .env file** - Add to .gitignore
2. **Use strong SECRET_KEY** - Generate with: `python -c "import secrets; print(secrets.token_hex(32))"`
3. **Enable HTTPS in production** - Use Railway, Heroku, or similar
4. **Use app passwords for Gmail** - More secure than regular passwords
5. **Regularly update dependencies** - Check for security updates

---

## 🌐 Production Deployment (Railway)

### Update Environment Variables in Railway:

1. Go to your Railway project
2. Settings → Variables
3. Add all environment variables from .env
4. **Update callback URLs**:
   ```
   STRAVA_REDIRECT_URI=https://your-app.railway.app/strava/callback
   ```

### Update OAuth Redirect URIs:

**Google Cloud Console:**
- Add: `https://your-app.railway.app/callback/google`

**GitHub OAuth Settings:**
- Update Homepage URL: `https://your-app.railway.app`
- Update Callback URL: `https://your-app.railway.app/callback/github`

---

## 🐛 Troubleshooting

### Issue: Email not sending

**Solution:**
- Check EMAIL_ADDRESS and EMAIL_PASSWORD in .env
- For Gmail, use App Password, not regular password
- Ensure "Less secure apps" is enabled OR use App Password

### Issue: OAuth redirect mismatch

**Solution:**
- Verify redirect URIs match exactly in OAuth provider settings
- Check for http vs https
- Check for trailing slashes

### Issue: "User not found" after OAuth login

**Solution:**
- OAuth providers might not return email
- For GitHub, ensure email is public in GitHub settings

### Issue: Session not persisting

**Solution:**
- Check SECRET_KEY is set in environment
- Clear browser cookies
- Restart Flask application

---

## 📚 Additional Resources

- **Google OAuth Documentation**: https://developers.google.com/identity/protocols/oauth2
- **GitHub OAuth Documentation**: https://docs.github.com/en/developers/apps/building-oauth-apps
- **Flask-Login Documentation**: https://flask-login.readthedocs.io/
- **Authlib Documentation**: https://docs.authlib.org/

---

## 🆘 Support

If you encounter issues:
1. Check the error messages in terminal
2. Verify all environment variables are set correctly
3. Check OAuth redirect URIs match exactly
4. Ensure email credentials are correct
5. Try clearing browser cache/cookies

---

## ✅ Checklist

Before deploying to production:

- [ ] All environment variables configured
- [ ] OAuth redirect URIs updated for production domain
- [ ] Email sending tested and working
- [ ] .env file added to .gitignore
- [ ] Strong SECRET_KEY generated
- [ ] Database migration completed successfully
- [ ] All authentication methods tested (email, Google, GitHub)
- [ ] HTTPS enabled in production
- [ ] Email verification working
- [ ] User data isolation verified