# Allow HTTP for local development only (OAuth 2.0 security requirement)
import os

# Check if we're in production (Render) or development (local)
IS_PRODUCTION = os.environ.get('FLASK_ENV') == 'production' or os.environ.get('RENDER') == 'true'

if not IS_PRODUCTION:
    os.environ['OAUTHLIB_INSECURE_TRANSPORT'] = '1'

from flask import Flask, render_template, request, jsonify, redirect, url_for, session
from openai import OpenAI
import json
import re
import random
import uuid
from flask_dance.contrib.google import make_google_blueprint, google
from dotenv import load_dotenv
from werkzeug.middleware.proxy_fix import ProxyFix
from models import db, User, UserSession, Performance, QuestionHistory
from datetime import datetime

# Load environment variables
load_dotenv()

GOOGLE_CLIENT_ID = os.environ.get("GOOGLE_CLIENT_ID")
GOOGLE_CLIENT_SECRET = os.environ.get("GOOGLE_CLIENT_SECRET")
SESSION_SECRET = os.environ.get("SESSION_SECRET")

# Debug: Print credentials (only in development)
if not IS_PRODUCTION:
    print(f"DEBUG: GOOGLE_CLIENT_ID: {GOOGLE_CLIENT_ID}")
    print(f"DEBUG: GOOGLE_CLIENT_SECRET: {GOOGLE_CLIENT_SECRET[:10]}..." if GOOGLE_CLIENT_SECRET else "DEBUG: GOOGLE_CLIENT_SECRET: None")
    print(f"DEBUG: SESSION_SECRET: {SESSION_SECRET[:10]}..." if SESSION_SECRET else "DEBUG: SESSION_SECRET: None")

app = Flask(__name__)
app.wsgi_app = ProxyFix(app.wsgi_app, x_proto=1, x_host=1)

# Database configuration
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL', f'sqlite:///{os.path.join(os.path.dirname(os.path.abspath(__file__)), "maths_generator.db")}')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Initialize database
db.init_app(app)

# Create database tables if they don't exist
with app.app_context():
    db.create_all()

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
    scope=[
        "openid",
        "https://www.googleapis.com/auth/userinfo.email",
        "https://www.googleapis.com/auth/userinfo.profile"
    ]
)

# Debug: Print the exact redirect URI being used
if not IS_PRODUCTION:
    print(f"DEBUG: Google OAuth redirect URI: {google_bp.redirect_url}")
    print(f"DEBUG: Google OAuth redirect to: {google_bp.redirect_to}")
app.register_blueprint(google_bp, url_prefix="/google_login")

# Debug: Print the blueprint info (only in development)
if not IS_PRODUCTION:
    print(f"DEBUG: Google blueprint registered with prefix: {google_bp.url_prefix}")
    print(f"DEBUG: Blueprint routes: {[str(rule) for rule in google_bp.deferred_functions]}")
    print(f"DEBUG: App routes: {[str(rule) for rule in app.url_map.iter_rules()]}")

# Email whitelist check function
def is_email_allowed(email):
    return email.endswith("@school.cdgfss.edu.hk")

def get_or_create_user(email, user_info=None):
    """Get existing user or create new user record"""
    user = User.query.filter_by(email=email).first()
    
    if not user:
        # Create new user
        user = User(
            email=email,
            first_name=user_info.get('given_name', '') if user_info else '',
            last_name=user_info.get('family_name', '') if user_info else '',
            role='student'  # Default role, can be updated later
        )
        db.session.add(user)
        db.session.commit()
    
    # Update last login time
    user.last_login = datetime.utcnow()
    db.session.commit()
    
    return user

def create_user_session(user_id, session_token, request):
    """Create a new user session record"""
    session_record = UserSession(
        user_id=user_id,
        session_token=session_token,
        ip_address=request.remote_addr,
        user_agent=request.headers.get('User-Agent', ''),
        is_active=True
    )
    db.session.add(session_record)
    db.session.commit()
    return session_record

