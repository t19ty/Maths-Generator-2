# Database Setup for Maths Generator App

This document explains how to set up and use the database system for tracking user trials, login information, and performance data.

## 🗄️ Database Overview

The app now includes a comprehensive database system with the following features:

### Database Models

1. **User** - Stores user information (email, name, role, login times)
2. **UserSession** - Tracks login/logout sessions with IP and user agent
3. **Performance** - Records user performance on math questions
4. **QuestionHistory** - Stores all generated questions for analytics

### Features

- ✅ **Automatic user creation** when users first log in
- ✅ **Session tracking** with login/logout times and IP addresses
- ✅ **Performance analytics** by topic and difficulty
- ✅ **Question history** tracking for all generated questions
- ✅ **Real-time statistics** for teachers and students

## 🚀 Setup Instructions

### 1. Install Required Packages

```bash
python3 -m pip install Flask-SQLAlchemy Flask-Migrate
```

### 2. Initialize the Database

```bash
python3 init_db.py
```

This will:
- Create the SQLite database file (`maths_generator.db`)
- Create all necessary tables
- Add sample data for testing

### 3. Run the App

```bash
python3 app.py
```

## 📊 Database Management

### View Database Contents

Use the management script to view database records:

```bash
python3 manage_db.py
```

This provides a menu to:
- View all users
- View recent sessions
- View performance statistics
- View question history

### Database File Location

- **SQLite**: `maths_generator.db` (created in the app directory)
- **Production**: Set `DATABASE_URL` environment variable for PostgreSQL

## 🔐 Authentication & User Management

### User Registration
- Users are automatically created on first login
- Email domain must be `@school.cdgfss.edu.hk`
- Default role is "student" (can be updated later)

### Session Tracking
- Each login creates a new session record
- Sessions include IP address and user agent
- Logout properly closes sessions

## 📈 Performance Tracking

### Recording Answers
The app now includes an API endpoint to record user answers:

```javascript
// Frontend JavaScript example
fetch('/api/submit_answer', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({
        topic: 'factorization',
        difficulty: 'medium',
        question: 'What is the question text?',
        userAnswer: 'User selected answer',
        correctAnswer: 'Correct answer',
        isCorrect: false,
        timeTaken: 45.2  // Time in seconds
    })
});
```

### Performance Analytics
Access user performance data via:

```
GET /api/performance/<user_id>
```

Returns:
- Overall accuracy statistics
- Performance by topic
- Recent performance history
- Time taken analysis

## 🛠️ Database Schema

### Users Table
```sql
CREATE TABLE users (
    id VARCHAR(36) PRIMARY KEY,
    email VARCHAR(255) UNIQUE NOT NULL,
    first_name VARCHAR(100),
    last_name VARCHAR(100),
    role VARCHAR(50) DEFAULT 'student',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    last_login DATETIME
);
```

### User Sessions Table
```sql
CREATE TABLE user_sessions (
    id VARCHAR(36) PRIMARY KEY,
    user_id VARCHAR(36) REFERENCES users(id),
    session_token VARCHAR(255) UNIQUE NOT NULL,
    login_time DATETIME DEFAULT CURRENT_TIMESTAMP,
    logout_time DATETIME,
    ip_address VARCHAR(45),
    user_agent TEXT,
    is_active BOOLEAN DEFAULT TRUE
);
```

### Performance Table
```sql
CREATE TABLE performances (
    id VARCHAR(36) PRIMARY KEY,
    user_id VARCHAR(36) REFERENCES users(id),
    topic VARCHAR(100) NOT NULL,
    difficulty VARCHAR(50) NOT NULL,
    question_text TEXT NOT NULL,
    user_answer VARCHAR(500),
    correct_answer VARCHAR(500) NOT NULL,
    is_correct BOOLEAN NOT NULL,
    time_taken FLOAT,
    attempt_number INTEGER DEFAULT 1,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);
```

### Question History Table
```sql
CREATE TABLE question_history (
    id VARCHAR(36) PRIMARY KEY,
    topic VARCHAR(100) NOT NULL,
    difficulty VARCHAR(50) NOT NULL,
    question_text TEXT NOT NULL,
    options JSON NOT NULL,
    correct_answer VARCHAR(500) NOT NULL,
    generated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    generated_by_user_id VARCHAR(36) REFERENCES users(id)
);
```

## 🔧 Environment Variables

Add these to your `.env` file for production:

```bash
# Database (optional - defaults to SQLite)
DATABASE_URL=postgresql://user:password@localhost/maths_generator

# Other existing variables
GOOGLE_CLIENT_ID=your_google_client_id
GOOGLE_CLIENT_SECRET=your_google_client_secret
SESSION_SECRET=your_session_secret
API_KEY=your_api_key
```

## 📱 Frontend Integration

### Required Frontend Changes

To fully utilize the performance tracking, update your frontend to:

1. **Track time taken** for each question
2. **Submit answers** to `/api/submit_answer`
3. **Display performance** statistics
4. **Show progress** by topic and difficulty

### Example Frontend Code

```javascript
// Track time when question starts
let startTime = Date.now();

// When user submits answer
function submitAnswer(userAnswer, correctAnswer, isCorrect) {
    const timeTaken = (Date.now() - startTime) / 1000;
    
    fetch('/api/submit_answer', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({
            topic: currentTopic,
            difficulty: currentDifficulty,
            question: currentQuestion,
            userAnswer: userAnswer,
            correctAnswer: correctAnswer,
            isCorrect: isCorrect,
            timeTaken: timeTaken
        })
    });
}
```

## 🚨 Troubleshooting

### Common Issues

1. **Database not created**: Run `python3 init_db.py`
2. **Import errors**: Ensure all packages are installed
3. **Permission errors**: Check file permissions for database file

### Database Reset

To reset the database:

```bash
rm maths_generator.db
python3 init_db.py
```

## 🔮 Future Enhancements

Potential database improvements:

- **User roles and permissions** system
- **Class/group management** for teachers
- **Advanced analytics** and reporting
- **Export functionality** for data analysis
- **Backup and recovery** systems

## 📞 Support

For database-related issues:
1. Check the console output for error messages
2. Verify all packages are installed
3. Ensure database file has proper permissions
4. Check environment variables are set correctly
