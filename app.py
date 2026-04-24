from flask import Flask, render_template, request, redirect, session, jsonify
import sqlite3
import requests
import os
from dotenv import load_dotenv

# Load env
load_dotenv()

app = Flask(__name__)
app.secret_key = "secret123"

YOUTUBE_API_KEY = os.getenv("YOUTUBE_API_KEY")

# ---------- DATABASE ----------
def init_db():
    conn = sqlite3.connect("database.db")
    cur = conn.cursor()
    cur.execute("CREATE TABLE IF NOT EXISTS users (id INTEGER PRIMARY KEY, username TEXT, password TEXT)")
    cur.execute("CREATE TABLE IF NOT EXISTS marks (id INTEGER PRIMARY KEY, username TEXT, subject TEXT, score INTEGER)")
    conn.commit()
    conn.close()

init_db()

# ---------- AUTH ----------
@app.route('/', methods=['GET','POST'])
def login():
    if request.method == 'POST':
        user = request.form['username']
        pwd = request.form['password']

        conn = sqlite3.connect("database.db")
        cur = conn.cursor()
        cur.execute("SELECT * FROM users WHERE username=? AND password=?", (user, pwd))
        if cur.fetchone():
            session['user'] = user
            return redirect('/dashboard')

    return render_template("login.html")

@app.route('/signup', methods=['GET','POST'])
def signup():
    if request.method == 'POST':
        user = request.form['username']
        pwd = request.form['password']

        conn = sqlite3.connect("database.db")
        cur = conn.cursor()
        cur.execute("INSERT INTO users (username,password) VALUES (?,?)", (user,pwd))
        conn.commit()
        conn.close()
        return redirect('/')

    return render_template("signup.html")

# ---------- DASHBOARD ----------
@app.route('/dashboard')
def dashboard():
    if 'user' not in session:
        return redirect('/')

    user = session['user']
    conn = sqlite3.connect("database.db")
    cur = conn.cursor()
    cur.execute("SELECT subject, score FROM marks WHERE username=?", (user,))
    data = cur.fetchall()
    conn.close()

    subjects = [r[0] for r in data]
    scores = [r[1] for r in data]

    avg = sum(scores)/len(scores) if scores else 0

    return render_template(
        "dashboard.html",
        data=data,
        subjects=subjects,
        scores=scores,
        avg=round(avg,2)
    )

# ---------- ADD MARKS ----------
@app.route('/add_marks', methods=['POST'])
def add_marks():
    subject = request.form['subject']
    score = request.form['score']
    user = session['user']

    conn = sqlite3.connect("database.db")
    cur = conn.cursor()
    cur.execute("INSERT INTO marks (username, subject, score) VALUES (?, ?, ?)", (user, subject, score))
    conn.commit()
    conn.close()

    return redirect('/dashboard')

# ---------- YOUTUBE ----------
def get_videos(query):
    try:
        url = "https://www.googleapis.com/youtube/v3/search"
        params = {
            "part": "snippet",
            "q": query,
            "key": YOUTUBE_API_KEY,
            "maxResults": 6,
            "type": "video"
        }

        res = requests.get(url, params=params).json()

        videos = []
        for item in res.get("items", []):
            title = item["snippet"]["title"].lower()

            if "short" in title:
                continue

            vid = item["id"]["videoId"]
            videos.append({
                "url": f"https://www.youtube.com/embed/{vid}",
                "title": item["snippet"]["title"]
            })

        return videos[:3]
    except Exception as e:
        print("YT ERROR:", e)
        return []

# ---------- CHAT ----------
@app.route('/chat', methods=['POST'])
def chat():
    try:
        msg = request.json.get("message", "")

        # ---------- AI RESPONSE ----------
        prompt = f"""
Answer properly.

Question: {msg}

- Numerical → solve directly with final answer
- Programming → give logic/code
- Theory → short explanation
- If videos requested → say "videos are shown below"

Give only the answer:
"""

        response = requests.post(
            "http://127.0.0.1:11434/api/generate",
            json={
                "model": "phi:latest",
                "prompt": prompt,
                "stream": False,
                "options": {
                    "num_predict": 80,
                    "temperature": 0.2
                }
            },
            timeout=90
        )

        reply = response.json().get("response", "").strip()

        # ---------- VIDEO LOGIC ----------
        videos = []
        if any(w in msg.lower() for w in ["video", "learn", "tutorial", "course"]):
            query = msg + " full tutorial"
            print("QUERY:", query)

            videos = get_videos(query)
            print("VIDEOS:", videos)

        return jsonify({"reply": reply, "videos": videos})

    except Exception as e:
        print("ERROR:", e)
        return jsonify({
            "reply": "⚠️ AI error. Try again.",
            "videos": []
        })

# ---------- RUN ----------
if __name__ == "__main__":
    app.run(debug=True)