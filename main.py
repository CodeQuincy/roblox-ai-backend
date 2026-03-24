from flask import Flask, request, jsonify
from groq import Groq

app = Flask(__name__)

API_KEYS = [
    os.environ.get("GROQ_KEY_1"),
    os.environ.get("GROQ_KEY_2"),
    os.environ.get("GROQ_KEY_3"),
]

current_key_index = 0

SYSTEM_PROMPT = "You are a helpful assistant in a Roblox game. Keep replies short and friendly. Never say anything inappropriate."

def get_reply(message, player_name):
    global current_key_index

    attempts = 0
    while attempts < len(API_KEYS):
        key = API_KEYS[current_key_index]
        try:
            client = Groq(api_key=key)
            completion = client.chat.completions.create(
                model="llama-3.1-8b-instant",
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": f"{player_name}: {message}"}
                ],
                max_tokens=100
            )
            return completion.choices[0].message.content.strip()

        except Exception as e:
            error_str = str(e).lower()
            if "rate_limit" in error_str or "quota" in error_str or "429" in error_str:
                print(f"Key {current_key_index} exhausted, rotating...")
                current_key_index = (current_key_index + 1) % len(API_KEYS)
                attempts += 1
            else:
                raise e

    return None

@app.route("/chat", methods=["POST"])
def chat():
    data = request.get_json()
    if not data or "message" not in data:
        return jsonify({"error": "Missing message"}), 400

    message = data.get("message", "")[:160]
    player_name = data.get("playerName", "Player")

    try:
        reply = get_reply(message, player_name)
        if reply is None:
            return jsonify({"reply": "I'm overwhelmed right now, try again later!"}), 503
        return jsonify({"reply": reply})

    except Exception as e:
        print(f"Unexpected error: {e}")
        return jsonify({"reply": "Something went wrong."}), 500

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=3000)
```

Scroll down and click **"Commit new file"**

---

## Step 2 — Create Second File

Click **"Add file" → "Create new file"** again

**Name it `requirements.txt`** and paste:
```
flask
groq
gunicorn
```

Click **"Commit new file"**

---

## Step 3 — Go to Render

Your repo should now look like this:
```
your-repo/
├── main.py
└── requirements.txt
```

1. Go to [render.com](https://render.com)
2. Sign up with your **GitHub account** (easiest)
3. Click **"New +"** → **"Web Service"**
4. Click **"Connect"** next to your repository
5. Fill in these settings:

| Setting | Value |
|---|---|
| Name | anything you want |
| Region | closest to you |
| Branch | main |
| Runtime | Python 3 |
| Build Command | `pip install -r requirements.txt` |
| Start Command | `gunicorn main:app --bind 0.0.0.0:3000` |
| Instance Type | **Free** |

6. Click **"Create Web Service"**

---

## Step 4 — Get Your URL

Render will take about **2-3 minutes** to deploy. Once it says **"Live"** you'll see your URL at the top:
```
https://your-app-name.onrender.com
```

Your Roblox backend URL will be:
```
https://your-app-name.onrender.com/chat
