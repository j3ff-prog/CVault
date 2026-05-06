# CVault — Setup Instructions
# Run these commands in your terminal exactly as written.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
 PART 1 — INSTALL PYTHON (if not already installed)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Check if Python is installed:
  python --version

If you get an error, download Python from https://python.org/downloads
Install Python 3.11 or newer. During install, CHECK the box that says
"Add Python to PATH".

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
 PART 2 — SET UP THE PROJECT
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

1. Open a terminal (Command Prompt or PowerShell on Windows,
   Terminal on Mac/Linux).

2. Navigate to where you want to put the project:
   cd Desktop

3. Create the project folder (if you haven't already):
   mkdir cvault-backend
   cd cvault-backend

4. Create a virtual environment (keeps your packages separate):
   python -m venv venv

5. Activate the virtual environment:

   On Windows:
     venv\Scripts\activate

   On Mac/Linux:
     source venv/bin/activate

   You should see (venv) appear at the start of your terminal line.
   If you close the terminal, you need to run this activate command again.

6. Install all dependencies:
   pip install -r requirements.txt

   This installs Flask, Gemini, PyMuPDF, python-docx and all other
   required packages. It may take 1-2 minutes.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
 PART 3 — CONFIGURE YOUR ENVIRONMENT
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

1. Copy the example env file:

   On Windows:
     copy .env.example .env

   On Mac/Linux:
     cp .env.example .env

2. Open .env in any text editor (Notepad, VS Code, etc.)
   and fill in your values:

   GEMINI_API_KEY
   → Go to https://aistudio.google.com/app/apikey
   → Click "Create API Key"
   → Copy and paste it in

   PAYSTACK_SECRET_KEY and PAYSTACK_PUBLIC_KEY
   → Go to https://dashboard.paystack.com/#/settings/developer
   → Copy your secret key and public key

   GMAIL_APP_PASSWORD
   → Go to https://myaccount.google.com
   → Click Security
   → Turn on 2-Step Verification (if not already on)
   → Search "App passwords" in the search bar at the top
   → Create a new one, name it "CVault"
   → Copy the 16-character password (e.g. abcd efgh ijkl mnop)
   → Paste it WITHOUT spaces: abcdefghijklmnop

   FRONTEND_URL
   → Leave this as http://localhost:5000 for now
   → You'll update it to your Render URL after deploying

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
 PART 4 — ADD YOUR FRONTEND FILES
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Create a 'static' folder inside cvault-backend:

  mkdir static

Copy ALL your HTML files into this static folder:
  - index.html
  - cvault-login.html
  - cvault-signup.html
  - cvault-dashboard.html
  - cvault-payment.html
  - cvault-payment-success.html
  - cvault-analysis.html
  - cvault-forgot-password.html
  - cvault-reset-password.html

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
 PART 5 — RUN LOCALLY
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Make sure your virtual environment is active (you see (venv)),
then run:

  python app.py

You should see:
  [DB] Tables initialised.
  [CVault] Running on http://localhost:5000

Open your browser and go to:
  http://localhost:5000

You should see your landing page (index.html).

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
 PART 6 — CONNECT FRONTEND TO BACKEND
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

In your HTML files, update the API calls to hit your backend.
Add this constant near the top of each page's <script> tag:

  const API = 'http://localhost:5000';   // local dev
  // const API = 'https://cvault.onrender.com';  // production (uncomment when deployed)

Example — Login page:
  const res = await fetch(`${API}/api/auth/login`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ email, password })
  });
  const data = await res.json();
  if (res.ok) {
    localStorage.setItem('cvault_token', data.token);
    localStorage.setItem('cvault_user', JSON.stringify(data.user));
    localStorage.setItem('cvault_credits', JSON.stringify(data.credits));
    window.location.href = '/cvault-dashboard.html';
  }

Example — Analysis page (generate):
  const token = localStorage.getItem('cvault_token');
  const form = new FormData();
  form.append('cvFile', fileInput.files[0]);  // or cvText
  form.append('jobDescription', jobText);
  const res = await fetch(`${API}/api/generate`, {
    method: 'POST',
    headers: { 'Authorization': `Bearer ${token}` },
    body: form
  });

Example — Payment success page (verify after Paystack redirect):
  const params = new URLSearchParams(window.location.search);
  const reference = params.get('reference');
  const token = localStorage.getItem('cvault_token');
  const res = await fetch(`${API}/api/payments/verify`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'Authorization': `Bearer ${token}`
    },
    body: JSON.stringify({ reference })
  });
  const data = await res.json();
  // data.credits now has the real updated balance

IMPORTANT — Use localStorage instead of sessionStorage in
your HTML files so login persists across page refreshes.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
 PART 7 — DEPLOY TO RENDER
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

1. Install Git if you don't have it:
   https://git-scm.com/downloads

2. Create a GitHub account if you don't have one:
   https://github.com

3. Create a new GitHub repository (name it cvault-backend),
   make it PRIVATE.

4. In your terminal (inside cvault-backend folder):
   git init
   git add .
   git commit -m "CVault backend initial commit"
   git remote add origin https://github.com/YOUR_GITHUB_USERNAME/cvault-backend.git
   git push -u origin main

5. Go to https://render.com and sign up (free)

6. Click New → Web Service → Connect GitHub → select cvault-backend

7. Render detects render.yaml automatically. Click Deploy.

8. In your Render dashboard → Environment, add these variables
   (the ones marked sync:false in render.yaml):
   - GEMINI_API_KEY
   - PAYSTACK_SECRET_KEY
   - PAYSTACK_PUBLIC_KEY
   - GMAIL_USER         → Jeff.006760@gmail.com
   - GMAIL_APP_PASSWORD → your 16-char app password
   - FRONTEND_URL       → https://cvault.onrender.com (your Render URL)

9. Go to Render → your service → Disks → Add Disk:
   - Mount path: /var/data
   - Size: 1 GB

10. Redeploy. Your site will be live at:
    https://cvault.onrender.com

11. Set Paystack webhook URL in your Paystack dashboard:
    → Settings → API Keys & Webhooks → Webhook URL:
    https://cvault.onrender.com/api/payments/webhook

12. Update your HTML files:
    Change: const API = 'http://localhost:5000';
    To:     const API = 'https://cvault.onrender.com';

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
 OWNER ACCESS
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

When you log in with Jeff.006760@gmail.com, the backend
automatically gives your account unlimited credits that
never expire. You don't need to pay anything — just log in
and you have full access forever.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
 COMMON ERRORS AND FIXES
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

"ModuleNotFoundError: No module named 'flask'"
→ Your virtual environment is not active.
→ Run: venv\Scripts\activate  (Windows)
→ Run: source venv/bin/activate  (Mac/Linux)
→ Then: pip install -r requirements.txt

"Address already in use"
→ Something is already running on port 5000.
→ Run: python app.py  -- port 5001
→ Or kill the other process.

"GEMINI_API_KEY not set"
→ Your .env file is missing or the key is wrong.
→ Check that .env exists in the cvault-backend folder.

Gemini gives "JSON parse error"
→ This is rare. Usually means the AI responded with extra text.
→ The code already handles this — just retry the request.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