# Route protection decorator
def login_required(f):
    from functools import wraps
    @wraps(f)
    def decorated_function(*args, **kwargs):
        # Check if user is already authenticated via session
        if session.get("user_email") and session.get("user_id"):
            return f(*args, **kwargs)
        
        # If not authenticated via session, check Google OAuth
        if not google.authorized:
            return redirect(url_for("login"))
        
        try:
            resp = google.get("/oauth2/v2/userinfo")
            if not resp.ok:
                # Token might be expired, redirect to login
                return redirect(url_for("login"))
            
            email = resp.json().get("email", "")
            if not is_email_allowed(email):
                return redirect(url_for("login", error="unauthorized"))
            
            session["user_email"] = email
            return f(*args, **kwargs)
        except Exception as e:
            # Handle token expiration and other OAuth errors
            if not IS_PRODUCTION:
                print(f"DEBUG: OAuth error in login_required: {e}")
            return redirect(url_for("login"))
    return decorated_function

@app.route("/protected")
@login_required
def protected():
    return f"Logged-in user: {session.get('user_email')}"

@app.route('/')
@login_required
def home():
    if not IS_PRODUCTION:
        print(f"DEBUG: User accessing home page, session: {session}")
    return render_template('index.html')

@app.route('/login')
def login():
    if os.environ.get('FLASK_ENV') != 'production':
        print(f"DEBUG: User accessing login page, google.authorized: {google.authorized}")
    
    # Check if there's an error parameter
    error = request.args.get('error')
    
    # Check if user is already authenticated via session
    if session.get("user_email") and session.get("user_id"):
        if os.environ.get('FLASK_ENV') != 'production':
            print("DEBUG: User already authenticated via session, redirecting to home")
        return redirect(url_for('home'))
    
    # Check Google OAuth
    if google.authorized and not error:
        if os.environ.get('FLASK_ENV') != 'production':
            print("DEBUG: User is authorized via Google and no error, redirecting to home")
        return redirect(url_for('home'))
    
    if os.environ.get('FLASK_ENV') != 'production':
        print("DEBUG: User not authorized, showing login page")
    
    # Debug: Show what the Google login URL will be
    google_login_url = url_for('google.login', _external=True)
    if os.environ.get('FLASK_ENV') != 'production':
        print(f"DEBUG: Google login URL will be: {google_login_url}")
    
    return render_template('login.html')

@app.route('/logout')
def logout():
    # Close active session in database
    if session.get('session_token'):
        session_record = UserSession.query.filter_by(
            session_token=session.get('session_token')
        ).first()
        if session_record:
            session_record.logout_time = datetime.utcnow()
            session_record.is_active = False
            db.session.commit()
    
    # Clear session
    session.clear()
    return redirect(url_for('login'))

@app.route('/test')
def test():
    """Simple test route to check if the app is working"""
    return "App is working! OAuth status: " + str(google.authorized)

@app.route('/health')
def health():
    """Health check route that doesn't require authentication"""
    return jsonify({
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "session_data": {
            "has_user_email": bool(session.get("user_email")),
            "has_user_id": bool(session.get("user_id")),
            "google_authorized": google.authorized
        }
    })

@app.route('/results')
def results():
    """Results page for users to view their performance"""
    print("DEBUG: Results route accessed")
    return render_template('results.html')

@app.route('/simple-results')
def simple_results():
    """Simple test results route"""
    return "Simple results route working!"

