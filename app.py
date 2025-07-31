from flask import Flask, render_template, request, jsonify, redirect, url_for, session
from openai import OpenAI
import json
import re
import os
import random
import uuid
from flask_dance.contrib.google import make_google_blueprint, google
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

GOOGLE_CLIENT_ID = os.environ.get("GOOGLE_CLIENT_ID")
GOOGLE_CLIENT_SECRET = os.environ.get("GOOGLE_CLIENT_SECRET")
SESSION_SECRET = os.environ.get("SESSION_SECRET")

app = Flask(__name__)

API_KEY = os.environ.get("API_KEY", "sk-2b91306525ae497ca872f7bc7df5421d")
BASE_URL = "https://api.deepseek.com"

# Store the last question for each topic/difficulty
last_questions = {}

app.secret_key = SESSION_SECRET or "your-secret-key-change-this-in-production"

# Configure OAuth environment variables (like Google example)
if app.debug:
    os.environ['OAUTHLIB_INSECURE_TRANSPORT'] = '1'
    os.environ['OAUTHLIB_RELAX_TOKEN_SCOPE'] = '1'

google_bp = make_google_blueprint(
    client_id=GOOGLE_CLIENT_ID,
    client_secret=GOOGLE_CLIENT_SECRET,
    scope=["profile", "email"],
    redirect_url="https://maths-generator-2.onrender.com/google_login/google/authorized",
)
app.register_blueprint(google_bp, url_prefix="/google_login")

# Email whitelist check function
def is_email_allowed(email):
    return (
        email == "t19ty@cdgfss.edu.hk" or
        re.match(r"^cdg\d{6}@cdgfss\.edu\.hk$", email)
    )

# Route protection decorator
def login_required(f):
    from functools import wraps
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not google.authorized:
            return redirect(url_for("login"))
        resp = google.get("/oauth2/v2/userinfo")
        if not resp.ok:
            return redirect(url_for("login"))
        email = resp.json().get("email", "")
        if not is_email_allowed(email):
            return redirect(url_for("login", error="unauthorized"))
        session["user_email"] = email
        return f(*args, **kwargs)
    return decorated_function

@app.route("/protected")
@login_required
def protected():
    return f"Logged-in user: {session.get('user_email')}"

@app.route('/')
@login_required
def home():
    return render_template('index.html')

@app.route('/login')
def login():
    if google.authorized:
        return redirect(url_for('home'))
    return render_template('login.html')

@app.route('/logout')
def logout():
    # Clear session
    session.clear()
    return redirect(url_for('login'))

@app.route('/google_login/google/authorized')
def google_authorized():
    """Handle Google OAuth callback with proper error handling"""
    if not google.authorized:
        return redirect(url_for('login'))
    
    # Get user info
    resp = google.get("/oauth2/v2/userinfo")
    if not resp.ok:
        return redirect(url_for('login'))
    
    user_info = resp.json()
    email = user_info.get("email", "")
    
    # Check email whitelist
    if not is_email_allowed(email):
        return redirect(url_for('login', error="unauthorized"))
    
    # Store user info in session
    session["user_email"] = email
    session["user_info"] = user_info
    
    return redirect(url_for('home'))

