from flask import Flask, render_template, request, jsonify
from openai import OpenAI
import json
import re
import os

app = Flask(__name__)

API_KEY = os.environ.get("API_KEY", "sk-2b91306525ae497ca872f7bc7df5421d")
BASE_URL = "https://api.deepseek.com"

# Store the last question for each topic/difficulty
last_questions = {}

@app.route('/')
def home():
    return render_template('index.html')

@app.route('/api/generate', methods=['POST'])
def generate():
    try:
        data = request.json
        topic = data.get('topic', 'mathematics')
        difficulty = data.get('difficulty', 'medium')
        key = f"{topic}|{difficulty}"
        last_question = last_questions.get(key, "")

        messages = [
            {
                "role": "system",
                "content": (
                    "You are a strict generator of multiple-choice questions. "
                    "Return your answer as a JSON object with keys: question, options (array of 4), and correct_answer (the correct option string)."
                )
            },
            {
                "role": "user",
                "content": (
                    f"Generate ONE {difficulty} secondary-school mathematics "
                    f"question on \"{topic}\". Provide EXACTLY 4 answer options."
                    + (f" Do NOT repeat this question: \"{last_question}\"" if last_question else "")
                )
            }
        ]

        client = OpenAI(api_key=API_KEY, base_url=BASE_URL)
        response = client.chat.completions.create(
            model="deepseek-chat",
            messages=messages,
            temperature=0.2,
            max_tokens=800
        )

        choice = response.choices[0]
        content = choice.message.content

        # Extract JSON from markdown code block if present
        match = re.search(r'```json\n(.*?)```', content, re.DOTALL)
        if match:
            json_str = match.group(1)
        else:
            json_str = content

        args = json.loads(json_str)

        question = args["question"]
        options = args["options"]
        correct_answer = args["correct_answer"]
        correctIndex = options.index(correct_answer)

        # Save the last question for this topic/difficulty
        last_questions[key] = question

        return jsonify({
            "question": question,
            "options": options,
            "correctIndex": correctIndex
        })
    except Exception as e:
        print(e)
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    app.run(debug=False, host="0.0.0.0", port=int(os.environ.get("PORT", 10000))) 