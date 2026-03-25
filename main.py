import os
import json
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
    "objective": {
        "text": "Already unlocked.",
        "target": 0,
    },
}

DEFAULT_PLAYER_CHARACTER_STATE = {
    "progress": 0,
    "unlocked": False,
    "target": 100,
}


def sanitize_character_data(raw):
    if not isinstance(raw, dict):
        raw = {}

    objective_raw = raw.get("objective")
    if not isinstance(objective_raw, dict):
        objective_raw = {}

    return {
        "displayName": str(raw.get("displayName") or DEFAULT_CHARACTER_DATA["displayName"]),
        "modelName": str(raw.get("modelName") or DEFAULT_CHARACTER_DATA["modelName"]),
        "background": str(raw.get("background") or DEFAULT_CHARACTER_DATA["background"]),
        "personality": str(raw.get("personality") or DEFAULT_CHARACTER_DATA["personality"]),
        "difficulty": str(raw.get("difficulty") or DEFAULT_CHARACTER_DATA["difficulty"]),
        "voiceId": str(raw.get("voiceId") or DEFAULT_CHARACTER_DATA["voiceId"]),
        "objective": {
            "text": str(objective_raw.get("text") or DEFAULT_CHARACTER_DATA["objective"]["text"]),
            "target": int(objective_raw.get("target") or DEFAULT_CHARACTER_DATA["objective"]["target"] or 0),
        },
    }


def sanitize_player_character_state(raw):
    if not isinstance(raw, dict):
        raw = {}

    progress = raw.get("progress", DEFAULT_PLAYER_CHARACTER_STATE["progress"])
    unlocked = raw.get("unlocked", DEFAULT_PLAYER_CHARACTER_STATE["unlocked"])
    target = raw.get("target", DEFAULT_PLAYER_CHARACTER_STATE["target"])

    try:
        progress = int(progress)
    except Exception:
        progress = DEFAULT_PLAYER_CHARACTER_STATE["progress"]

    try:
        target = int(target)
    except Exception:
        target = DEFAULT_PLAYER_CHARACTER_STATE["target"]

    unlocked = bool(unlocked)

    progress = max(0, progress)
    target = max(0, target)

    return {
        "progress": progress,
        "unlocked": unlocked,
        "target": target,
    }


def build_chat_system_prompt(character_data, player_name):
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


def build_scoring_system_prompt(character_data, player_name, player_state):
    display_name = character_data["displayName"]
    background = character_data["background"]
    personality = character_data["personality"]
    difficulty = character_data["difficulty"]
    objective_text = character_data["objective"]["text"]
    current_progress = player_state["progress"]
    target = player_state["target"]

    return f"""
You are scoring a player's progress toward unlocking a character in a Roblox game.

Character: {display_name}
Player name: {player_name}

Character background:
{background}

Character personality:
{personality}

Character difficulty:
{difficulty}

Unlock objective:
{objective_text}

Current progress:
{current_progress}/{target}

Your job:
1. Write a short in-character reply as {display_name}.
2. Judge how much the player's latest message helps with the unlock objective.
3. Return ONLY valid JSON with these keys:
   - "reply": string
   - "progressDelta": integer

Scoring rules:
- If the message is irrelevant, repetitive, nonsense, hostile, or does not help the objective, use 0 to 2.
- If the message is a little relevant, use 3 to 7.
- If the message is meaningfully relevant and sincere, use 8 to 14.
- If the message is especially strong, insightful, emotional, or persuasive, use 15 to 20.
- Use negative values only if the player strongly goes against the objective, is rude, or clearly sabotages trust. Minimum is -10.
- Never give more than 20.
- Keep the reply short, in character, and appropriate for Roblox.
- The reply should subtly reflect whether the message helped.
- Do not explain the score.
- Do not include markdown fences.
- Output JSON only.

Important:
- The score should reflect the latest message only, not the full total.
- Be stricter for hard characters and slightly more generous for easy characters.
""".strip()


def extract_json_object(text):
    text = text.strip()

    try:
        return json.loads(text)
    except Exception:
        pass

    start = text.find("{")
    end = text.rfind("}")

    if start != -1 and end != -1 and end > start:
        candidate = text[start:end + 1]
        try:
            return json.loads(candidate)
        except Exception:
            pass

    return None


def call_groq(messages, max_tokens=140, temperature=0.7):
    global current_key_index

    if not API_KEYS:
        return None

    attempts = 0
    while attempts < len(API_KEYS):
        key = API_KEYS[current_key_index]

        try:
            client = Groq(api_key=key)
            completion = client.chat.completions.create(
                model="llama-3.1-8b-instant",
                messages=messages,
                max_tokens=max_tokens,
                temperature=temperature,
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


def get_free_chat_reply(message, player_name, character_data):
    system_prompt = build_chat_system_prompt(character_data, player_name)

    return call_groq(
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": message},
        ],
        max_tokens=100,
        temperature=0.9,
    )


def get_scored_reply(message, player_name, character_data, player_state):
    system_prompt = build_scoring_system_prompt(character_data, player_name, player_state)

    raw = call_groq(
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": message},
        ],
        max_tokens=180,
        temperature=0.6,
    )

    if raw is None:
        return None

    parsed = extract_json_object(raw)
    if not isinstance(parsed, dict):
        print("Failed to parse JSON from model:", raw)
        return {
            "reply": "Hmm... tell me more.",
            "progressDelta": 0,
        }

    reply = str(parsed.get("reply") or "").strip()
    if not reply:
        reply = "Hmm... tell me more."

    progress_delta = parsed.get("progressDelta", 0)
    try:
        progress_delta = int(progress_delta)
    except Exception:
        progress_delta = 0

    progress_delta = max(-10, min(20, progress_delta))

    return {
        "reply": reply[:300],
        "progressDelta": progress_delta,
    }


@app.route("/chat", methods=["POST"])
def chat():
    data = request.get_json(silent=True)

    if not data or "message" not in data:
        return jsonify({"error": "Missing message"}), 400

    message = str(data.get("message", ""))[:160].strip()
    player_name = str(data.get("playerName", "Player"))[:50]
    character_key = str(data.get("characterKey", "default"))[:50]
    character_data = sanitize_character_data(data.get("characterData"))
    player_state = sanitize_player_character_state(data.get("playerCharacterState"))

    if not message:
        return jsonify({"error": "Empty message"}), 400

    print("Incoming characterKey:", character_key)
    print("Incoming characterData:", character_data)
    print("Incoming playerState:", player_state)

    try:
        is_unlocked = player_state["unlocked"] or character_key == "default"

        if is_unlocked:
            reply = get_free_chat_reply(message, player_name, character_data)

            if reply is None:
                return jsonify({
                    "reply": "I'm overwhelmed right now, try again later!",
                    "progressDelta": 0,
                }), 503

            return jsonify({
                "reply": reply[:300],
                "progressDelta": 0,
            })

        scored = get_scored_reply(message, player_name, character_data, player_state)

        if scored is None:
            return jsonify({
                "reply": "I'm overwhelmed right now, try again later!",
                "progressDelta": 0,
            }), 503

        return jsonify(scored)

    except Exception as e:
        print(f"Unexpected error: {e}")
        return jsonify({
            "reply": "Something went wrong.",
            "progressDelta": 0,
        }), 500


@app.route("/health", methods=["GET"])
def health():
    return jsonify({
        "ok": True,
        "has_keys": len(API_KEYS) > 0,
        "key_count": len(API_KEYS),
    })


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 3000))
    app.run(host="0.0.0.0", port=port)
