from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
import cv2
import numpy as np
import os
import base64
import time
import uuid
import re
from io import BytesIO
from PIL import Image
from werkzeug.utils import secure_filename
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = 'static/uploads/'
app.secret_key = 'your_secret_key'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///image_filters.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16 MB max upload

db = SQLAlchemy(app)

# تأكد أن مجلد الرفع موجود
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
os.makedirs('static/css', exist_ok=True)

# تعريف نموذج المستخدم
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password = db.Column(db.String(200), nullable=False)
    images = db.relationship('FilterHistory', backref='user', lazy=True)
    
    def __repr__(self):
        return f'<User {self.username}>'

# تعريف نموذج سجل الفلاتر
class FilterHistory(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    original_filename = db.Column(db.String(120), nullable=False)
    edited_filename = db.Column(db.String(120), nullable=False)
    filters_applied = db.Column(db.String(200), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    
    def __repr__(self):
        return f'<FilterHistory {self.edited_filename}>'

# إنشاء قاعدة البيانات إذا لم تكن موجودة
with app.app_context():
    db.create_all()

@app.route('/')
def index():
    if 'user_id' in session:
        return render_template('index.html')
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        
        user = User.query.filter_by(username=username).first()
        
        if user and check_password_hash(user.password, password):
            session['user_id'] = user.id
            session['username'] = user.username
            flash('تم تسجيل الدخول بنجاح!', 'success')
            return redirect(url_for('index'))
        else:
            flash('اسم المستخدم أو كلمة المرور غير صحيحة', 'danger')
    
    return render_template('login.html')

@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        confirm_password = request.form['confirm_password']
        
        # التحقق من تطابق كلمات المرور
        if password != confirm_password:
            flash('كلمات المرور غير متطابقة', 'danger')
            return render_template('signup.html')
        
        # التحقق من وجود المستخدم
        existing_user = User.query.filter_by(username=username).first()
        if existing_user:
            flash('اسم المستخدم موجود بالفعل', 'danger')
            return render_template('signup.html')
        
        # إنشاء مستخدم جديد
        hashed_password = generate_password_hash(password)
        new_user = User(username=username, password=hashed_password)
        
        db.session.add(new_user)
        db.session.commit()
        
        flash('تم إنشاء الحساب بنجاح! يمكنك الآن تسجيل الدخول', 'success')
        return redirect(url_for('login'))
    
    return render_template('signup.html')

@app.route('/logout')
def logout():
    session.pop('user_id', None)
    session.pop('username', None)
    flash('تم تسجيل الخروج بنجاح', 'info')
    return redirect(url_for('login'))

@app.route('/upload', methods=['POST'])
def upload():
    if 'user_id' not in session:
        return redirect(url_for('login'))
        
    if 'image' not in request.files:
        flash('لم يتم اختيار صورة!', 'danger')
        return redirect(url_for('index'))

    file = request.files['image']
    filters = request.form.getlist('filter')

    if file:
        # Générer un nom unique pour éviter les écrasements de fichiers
        timestamp = str(int(time.time()))
        unique_id = str(uuid.uuid4().hex[:8])
        
        original_filename = secure_filename(file.filename)
        # Préserver l'extension du fichier
        file_extension = os.path.splitext(original_filename)[1]
        
        # Créer un nouveau nom de fichier avec timestamp et identifiant unique
        unique_filename = f"{timestamp}_{unique_id}{file_extension}"
        
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], unique_filename)
        file.save(filepath)

        image = cv2.imread(filepath)
        
        # Vérifier si l'image est correctement chargée
        if image is None:
            flash('خطأ في تحميل الصورة. الرجاء المحاولة بصورة أخرى.', 'danger')
            # Supprimer le fichier en cas d'erreur
            if os.path.exists(filepath):
                os.remove(filepath)
            return redirect(url_for('index'))
            
        # Obtenir les dimensions de l'image pour adapter les paramètres de filtres
        height, width = image.shape[:2]
        max_dimension = max(height, width)
        
        # تطبيق التحويلات الأساسية
        rotation = int(request.form.get('rotation', 0))
        flip_h = int(request.form.get('flip_h', 0))
        flip_v = int(request.form.get('flip_v', 0))
        brightness = int(request.form.get('brightness', 0))
        contrast = int(request.form.get('contrast', 0))
        saturation = int(request.form.get('saturation', 0))
        
        # تطبيق الدوران
        if rotation != 0:
            # حساب عدد الدورات بـ 90 درجة
            rotations = (rotation % 360) // 90
            for _ in range(abs(rotations)):
                if rotations > 0:
                    image = cv2.rotate(image, cv2.ROTATE_90_CLOCKWISE)
                else:
                    image = cv2.rotate(image, cv2.ROTATE_90_COUNTERCLOCKWISE)
        
        # تطبيق القلب
        if flip_h:
            image = cv2.flip(image, 1)  # 1 للقلب الأفقي
        if flip_v:
            image = cv2.flip(image, 0)  # 0 للقلب الرأسي
            
        # تطبيق السطوع والتباين
        if brightness != 0 or contrast != 0:
            # تحويل النطاق من [-100, 100] إلى قيم مناسبة
            alpha = (contrast / 100) + 1  # التباين
            beta = brightness  # السطوع
            
            # تطبيق المعادلة: g(x) = alpha * f(x) + beta
            image = cv2.convertScaleAbs(image, alpha=alpha, beta=beta)
            
        # تطبيق التشبع
        if saturation != 0:
            # تحويل إلى HSV لتعديل التشبع
            hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV).astype("float32")
            (h, s, v) = cv2.split(hsv)
            
            # تعديل قناة التشبع
            s = s * (1 + saturation / 100)
            s = np.clip(s, 0, 255)
            
            # دمج القنوات وإعادة التحويل إلى BGR
            hsv = cv2.merge([h, s, v])
            image = cv2.cvtColor(hsv.astype("uint8"), cv2.COLOR_HSV2BGR)

        # تطبيق الفلاتر
        for filter_type in filters:
            if filter_type == 'sepia':
                kernel = np.array([[0.272, 0.534, 0.131],
                                   [0.349, 0.686, 0.168],
                                   [0.393, 0.769, 0.189]])
                image = cv2.transform(image, kernel)
                image = np.clip(image, 0, 255).astype(np.uint8)

            elif filter_type == 'blur':
                # Amélioration du filtre flou avec un paramètre adaptatif
                # Plus l'image est grande, plus le noyau de flou est grand
                kernel_size = max(3, min(31, int(max_dimension / 50)))
                # Toujours s'assurer que le kernel_size est impair
                if kernel_size % 2 == 0:
                    kernel_size += 1
                
                # Appliquer un flou gaussien avec un kernel adaptatif
                image = cv2.GaussianBlur(image, (kernel_size, kernel_size), 0)
                
                # Si l'effet est trop faible, appliquer un second passage
                blur_intensity = int(request.form.get('blur_intensity', 1))
                if blur_intensity > 1:
                    for _ in range(blur_intensity - 1):
                        image = cv2.GaussianBlur(image, (kernel_size, kernel_size), 0)

            elif filter_type == 'gray':
                image = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
                # للتأكد من أن الصورة تحتوي على 3 قنوات ألوان للتخزين
                if len(image.shape) == 2:
                    image = cv2.cvtColor(image, cv2.COLOR_GRAY2BGR)
                    
            # فلتر زيادة حدة الصورة
            elif filter_type == 'sharpen':
                kernel = np.array([[0, -1, 0],
                                   [-1, 5, -1],
                                   [0, -1, 0]])
                image = cv2.filter2D(image, -1, kernel)
                
            # فلتر حواف الصورة
            elif filter_type == 'edge':
                image = cv2.Canny(image, 100, 200)
                if len(image.shape) == 2:
                    image = cv2.cvtColor(image, cv2.COLOR_GRAY2BGR)
                    
            # فلتر الرسم بالقلم
            elif filter_type == 'pencil':
                gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
                gray_blur = cv2.GaussianBlur(gray, (7, 7), 0)
                edges = cv2.Laplacian(gray_blur, cv2.CV_8U, ksize=5)
                ret, mask = cv2.threshold(edges, 100, 255, cv2.THRESH_BINARY_INV)
                image = cv2.cvtColor(mask, cv2.COLOR_GRAY2BGR)
                
            # فلتر الألوان العكسية
            elif filter_type == 'invert':
                image = cv2.bitwise_not(image)
                
            # فلتر الصورة الحرارية (thermal)
            elif filter_type == 'thermal':
                image_gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
                image_gray = cv2.equalizeHist(image_gray)
                image = cv2.applyColorMap(image_gray, cv2.COLORMAP_JET)
                
            # فلتر الصورة البارزة (emboss)
            elif filter_type == 'emboss':
                kernel = np.array([[0, -1, -1],
                                  [1, 0, -1],
                                  [1, 1, 0]])
                image = cv2.filter2D(image, -1, kernel) + 128
                
            # فلتر البيكسل (pixelate)
            elif filter_type == 'pixel':
                height, width = image.shape[:2]
                temp = cv2.resize(image, (width//16, height//16), interpolation=cv2.INTER_LINEAR)
                image = cv2.resize(temp, (width, height), interpolation=cv2.INTER_NEAREST)

        # Générer un nom unique pour l'image modifiée également
        output_filename = f"edited_{timestamp}_{unique_id}{file_extension}"
        output_path = os.path.join(app.config['UPLOAD_FOLDER'], output_filename)
        cv2.imwrite(output_path, image)
        
        # حفظ العملية في قاعدة البيانات
        edit_operations = []
        if rotation != 0:
            edit_operations.append(f"دوران: {rotation}°")
        if flip_h:
            edit_operations.append("قلب أفقي")
        if flip_v:
            edit_operations.append("قلب رأسي")
        if brightness != 0:
            edit_operations.append(f"سطوع: {brightness}")
        if contrast != 0:
            edit_operations.append(f"تباين: {contrast}")
        if saturation != 0:
            edit_operations.append(f"تشبع: {saturation}")
        
        # إضافة الفلاتر المطبقة
        filter_names = []
        for f in filters:
            if f == 'sepia':
                filter_names.append("سيبيا")
            elif f == 'blur':
                filter_names.append("ضبابي")
            elif f == 'gray':
                filter_names.append("أبيض وأسود")
            elif f == 'sharpen':
                filter_names.append("حدة الصورة")
            elif f == 'edge':
                filter_names.append("الحواف")
            elif f == 'pencil':
                filter_names.append("رسم بالقلم")
            elif f == 'invert':
                filter_names.append("ألوان عكسية")
            elif f == 'thermal':
                filter_names.append("التصوير الحراري")
            elif f == 'emboss':
                filter_names.append("بارز")
            elif f == 'pixel':
                filter_names.append("بكسلة")
        
        # دمج كل العمليات
        all_operations = edit_operations + filter_names
        operations_str = ', '.join(all_operations) if all_operations else "لا تعديلات"
        
        filter_history = FilterHistory(
            original_filename=unique_filename,  # Utiliser le nom de fichier unique
            edited_filename=output_filename,    # Utiliser le nom de fichier modifié unique
            filters_applied=operations_str,
            user_id=session['user_id']
        )
        
        db.session.add(filter_history)
        db.session.commit()

        return render_template('result.html', 
                              original=unique_filename, 
                              edited=output_filename, 
                              operations=operations_str)
    else:
        flash('يرجى اختيار صورة!', 'warning')
        return redirect(url_for('index'))

@app.route('/history')
def history():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    user_history = FilterHistory.query.filter_by(user_id=session['user_id']).order_by(FilterHistory.created_at.desc()).all()
    return render_template('history.html', history=user_history)

@app.route('/delete_image/<int:image_id>', methods=['POST'])
def delete_image(image_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    # Récupérer l'entrée à supprimer
    image_entry = FilterHistory.query.filter_by(id=image_id, user_id=session['user_id']).first()
    
    if image_entry:
        # Supprimer les fichiers réels
        try:
            original_path = os.path.join(app.config['UPLOAD_FOLDER'], image_entry.original_filename)
            edited_path = os.path.join(app.config['UPLOAD_FOLDER'], image_entry.edited_filename)
            
            # Supprimer les fichiers s'ils existent
            if os.path.exists(original_path):
                os.remove(original_path)
            if os.path.exists(edited_path):
                os.remove(edited_path)
                
            # Supprimer l'entrée de la base de données
            db.session.delete(image_entry)
            db.session.commit()
            
            flash('تم حذف الصورة بنجاح', 'success')
        except Exception as e:
            flash(f'حدث خطأ أثناء حذف الصورة: {str(e)}', 'danger')
    else:
        flash('لم يتم العثور على الصورة', 'warning')
    
    return redirect(url_for('history'))

@app.route('/uploads/<filename>')
def send_file(filename):
    return redirect(url_for('static', filename='uploads/' + filename), code=301)

@app.route('/save_transformed_image', methods=['POST'])
def save_transformed_image():
    if 'user_id' not in session:
        return jsonify({'success': False, 'error': 'غير مصرح به، يرجى تسجيل الدخول'}), 401
        
    try:
        data = request.json
        image_data = data['image_data']
        original_filename = data['original_filename']
        transformations = data['transformations']
        
        # Extraire les données d'image de la chaîne de données URL
        image_data = re.sub('^data:image/.+;base64,', '', image_data)
        image_binary = base64.b64decode(image_data)
        
        # Charger l'image avec PIL
        image = Image.open(BytesIO(image_binary))
        
        # Générer un nouveau nom de fichier unique
        timestamp = str(int(time.time()))
        unique_id = str(uuid.uuid4().hex[:8])
        file_extension = os.path.splitext(original_filename)[1] if '.' in original_filename else '.jpg'
        
        # Créer le nouveau nom de fichier
        new_edited_filename = f"transformed_{timestamp}_{unique_id}{file_extension}"
        save_path = os.path.join(app.config['UPLOAD_FOLDER'], new_edited_filename)
        
        # Sauvegarder l'image transformée
        image.save(save_path, quality=95)
        
        # Chercher l'entrée d'historique correspondante
        history_entry = FilterHistory.query.filter(
            FilterHistory.user_id == session['user_id'],
            (FilterHistory.original_filename == original_filename) | (FilterHistory.edited_filename == original_filename)
        ).first()
        
        if not history_entry:
            return jsonify({'success': False, 'error': 'لم يتم العثور على الصورة الأصلية'}), 404
            
        # Créer une description des transformations appliquées
        transform_description = []
        if transformations['scale'] != 1:
            scale_percent = int((transformations['scale'] - 1) * 100)
            if scale_percent > 0:
                transform_description.append(f"تكبير: +{scale_percent}%")
            else:
                transform_description.append(f"تصغير: {scale_percent}%")
                
        if transformations['rotation'] != 0:
            transform_description.append(f"دوران: {transformations['rotation']}°")
            
        if transformations['flip_h']:
            transform_description.append("قلب أفقي")
            
        if transformations['flip_v']:
            transform_description.append("قلب رأسي")
        
        # Ajouter les filtres originaux à la description
        original_filters = history_entry.filters_applied
        if original_filters and original_filters != "لا تعديلات":
            transform_description.append(original_filters)
            
        # Joindre toutes les descriptions
        transforms_str = ', '.join(transform_description) if transform_description else "تعديلات الشكل فقط"
        
        # Déterminer si nous travaillons sur une image originale ou déjà modifiée
        is_edited = original_filename.startswith('edited_') or original_filename.startswith('transformed_')
        
        # Créer une nouvelle entrée dans l'historique
        new_history = FilterHistory(
            original_filename=history_entry.original_filename if is_edited else original_filename,
            edited_filename=new_edited_filename,
            filters_applied=transforms_str,
            user_id=session['user_id']
        )
        
        db.session.add(new_history)
        db.session.commit()
        
        return jsonify({
            'success': True, 
            'filename': new_edited_filename,
            'message': 'تم حفظ الصورة بنجاح'
        })
        
    except Exception as e:
        print(f"Error: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500

if __name__ == "__main__":
    app.run(debug=True)
