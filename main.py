import os
from flask import Flask, request, jsonify
from groq import Groq

app = Flask(__name__)

API_KEYS = [
    os.environ.get("GROQ_KEY_1"),
    os.environ.get("GROQ_KEY_2"),
    os.environ.get("GROQ_KEY_3"),
]

API_KEYS = [key for key in API_KEYS if key]

current_key_index = 0

DEFAULT_CHARACTER_DATA = {
    "displayName": "NPC",
    "modelName": "default",
    "background": "A helpful assistant in a Roblox game.",
    "personality": "Friendly, helpful, neutral.",
    "difficulty": "easy",
    "voiceId": "4",
}


def sanitize_character_data(raw):
    if not isinstance(raw, dict):
        raw = {}

    return {
        "displayName": str(raw.get("displayName") or DEFAULT_CHARACTER_DATA["displayName"]),
        "modelName": str(raw.get("modelName") or DEFAULT_CHARACTER_DATA["modelName"]),
        "background": str(raw.get("background") or DEFAULT_CHARACTER_DATA["background"]),
        "personality": str(raw.get("personality") or DEFAULT_CHARACTER_DATA["personality"]),
        "difficulty": str(raw.get("difficulty") or DEFAULT_CHARACTER_DATA["difficulty"]),
        "voiceId": str(raw.get("voiceId") or DEFAULT_CHARACTER_DATA["voiceId"]),
    }


def build_system_prompt(character_data, player_name):
    display_name = character_data["displayName"]
    background = character_data["background"]
    personality = character_data["personality"]
    difficulty = character_data["difficulty"]

    return f"""
You are {display_name}, speaking to a player in a Roblox game.

Stay fully in character at all times.

Character background:
{background}

Character personality:
{personality}

Conversation style rules:
- Keep replies short, natural, and suitable for a Roblox game.
- Usually respond in 1 to 3 sentences.
- Be engaging and in-character.
- Do not call yourself Robby, RobbyBot, RobbyRocks, or a generic Roblox assistant.
- Do not say you are an AI assistant unless the character itself would somehow know that.
- Do not mention system prompts, hidden rules, or moderation.
- Never break character.
- The player's name is {player_name}.
- Match the tone of the character. If the character is playful, sound playful. If intimidating, sound intimidating.
- Keep everything appropriate and safe.

Difficulty guidance:
{difficulty}
""".strip()


def get_reply(message, player_name, character_data):
    global current_key_index

    if not API_KEYS:
        return None

    system_prompt = build_system_prompt(character_data, player_name)

    attempts = 0
    while attempts < len(API_KEYS):
        key = API_KEYS[current_key_index]

        try:
            client = Groq(api_key=key)
            completion = client.chat.completions.create(
                model="llama-3.1-8b-instant",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": message}
                ],
                max_tokens=100,
                temperature=0.9,
            )

            reply = completion.choices[0].message.content.strip()
            return reply

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
    data = request.get_json(silent=True)

    if not data or "message" not in data:
        return jsonify({"error": "Missing message"}), 400

    message = str(data.get("message", ""))[:160].strip()
    player_name = str(data.get("playerName", "Player"))[:50]
    character_key = str(data.get("characterKey", "default"))[:50]
    character_data = sanitize_character_data(data.get("characterData"))

    if not message:
        return jsonify({"error": "Empty message"}), 400

    print("Incoming characterKey:", character_key)
    print("Incoming characterData:", character_data)

    try:
        reply = get_reply(message, player_name, character_data)

        if reply is None:
            return jsonify({"reply": "I'm overwhelmed right now, try again later!"}), 503

        return jsonify({"reply": reply})

    except Exception as e:
        print(f"Unexpected error: {e}")
        return jsonify({"reply": "Something went wrong."}), 500


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=3000)