@app.route('/api/generate', methods=['POST'])
def generate():
    try:
        data = request.json
        topic = data.get('topic', 'mathematics')
        difficulty = data.get('difficulty', 'medium')
        previous_questions = data.get('previousQuestions', [])
        key = f"{topic}|{difficulty}"
        last_question = last_questions.get(key, "")

        # Add prompt variety: random template and random tag
        templates = [
            "Generate ONE {difficulty} secondary-school mathematics question on '{topic}'. Provide EXACTLY 4 answer options.",
            "Write a {difficulty} math question for secondary school about '{topic}' with 4 answer choices.",
            "Create a single {difficulty} level math MCQ on '{topic}'. Give 4 options.",
            "Formulate a {difficulty} secondary-school mathematics multiple-choice question on '{topic}' with 4 options."
        ]
        rand_tag = str(uuid.uuid4())[:8]

        factorization_templates = [
            "Write a {difficulty} math question for secondary school about factorization using identities (perfect square, difference of two squares), with 4 answer choices.",
            "Create a single {difficulty} level math MCQ on factorization (identities: perfect square, difference of two squares). Give 4 options.",
            "Formulate a {difficulty} secondary-school mathematics multiple-choice question on factorization using identities (perfect square, difference of two squares) with 4 options."
        ]
        # Add a special template for challenging level
        if difficulty.lower() == "challenging":
            factorization_templates.append(
                "Generate a CHALLENGING secondary-school mathematics question on factorization using identities (perfect square, difference of two squares). Provide EXACTLY 4 answer options. The question should be similar in style to: Factorize the expression 4x^2 + 4x + 1 - y^2."
            )
            factorization_templates.append(
                "Write a challenging factorization question for secondary school using identities (perfect square, difference of two squares). Provide 4 answer choices. The question should be similar in style to: Factorize the expression: y^2 - x^2 - 2x - 1."
            )

        # Templates for factorization using cross method
        cross_method_templates = [
            "Generate ONE {difficulty} secondary-school mathematics question on factorization using the cross method. Provide EXACTLY 4 answer options.",
            "Write a {difficulty} math question for secondary school about factorization using the cross method, with 4 answer choices.",
            "Create a single {difficulty} level math MCQ on factorization using the cross method. Give 4 options.",
            "Formulate a {difficulty} secondary-school mathematics multiple-choice question on factorization using the cross method with 4 options."
        ]
        if difficulty.lower() == "challenging":
            cross_method_templates.append(
                "Write a challenging factorization question for secondary school using the cross method. Provide 4 answer choices. The question should be similar in style to: Factorize the expression: 6x^2 + 11x + 3."
            )

        # Templates for positive integral indices
        indices_templates = [
            "Generate ONE {difficulty} secondary-school mathematics question on positive integral indices. Provide EXACTLY 4 answer options.",
            "Write a {difficulty} math question for secondary school about positive integral indices, with 4 answer choices.",
            "Create a single {difficulty} level math MCQ on positive integral indices. Give 4 options.",
            "Formulate a {difficulty} secondary-school mathematics multiple-choice question on positive integral indices with 4 options."
        ]
        if difficulty.lower() == "challenging":
            indices_templates.append(
                "Write a challenging question for secondary school on positive integral indices. Provide 4 answer choices. The question should be similar in style to: Simplify (x^3 * y^2)^4 / (x^2 * y)^3."
            )

        # Select template set based on topic
        if "factorization using cross method" in topic.lower():
            template = random.choice(cross_method_templates)
            user_content = template.format(difficulty=difficulty)
            if previous_questions:
                user_content += " Do NOT repeat any of these questions: " + "; ".join(f'\"{q}\"' for q in previous_questions)
            user_content += f" Tag: {rand_tag}."
        elif "positive integral indices" in topic.lower():
            template = random.choice(indices_templates)
            user_content = template.format(difficulty=difficulty)
            if previous_questions:
                user_content += " Do NOT repeat any of these questions: " + "; ".join(f'\"{q}\"' for q in previous_questions)
            user_content += f" Tag: {rand_tag}."
        elif "factorization" in topic.lower():
            template = random.choice(factorization_templates)
            user_content = template.format(difficulty=difficulty)
            if previous_questions:
                user_content += " Do NOT repeat any of these questions: " + "; ".join(f'\"{q}\"' for q in previous_questions)
            user_content += f" Tag: {rand_tag}."
        else:
            template = random.choice(templates)
            user_content = template.format(difficulty=difficulty, topic=topic)
            if previous_questions:
                user_content += " Do NOT repeat any of these questions: " + "; ".join(f'\"{q}\"' for q in previous_questions)
            user_content += f" Tag: {rand_tag}."

        # print("System prompt:", system_prompt)
        print("User prompt:", user_content)

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
                "content": user_content
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

        print("AI raw content:", content)

        # Extract JSON from markdown code block if present
        match = re.search(r'```json\s*(\{[\s\S]*?\})\s*```', content)
        if not match:
            match = re.search(r'```\s*(\{[\s\S]*?\})\s*```', content)
        if match:
            json_str = match.group(1)
        else:
            # Try to find the first JSON object in the string
            match = re.search(r'(\{[\s\S]*\})', content)
            if match:
                json_str = match.group(1)
            else:
                json_str = content.strip()

        # Escape all unescaped backslashes (e.g., in LaTeX) to make valid JSON
        json_str = re.sub(r'(?<!\\)\\(?![\\"/bfnrtu])', r'\\\\', json_str)

        # No need to escape backslashes or quotes now, just parse
        args = json.loads(json_str)

        question = args["question"]
        options = args["options"]
        correct_answer = args["correct_answer"]

        # Shuffle options and update correctIndex
        combined = list(zip(options, range(len(options))))
        random.shuffle(combined)
        shuffled_options = [opt for opt, _ in combined]
        correctIndex = shuffled_options.index(correct_answer)
        options = shuffled_options

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