# Flask-Dance will handle the OAuth callback automatically at /google_login/google/authorized
# Add a post-login handler to check email and redirect appropriately
@app.route('/google_login/google/authorized')
def google_authorized():
    """Handle post-OAuth login to check email and set session"""
    if not google.authorized:
        if os.environ.get('FLASK_ENV') != 'production':
            print("DEBUG: OAuth not authorized in callback")
        return redirect(url_for('login'))
    
    if os.environ.get('FLASK_ENV') != 'production':
        print("DEBUG: OAuth authorized, getting user info")
    
    # Get user info
    resp = google.get("/oauth2/v2/userinfo")
    if not resp.ok:
        if os.environ.get('FLASK_ENV') != 'production':
            print(f"DEBUG: Failed to get user info: {resp.status_code}")
        return redirect(url_for('login'))
    
    user_info = resp.json()
    email = user_info.get("email", "")
    if os.environ.get('FLASK_ENV') != 'production':
        print(f"DEBUG: User email: {email}")
    
    # Check email whitelist
    if not is_email_allowed(email):
        if os.environ.get('FLASK_ENV') != 'production':
            print(f"DEBUG: Email not allowed: {email}")
        return redirect(url_for('login', error="unauthorized"))
    
    if os.environ.get('FLASK_ENV') != 'production':
        print(f"DEBUG: Email allowed, setting session for: {email}")
    
    # Create or get user record in database
    user = get_or_create_user(email, user_info)
    
    # Create session record
    session_token = str(uuid.uuid4())
    create_user_session(user.id, session_token, request)
    
    # Store user info in session
    session["user_email"] = email
    session["user_info"] = user_info
    session["user_id"] = user.id
    session["session_token"] = session_token
    
    if os.environ.get('FLASK_ENV') != 'production':
        print(f"DEBUG: Session set, redirecting to home. Session: {session}")
    
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

        # Save question to history
        question_history = QuestionHistory(
            topic=topic,
            difficulty=difficulty,
            question_text=question,
            options=options,
            correct_answer=correct_answer,
            generated_by_user_id=session.get('user_id')
        )
        db.session.add(question_history)
        db.session.commit()
        
        return jsonify({
            "question": question,
            "options": options,
            "correctIndex": correctIndex
        })
    except Exception as e:
        print(e)
        return jsonify({"error": str(e)}), 500

@app.route('/api/submit_answer', methods=['POST'])
@login_required
def submit_answer():
    """Record user's answer and performance"""
    try:
        data = request.json
        topic = data.get('topic')
        difficulty = data.get('difficulty')
        question_text = data.get('question')
        user_answer = data.get('userAnswer')
        correct_answer = data.get('correctAnswer')
        is_correct = data.get('isCorrect', False)
        time_taken = data.get('timeTaken')  # Time in seconds
        
        # Create performance record
        performance = Performance(
            user_id=session.get('user_id'),
            topic=topic,
            difficulty=difficulty,
            question_text=question_text,
            user_answer=user_answer,
            correct_answer=correct_answer,
            is_correct=is_correct,
            time_taken=time_taken
        )
        
        db.session.add(performance)
        db.session.commit()
        
        return jsonify({"success": True, "message": "Answer recorded"})
        
    except Exception as e:
        print(f"Error recording answer: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/api/performance/<user_id>')
@login_required
def get_user_performance(user_id):
    """Get performance statistics for a user"""
    try:
        # Only allow users to see their own performance or teachers to see all
        if session.get('user_id') != user_id and session.get('role') != 'teacher':
            return jsonify({"error": "Unauthorized"}), 403
        
        performances = Performance.query.filter_by(user_id=user_id).all()
        
        # Calculate statistics
        total_questions = len(performances)
        correct_answers = len([p for p in performances if p.is_correct])
        accuracy = (correct_answers / total_questions * 100) if total_questions > 0 else 0
        
        # Group by topic
        topic_stats = {}
        for p in performances:
            if p.topic not in topic_stats:
                topic_stats[p.topic] = {'total': 0, 'correct': 0}
            topic_stats[p.topic]['total'] += 1
            if p.is_correct:
                topic_stats[p.topic]['correct'] += 1
        
        # Calculate topic accuracy
        for topic in topic_stats:
            topic_stats[topic]['accuracy'] = (
                topic_stats[topic]['correct'] / topic_stats[topic]['total'] * 100
            )
        
        return jsonify({
            "total_questions": total_questions,
            "correct_answers": correct_answers,
            "accuracy": round(accuracy, 2),
            "topic_stats": topic_stats,
            "recent_performances": [
                {
                    "topic": p.topic,
                    "difficulty": p.difficulty,
                    "is_correct": p.is_correct,
                    "time_taken": p.time_taken,
                    "created_at": p.created_at.isoformat()
                }
                for p in performances[-10:]  # Last 10 attempts
            ]
        })
        
    except Exception as e:
        print(f"Error getting performance: {e}")
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    app.run(debug=False, host="0.0.0.0", port=int(os.environ.get("PORT", 8000))) 
