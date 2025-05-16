from flask import Flask, render_template, redirect, url_for, flash, request, jsonify
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime, timedelta
import os
from sqlalchemy import func

# Initialize Flask app
app = Flask(__name__)
app.config['SECRET_KEY'] = 'your-secret-key'
# Use in-memory SQLite for serverless deployment
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///:memory:'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Initialize SQLAlchemy
db = SQLAlchemy(app)

# Initialize Flask-Login
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

# Database Models
class User(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(100), unique=True, nullable=False)
    password = db.Column(db.String(200), nullable=False)
    full_name = db.Column(db.String(100), nullable=False)
    qualification = db.Column(db.String(100))
    dob = db.Column(db.Date)
    is_admin = db.Column(db.Boolean, default=False)
    scores = db.relationship('Score', backref='user', lazy=True)

class Subject(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text)
    chapters = db.relationship('Chapter', backref='subject', lazy=True, cascade="all, delete-orphan")

class Chapter(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text)
    subject_id = db.Column(db.Integer, db.ForeignKey('subject.id'), nullable=False)
    quizzes = db.relationship('Quiz', backref='chapter', lazy=True, cascade="all, delete-orphan")

class Quiz(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    chapter_id = db.Column(db.Integer, db.ForeignKey('chapter.id'), nullable=False)
    date_of_quiz = db.Column(db.Date, nullable=False)
    time_duration = db.Column(db.Integer, nullable=False)  # Duration in minutes
    remarks = db.Column(db.Text)
    questions = db.relationship('Question', backref='quiz', lazy=True, cascade="all, delete-orphan")
    scores = db.relationship('Score', backref='quiz', lazy=True, cascade="all, delete-orphan")

class Question(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    quiz_id = db.Column(db.Integer, db.ForeignKey('quiz.id'), nullable=False)
    question_statement = db.Column(db.Text, nullable=False)
    option1 = db.Column(db.Text, nullable=False)
    option2 = db.Column(db.Text, nullable=False)
    option3 = db.Column(db.Text, nullable=False)
    option4 = db.Column(db.Text, nullable=False)
    correct_option = db.Column(db.Integer, nullable=False)  # 1, 2, 3, or 4

class Score(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    quiz_id = db.Column(db.Integer, db.ForeignKey('quiz.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    total_scored = db.Column(db.Integer, nullable=False)
    total_questions = db.Column(db.Integer, nullable=False)

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# Create database and admin user
@app.before_request
def create_tables():
    db.create_all()
    
    # Check if admin exists, if not create one
    admin = User.query.filter_by(is_admin=True).first()
    if not admin:
        admin = User(
            email='admin@quizmaster.com',
            password=generate_password_hash('admin123'),
            full_name='Quiz Master Admin',
            is_admin=True
        )
        db.session.add(admin)
        db.session.commit()

# Routes
@app.route('/')
def index():
    return render_template('index.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        
        user = User.query.filter_by(email=email).first()
        
        if user and check_password_hash(user.password, password):
            login_user(user)
            if user.is_admin:
                return redirect(url_for('admin_dashboard'))
            else:
                return redirect(url_for('user_dashboard'))
        else:
            flash('Invalid email or password')
    
    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        full_name = request.form.get('full_name')
        qualification = request.form.get('qualification')
        dob_str = request.form.get('dob')
        
        # Check if user already exists
        existing_user = User.query.filter_by(email=email).first()
        if existing_user:
            flash('Email already registered')
            return redirect(url_for('register'))
        
        # Convert date string to date object
        try:
            dob = datetime.strptime(dob_str, '%Y-%m-%d').date()
        except:
            dob = None
        
        # Create new user
        new_user = User(
            email=email,
            password=generate_password_hash(password),
            full_name=full_name,
            qualification=qualification,
            dob=dob
        )
        
        db.session.add(new_user)
        db.session.commit()
        
        flash('Registration successful! Please login.')
        return redirect(url_for('login'))
    
    return render_template('register.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('index'))

# Admin routes
@app.route('/admin/dashboard')
@login_required
def admin_dashboard():
    if not current_user.is_admin:
        flash('Access denied')
        return redirect(url_for('index'))
    
    subjects_count = Subject.query.count()
    chapters_count = Chapter.query.count()
    quizzes_count = Quiz.query.count()
    users_count = User.query.filter_by(is_admin=False).count()
    
    # Get recent quizzes
    recent_quizzes = Quiz.query.order_by(Quiz.id.desc()).limit(5).all()
    
    # Get top performing users
    top_users = db.session.query(
        User.full_name,
        func.avg(Score.total_scored * 100 / Score.total_questions).label('avg_score')
    ).join(Score).group_by(User.id).order_by(func.avg(Score.total_scored * 100 / Score.total_questions).desc()).limit(5).all()
    
    return render_template('admin/dashboard.html', 
                          subjects_count=subjects_count,
                          chapters_count=chapters_count,
                          quizzes_count=quizzes_count,
                          users_count=users_count,
                          recent_quizzes=recent_quizzes,
                          top_users=top_users)

@app.route('/admin/subjects', methods=['GET', 'POST'])
@login_required
def admin_subjects():
    if not current_user.is_admin:
        flash('Access denied')
        return redirect(url_for('index'))
    
    if request.method == 'POST':
        name = request.form.get('name')
        description = request.form.get('description')
        
        new_subject = Subject(name=name, description=description)
        db.session.add(new_subject)
        db.session.commit()
        
        flash('Subject added successfully')
        return redirect(url_for('admin_subjects'))
    
    subjects = Subject.query.all()
    return render_template('admin/subjects.html', subjects=subjects)

@app.route('/admin/subject/<int:subject_id>/edit', methods=['GET', 'POST'])
@login_required
def edit_subject(subject_id):
    if not current_user.is_admin:
        flash('Access denied')
        return redirect(url_for('index'))
    
    subject = Subject.query.get_or_404(subject_id)
    
    if request.method == 'POST':
        subject.name = request.form.get('name')
        subject.description = request.form.get('description')
        
        db.session.commit()
        flash('Subject updated successfully')
        return redirect(url_for('admin_subjects'))
    
    return render_template('admin/edit_subject.html', subject=subject)

@app.route('/admin/subject/<int:subject_id>/delete')
@login_required
def delete_subject(subject_id):
    if not current_user.is_admin:
        flash('Access denied')
        return redirect(url_for('index'))
    
    subject = Subject.query.get_or_404(subject_id)
    db.session.delete(subject)
    db.session.commit()
    
    flash('Subject deleted successfully')
    return redirect(url_for('admin_subjects'))

@app.route('/admin/chapters', methods=['GET', 'POST'])
@login_required
def admin_chapters():
    if not current_user.is_admin:
        flash('Access denied')
        return redirect(url_for('index'))
    
    if request.method == 'POST':
        name = request.form.get('name')
        description = request.form.get('description')
        subject_id = request.form.get('subject_id')
        
        new_chapter = Chapter(name=name, description=description, subject_id=subject_id)
        db.session.add(new_chapter)
        db.session.commit()
        
        flash('Chapter added successfully')
        return redirect(url_for('admin_chapters'))
    
    chapters = Chapter.query.all()
    subjects = Subject.query.all()
    return render_template('admin/chapters.html', chapters=chapters, subjects=subjects)

@app.route('/admin/chapter/<int:chapter_id>/edit', methods=['GET', 'POST'])
@login_required
def edit_chapter(chapter_id):
    if not current_user.is_admin:
        flash('Access denied')
        return redirect(url_for('index'))
    
    chapter = Chapter.query.get_or_404(chapter_id)
    
    if request.method == 'POST':
        chapter.name = request.form.get('name')
        chapter.description = request.form.get('description')
        chapter.subject_id = request.form.get('subject_id')
        
        db.session.commit()
        flash('Chapter updated successfully')
        return redirect(url_for('admin_chapters'))
    
    subjects = Subject.query.all()
    return render_template('admin/edit_chapter.html', chapter=chapter, subjects=subjects)

@app.route('/admin/chapter/<int:chapter_id>/delete')
@login_required
def delete_chapter(chapter_id):
    if not current_user.is_admin:
        flash('Access denied')
        return redirect(url_for('index'))
    
    chapter = Chapter.query.get_or_404(chapter_id)
    db.session.delete(chapter)
    db.session.commit()
    
    flash('Chapter deleted successfully')
    return redirect(url_for('admin_chapters'))

@app.route('/admin/quizzes', methods=['GET', 'POST'])
@login_required
def admin_quizzes():
    if not current_user.is_admin:
        flash('Access denied')
        return redirect(url_for('index'))
    
    if request.method == 'POST':
        chapter_id = request.form.get('chapter_id')
        date_str = request.form.get('date_of_quiz')
        time_duration = request.form.get('time_duration')
        remarks = request.form.get('remarks')
        
        # Convert date string to date object
        date_of_quiz = datetime.strptime(date_str, '%Y-%m-%d').date()
        
        new_quiz = Quiz(
            chapter_id=chapter_id,
            date_of_quiz=date_of_quiz,
            time_duration=time_duration,
            remarks=remarks
        )
        
        db.session.add(new_quiz)
        db.session.commit()
        
        flash('Quiz added successfully')
        return redirect(url_for('admin_quizzes'))
    
    quizzes = Quiz.query.all()
    chapters = Chapter.query.all()
    return render_template('admin/quizzes.html', quizzes=quizzes, chapters=chapters)

@app.route('/admin/quiz/<int:quiz_id>/edit', methods=['GET', 'POST'])
@login_required
def edit_quiz(quiz_id):
    if not current_user.is_admin:
        flash('Access denied')
        return redirect(url_for('index'))
    
    quiz = Quiz.query.get_or_404(quiz_id)
    
    if request.method == 'POST':
        quiz.chapter_id = request.form.get('chapter_id')
        date_str = request.form.get('date_of_quiz')
        quiz.date_of_quiz = datetime.strptime(date_str, '%Y-%m-%d').date()
        quiz.time_duration = request.form.get('time_duration')
        quiz.remarks = request.form.get('remarks')
        
        db.session.commit()
        flash('Quiz updated successfully')
        return redirect(url_for('admin_quizzes'))
    
    chapters = Chapter.query.all()
    return render_template('admin/edit_quiz.html', quiz=quiz, chapters=chapters)

@app.route('/admin/quiz/<int:quiz_id>/delete')
@login_required
def delete_quiz(quiz_id):
    if not current_user.is_admin:
        flash('Access denied')
        return redirect(url_for('index'))
    
    quiz = Quiz.query.get_or_404(quiz_id)
    db.session.delete(quiz)
    db.session.commit()
    
    flash('Quiz deleted successfully')
    return redirect(url_for('admin_quizzes'))

@app.route('/admin/quiz/<int:quiz_id>/questions', methods=['GET', 'POST'])
@login_required
def quiz_questions(quiz_id):
    if not current_user.is_admin:
        flash('Access denied')
        return redirect(url_for('index'))
    
    quiz = Quiz.query.get_or_404(quiz_id)
    
    if request.method == 'POST':
        question_statement = request.form.get('question_statement')
        option1 = request.form.get('option1')
        option2 = request.form.get('option2')
        option3 = request.form.get('option3')
        option4 = request.form.get('option4')
        correct_option = request.form.get('correct_option')
        
        new_question = Question(
            quiz_id=quiz_id,
            question_statement=question_statement,
            option1=option1,
            option2=option2,
            option3=option3,
            option4=option4,
            correct_option=correct_option
        )
        
        db.session.add(new_question)
        db.session.commit()
        
        flash('Question added successfully')
        return redirect(url_for('quiz_questions', quiz_id=quiz_id))
    
    questions = Question.query.filter_by(quiz_id=quiz_id).all()
    return render_template('admin/questions.html', quiz=quiz, questions=questions)

@app.route('/admin/question/<int:question_id>/edit', methods=['GET', 'POST'])
@login_required
def edit_question(question_id):
    if not current_user.is_admin:
        flash('Access denied')
        return redirect(url_for('index'))
    
    question = Question.query.get_or_404(question_id)
    
    if request.method == 'POST':
        question.question_statement = request.form.get('question_statement')
        question.option1 = request.form.get('option1')
        question.option2 = request.form.get('option2')
        question.option3 = request.form.get('option3')
        question.option4 = request.form.get('option4')
        question.correct_option = request.form.get('correct_option')
        
        db.session.commit()
        flash('Question updated successfully')
        return redirect(url_for('quiz_questions', quiz_id=question.quiz_id))
    
    return render_template('admin/edit_question.html', question=question)

@app.route('/admin/question/<int:question_id>/delete')
@login_required
def delete_question(question_id):
    if not current_user.is_admin:
        flash('Access denied')
        return redirect(url_for('index'))
    
    question = Question.query.get_or_404(question_id)
    quiz_id = question.quiz_id
    
    db.session.delete(question)
    db.session.commit()
    
    flash('Question deleted successfully')
    return redirect(url_for('quiz_questions', quiz_id=quiz_id))

@app.route('/admin/users')
@login_required
def admin_users():
    if not current_user.is_admin:
        flash('Access denied')
        return redirect(url_for('index'))
    
    users = User.query.filter_by(is_admin=False).all()
    return render_template('admin/users.html', users=users)

# User routes
@app.route('/user/dashboard')
@login_required
def user_dashboard():
    if current_user.is_admin:
        return redirect(url_for('admin_dashboard'))
    
    # Get user's quiz attempts
    attempts = Score.query.filter_by(user_id=current_user.id).order_by(Score.timestamp.desc()).all()
    
    # Get available subjects
    subjects = Subject.query.all()
    
    # Get user's performance data for chart
    user_scores = Score.query.filter_by(user_id=current_user.id).all()
    chart_data = {
        'labels': [],
        'scores': []
    }
    
    for score in user_scores:
        quiz = Quiz.query.get(score.quiz_id)
        chapter = Chapter.query.get(quiz.chapter_id)
        chart_data['labels'].append(chapter.name)
        chart_data['scores'].append(round((score.total_scored / score.total_questions) * 100))
    
    return render_template('user/dashboard.html', 
                          attempts=attempts, 
                          subjects=subjects,
                          chart_data=chart_data)

@app.route('/user/subject/<int:subject_id>')
@login_required
def user_subject(subject_id):
    if current_user.is_admin:
        return redirect(url_for('admin_dashboard'))
    
    subject = Subject.query.get_or_404(subject_id)
    chapters = Chapter.query.filter_by(subject_id=subject_id).all()
    
    return render_template('user/subject.html', subject=subject, chapters=chapters)

@app.route('/user/chapter/<int:chapter_id>')
@login_required
def user_chapter(chapter_id):
    if current_user.is_admin:
        return redirect(url_for('admin_dashboard'))
    
    chapter = Chapter.query.get_or_404(chapter_id)
    quizzes = Quiz.query.filter_by(chapter_id=chapter_id).all()
    
    # Check which quizzes the user has already attempted
    attempted_quizzes = []
    for quiz in quizzes:
        score = Score.query.filter_by(quiz_id=quiz.id, user_id=current_user.id).first()
        if score:
            attempted_quizzes.append(quiz.id)
    
    return render_template('user/chapter.html', 
                          chapter=chapter, 
                          quizzes=quizzes,
                          attempted_quizzes=attempted_quizzes)

@app.route('/user/quiz/<int:quiz_id>')
@login_required
def user_quiz(quiz_id):
    if current_user.is_admin:
        return redirect(url_for('admin_dashboard'))
    
    quiz = Quiz.query.get_or_404(quiz_id)
    
    # Check if user has already attempted this quiz
    existing_score = Score.query.filter_by(quiz_id=quiz_id, user_id=current_user.id).first()
    if existing_score:
        flash('You have already attempted this quiz')
        return redirect(url_for('user_quiz_result', score_id=existing_score.id))
    
    questions = Question.query.filter_by(quiz_id=quiz_id).all()
    
    if not questions:
        flash('This quiz has no questions yet')
        return redirect(url_for('user_chapter', chapter_id=quiz.chapter_id))
    
    return render_template('user/quiz.html', quiz=quiz, questions=questions)

@app.route('/user/quiz/<int:quiz_id>/submit', methods=['POST'])
@login_required
def submit_quiz(quiz_id):
    if current_user.is_admin:
        return redirect(url_for('admin_dashboard'))
    
    quiz = Quiz.query.get_or_404(quiz_id)
    questions = Question.query.filter_by(quiz_id=quiz_id).all()
    
    total_questions = len(questions)
    total_scored = 0
    
    for question in questions:
        answer = request.form.get(f'question_{question.id}')
        if answer and int(answer) == question.correct_option:
            total_scored += 1
    
    # Save score
    new_score = Score(
        quiz_id=quiz_id,
        user_id=current_user.id,
        total_scored=total_scored,
        total_questions=total_questions
    )
    
    db.session.add(new_score)
    db.session.commit()
    
    return redirect(url_for('user_quiz_result', score_id=new_score.id))

@app.route('/user/quiz/result/<int:score_id>')
@login_required
def user_quiz_result(score_id):
    if current_user.is_admin:
        return redirect(url_for('admin_dashboard'))
    
    score = Score.query.get_or_404(score_id)
    
    # Ensure the score belongs to the current user
    if score.user_id != current_user.id:
        flash('Access denied')
        return redirect(url_for('user_dashboard'))
    
    quiz = Quiz.query.get(score.quiz_id)
    chapter = Chapter.query.get(quiz.chapter_id)
    subject = Subject.query.get(chapter.subject_id)
    
    percentage = (score.total_scored / score.total_questions) * 100
    
    return render_template('user/result.html', 
                          score=score, 
                          quiz=quiz,
                          chapter=chapter,
                          subject=subject,
                          percentage=percentage)

# API routes
@app.route('/api/subjects', methods=['GET'])
def api_subjects():
    subjects = Subject.query.all()
    result = []
    
    for subject in subjects:
        result.append({
            'id': subject.id,
            'name': subject.name,
            'description': subject.description
        })
    
    return jsonify(result)

@app.route('/api/chapters/<int:subject_id>', methods=['GET'])
def api_chapters(subject_id):
    chapters = Chapter.query.filter_by(subject_id=subject_id).all()
    result = []
    
    for chapter in chapters:
        result.append({
            'id': chapter.id,
            'name': chapter.name,
            'description': chapter.description
        })
    
    return jsonify(result)

@app.route('/api/quizzes/<int:chapter_id>', methods=['GET'])
def api_quizzes(chapter_id):
    quizzes = Quiz.query.filter_by(chapter_id=chapter_id).all()
    result = []
    
    for quiz in quizzes:
        result.append({
            'id': quiz.id,
            'date_of_quiz': quiz.date_of_quiz.strftime('%Y-%m-%d'),
            'time_duration': quiz.time_duration,
            'remarks': quiz.remarks
        })
    
    return jsonify(result)

if __name__ == '__main__':
    app.run(debug=True)

# Add WSGI handler for serverless deployment
app.debug = False
