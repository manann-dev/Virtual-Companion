from flask import Flask, render_template, request, jsonify
from flask_sqlalchemy import SQLAlchemy
import os, json
import logging
import uuid
from stable_generator import generate_stable_image_from_text
from dotenv import load_dotenv
from werkzeug.security import generate_password_hash, check_password_hash
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
import secrets
from io import BytesIO
import base64
import requests
from PIL import Image as PILImage, ImageDraw, ImageFont
from time import sleep
from flask import redirect, flash, url_for
from itsdangerous import URLSafeTimedSerializer
from flask_mail import Mail, Message
from flask_migrate import Migrate
import traceback
from flask import abort
import stripe
from datetime import datetime, timedelta
from flask_socketio import SocketIO, emit
from celery import Celery, Task
import jinja2
from models import load_model, get_tokenizer, load_tokenizer
from tokenizer_auto import initialize_shared_components
from transformers import AutoTokenizer, AutoModelForCausalLM
import shared as shared

load_dotenv()

app = Flask(__name__)
socketio = SocketIO(app)

jinja_env = jinja2.Environment(app)
loaded_model = load_model("facebook_opt-1.3b", "Transformers")
initialize_shared_components('facebook/opt-1.3b')
# model = AutoModelForCausalLM.from_pretrained("facebook/opt-1.3b")
# tokenizer = AutoTokenizer.from_pretrained("facebook/opt-1.3b")
shared.model = loaded_model
shared.tokenizer = load_tokenizer('facebook/opt-1.3b')


# The database URL will be provided by Heroku in the DATABASE_URL environment variable
app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv('DATABASE_URL2')
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY')
app.config['MAIL_PASSWORD'] = os.getenv('MAIL_PASSWORD')
STRIPE_WEBHOOK_SECRET = os.getenv("STRIPE_WEBHOOK_SECRET")
LOGIN_REDIRECT_URL = os.getenv("LOGIN_REDIRECT_URL")
CELERY_BROKER_URL = os.getenv("CELERY_BROKER_URL")

stripe_api_key = os.getenv("stripe_api_key")

stripe.api_key = stripe_api_key

db = SQLAlchemy(app)
migrate = Migrate(app, db)

app.config['SECURITY_PASSWORD_SALT'] = os.getenv('SECURITY_PASSWORD_SALT')

app.config['MAIL_SERVER'] = 'mail.aihentaigenerator.net'
app.config['MAIL_PORT'] = 465
app.config['MAIL_USE_TLS'] = False
app.config['MAIL_USE_SSL'] = True
app.config['MAIL_DEFAULT_SENDER'] = 'mail.aihentaigenerator.net'

app.config['MAIL_USERNAME'] = 'info@aihentaigenerator.net'

# Initialize Flask-Login
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'  # Redirects to the login page when trying to access a login_required route

mail = Mail(app)
app.config["DEBUG"] = True

BASE_DIR = os.path.dirname(os.path.abspath(__file__))  # This gets the directory of the current script
FONT_PATH = os.path.join(BASE_DIR, 'assets', 'Arial.ttf')

BLOCKED_IPS = ['223.233.82.132', '193.19.109.67', '85.8.130.19',
               '173.239.254.221']  # Replace with the IPs you want to block



def celery_init_app(app: Flask) -> Celery:
    class FlaskTask(Task):
        def __call__(self, *args: object, **kwargs: object) -> object:
            with app.app_context():
                return self.run(*args, **kwargs)

    celery_app = Celery(app.name, task_cls=FlaskTask)
    celery_app.config_from_object(app.config["CELERY"])
    celery_app.set_default()
    app.extensions["celery"] = celery_app
    return celery_app

app.config.from_mapping(
    CELERY=dict(
        broker_url=CELERY_BROKER_URL,
        result_backend=CELERY_BROKER_URL,
        task_ignore_result=True,
    ),
)
celery_app = celery_init_app(app)


active_users = {}

@app.before_request
def block_ips():
    if request.remote_addr in BLOCKED_IPS:
        abort(403)  # Forbidden


class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nickname = db.Column(db.String(150), unique=True, nullable=False)
    email = db.Column(db.String(150), unique=True, nullable=False)
    password = db.Column(db.String(200), nullable=False)
    premium = db.Column(db.Boolean, default=False, nullable=True)
    email_confirmed = db.Column(db.Boolean, default=False, nullable=True)
    images = db.relationship('Image', backref='user', lazy=True)
    banned = db.Column(db.Boolean, default=False, nullable=True)
    creation_date = db.Column(db.DateTime, default=datetime.utcnow)
 
    def set_password(self, password):
        self.password = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password, password)


# Define the Image model
class Image(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    url = db.Column(db.String, nullable=False)
    text_input = db.Column(db.String)
    negative_prompt = db.Column(db.String)
    ethnicity = db.Column(db.String)
    hairColor = db.Column(db.String)
    face = db.Column(db.String)
    hairStyle = db.Column(db.String)
    eyesColor = db.Column(db.String)
    outfit = db.Column(db.String)
    places = db.Column(db.String)
    race = db.Column(db.String)
    accessories = db.Column(db.String)
    tracking_id = db.Column(db.String)
    likes = db.Column(db.Integer, default=0)
    views = db.Column(db.Integer, default=0)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    in_private_gallery = db.Column(db.Boolean, default=False)


logging.basicConfig(filename='app.log', level=logging.DEBUG)

BANNED_WORDS = ['child', 'young', 'years old', 'little', 'daughter', 'son', 'petite', 'loli',
                'adolescent', 'flat', 'short', 'tiny', 'girl', 'boy', 'underage',
                'yr old', 'YR OLD', 'miniature', 'tiniest', 'small', 'wee', 'WEE', 'minute', 'mini',
                'MINI', 'innocent', 'diminutive', 'midget', 'undersized', 'cute', 'bite',
                'dainty', 'tiddly', 'compact', 'years_old', 'dwarf', 'fun sized', 'minuscule',
                'teensy', 'pisti', 'MAGI', 'magi', 'grade', 'school', 'elementary', 'student',
                'rem zero', 'year', '1', '2', '3', "4", "5", "6", "7", "8", "9", "10", "11", "12", "13",
                "14", "15", "16", "17", "teen", 'immature', 'underdeveloped', 'youthful', 'YOUTHFUL',
                'underdeveloped body', 'three', 'four', 'five', 'six', 'seven', 'eight', 'nine', 'ten',
                'eleven', 'twelve', 'thirteen', 'fourteen', 'fifteen', 'sixteen', 'seventeen', 'lolta',
                'innocen', 'littl', 'lil', 'petit', 'baby', 'babydoll', 'diaper', '\u77ed\u3044',
                '\u5e7c\u5973', '\u5c0f\u3055\u306a\u80f8', 'illya', 'classroom', 'auroriel', 'rape', 'baby',
                'raped', 'forced', 'asuka langley' 'sis', 'bro', 'hinata', 'orihime inoue']


@celery_app.task
def send_request_to_third_party(url, payload):

    response = requests.post(url, json=payload)
    print("Response from stable diffusion: ", response.status_code)
    

@app.route('/', methods=['GET', 'POST'])
def home():
    image_id = request.args.get('image_id')
    if image_id:
        print("afs")
        session = db.session  # or however you access your session
        clicked_image = session.get(Image, image_id)
        if clicked_image:
            # Pass the image parameters to the template to pre-fill the input fields
            # Now also send the tracking_id to the frontend.
            return render_template('index.html', image=clicked_image, tracking_id=clicked_image.tracking_id)

    default_image_url = "https://aihentaigenerator.net/wp-content/uploads/2023/11/AIGDefaultimage1.png"
    # print(request.data)
    # if str(request.data) != '' and request.method == 'POST':
    #     try:
    #         data = json.loads(request.data)

    #         text_input = data.get('text_input').lower()
    #         negative_prompt = data.get('negative_prompt')
    #         gender = data.get('gender')
    #         ethnicity = data.get('ethnicity')
    #         hairColor = data.get('hairColor')
    #         face = data.get('face')
    #         hairStyle = data.get('hairStyle')
    #         eyesColor = data.get('eyesColor')
    #         outfit = data.get('outfit')
    #         places = data.get('places')
    #         race = data.get('race')
    #         accessories = data.get('accessories')
    #         seed = data.get('seed', None)  # Get the seed value from the request data
    #         num_images = data.get('num_images', 1)
    #         uniqueId = data.get('uniqueId', 1)

    #         # premium featyres
    #         private_gallery = False
    #         no_watermark = "no"  # premium features
    #         quality = "utlra"
    #         img_size = data.get('img_size', 'square')

    #         try:
    #             seed = int(seed) if seed else None
    #         except ValueError:
    #             seed = None  # Reset to None if the conversion fails

    #         # If user is premium, override some values
    #         if current_user.is_authenticated and current_user.premium:
    #             no_watermark = data.get('no_watermark', "no")
    #             private_gallery = data.get('private_gallery', True)
    #             img_size = "max"
    #             quality = data.get('quality')

    #             # Replace banned words in text_input with empty string
    #         for word in BANNED_WORDS:
    #             text_input = text_input.replace(word, "")

    #         text_input = (
    #             f"{gender} {ethnicity}, {race}, ((age 20-30)), with {hairColor} hair, "
    #             f"{face}, Hair Style: {hairStyle}, {eyesColor}, {outfit}, "
    #             f"In {places}, With {accessories}, tall ((adult)), {text_input}, ((full body)), "
    #             f"(((nsfw))), (((hdr, masterpiece, highest resolution, best quality, beautiful, raw image))), "
    #             f"(((extremely detailed, rendered))), "

    #         )
    #         # Simulating the time taken to generate the image
    #         sleep(1)  # wait for 5 seconds, this is just for demonstration, remove it if you don't need a delay

    #         img_size = 'square'  # width and height of each image

    #         # image sizes adjustment
    #         if img_size == 'landscape':
    #             width = 1080
    #             height = 566
    #         elif img_size == 'portrait':
    #             width = 1080
    #             height = 1350
    #         else:
    #             width = 512
    #             height = 768

    #         # Generate a unique tracking ID for this image generation request
    #         track_id = uniqueId

    #         if quality == 'extreme':
    #             self_attention = "yes"
    #         else:
    #             self_attention = "no"


    #         # Generate the Stable Diffusion image URLs based on the entered text
    #         url, payload = generate_stable_image_from_text(text_input=text_input, num_images=num_images,
    #                                                                negative_prompt=negative_prompt, width=width,
    #                                                                height=height,
    #                                                                track_id=track_id, seed=seed, self_attention=self_attention)

    #         # generated_image_urls = []
    #         # print(generated_image_urls)
    #         # app.logger.debug("Generated image URLs: %s", generated_image_urls)
    #         # breakpoint()
    #         send_request_to_third_party(url, payload)
    #         # if generated_image_urls == "Request send to Stable Diffusion.":
    #         return jsonify({'message': 'Image generation is in progress.','tracking_id': track_id})



    #     except Exception as e:
    #         import os, sys
    #         exc_type, exc_obj, exc_tb = sys.exc_info()
    #         fname = os.path.split(exc_tb.tb_frame.f_code.co_filename)[1]
    #         app.logger.error(exc_tb.tb_lineno)

    #         return jsonify({'error': str(e)}), 500

    app.logger.error("Exception occurred", exc_info=True)

    return render_template('index.html', image_url=[default_image_url])


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        user = User.query.filter_by(email=email).first()

        if user and user.check_password(password):
            if user.banned:
                flash("Your account has been banned!")
                return redirect(url_for('login'))
            elif not user.email_confirmed:
                if datetime.utcnow() > user.creation_date + timedelta(hours=1):
                    flash("Please confirm your email first!")
                    return redirect(url_for('login'))
            else:
                login_user(user)
                return redirect(url_for('home'))
        else:
            flash("Invalid email or password!")
            return redirect(url_for('login'))
    return render_template('login.html')


@app.route('/create-account', methods=['GET', 'POST'])
def create_account():
    if request.method == 'POST':
        nickname = request.form.get('nickname')
        email = request.form.get('email')
        password = request.form.get('password')
        confirm_password = request.form.get('confirm_password')

        if password != confirm_password:
            flash("Passwords don't match!")
            return redirect(url_for('create_account'))

        new_user = User(nickname=nickname, email=email)
        new_user.set_password(password)

        db.session.add(new_user)
        db.session.commit()

        # Send confirmation email
        token = generate_confirmation_token(new_user.email)
        confirm_url = url_for('confirm_email', token=token, _external=True)
        html = render_template('activate.html', confirm_url=confirm_url)
        subject = "Please confirm your email"
        send_email(new_user.email, subject, html)

        flash('Account created successfully! Please check your email for the confirmation link.')
        return redirect(url_for('login'))

    return render_template('create-account.html')


@app.route('/unconfirmed_account', methods=['GET', 'POST'])
def unconfirmed_account():
    if request.method == 'POST':
        # Resend the confirmation email logic here.
        email = request.form.get('email')
        user = User.query.filter_by(email=email).first()
        if user:
            token = generate_confirmation_token(user.email)
            confirm_url = url_for('confirm_email', token=token, _external=True)
            html = render_template('activate.html', confirm_url=confirm_url)
            subject = "Please confirm your email"
            send_email(user.email, subject, html)
            flash('Confirmation email sent. Please check your inbox.')
        else:
            flash('Email not found!')
    return render_template('unconfirmed.html')


@app.route('/resend_verification', methods=['GET', 'POST'])
def resend_verification():
    if request.method == 'POST':
        email = request.form.get('email')
        user = User.query.filter_by(email=email).first()

        if user:
            if user.email_confirmed:
                flash('Your email is already confirmed!', 'info')
            else:
                token = generate_confirmation_token(user.email)
                confirm_url = url_for('confirm_email', token=token, _external=True)
                html = render_template('activate.html', confirm_url=confirm_url)
                subject = "Please confirm your email"
                send_email(user.email, subject, html)

                flash('Verification email has been resent. Please check your email!', 'success')
                return redirect(url_for('login'))
        else:
            flash('Email not found!', 'danger')

    return render_template('resend_verification.html')


@app.route('/ban_user', methods=['POST'])
def ban_user():
    # Ensure this endpoint is properly secured and only accessible by admins!
    user_id = request.form.get('user_id')
    user = User.query.filter_by(id=user_id).first()
    if user:
        user.banned = True
        db.session.commit()
        return "User banned successfully!"
    else:
        return "User not found!"


@app.route('/edit', methods=['GET', 'POST'])
def edit():
    return render_template('edit.html')

@app.route('/subscription', methods=['GET', 'POST'])
def subscription():
    return render_template('subscription.html')


@app.route('/logout')
@login_required
def logout():
    logout_user()
    return "Logged out successfully!"


@login_manager.user_loader
def load_user(user_id):
    return User.query.filter_by(id=int(user_id)).first()


@app.route('/api/gallery', methods=['GET'])
def api_gallery():
    page = request.args.get('page', 1, type=int)
    filter_type = request.args.get('filter_type', 'newest')  # default is 'newest'

    per_page = 12

    # Limit the page to a maximum of 2
    if page > 5:
        return jsonify([])

    # Now we will filter based on the filter_type
    if filter_type == 'newest':
        images = Image.query.order_by(Image.id.desc())
    elif filter_type == 'hot':
        # Assuming Image has a 'views' column, and hotness is determined by views
        images = Image.query.order_by(Image.views.desc())
    elif filter_type == 'most-liked':
        # Assuming Image has a 'likes' column
        images = Image.query.order_by(Image.likes.desc())
    else:
        images = Image.query.order_by(Image.id.desc())  # default order

    paginated_images = images.paginate(page=page, per_page=per_page, error_out=False)

    if paginated_images and hasattr(paginated_images, 'items'):
        # We will send the images as a JSON response
        images_data = [
            {
                'id': image.id,
                'url': image.url,
                'likes': image.likes,
                'views': image.views,
                'text_input': image.text_input or "No description"

            } for image in paginated_images.items
        ]

        return jsonify(images_data)
    else:
        return jsonify([])


@app.route('/gallery', methods=['GET'])
def public_gallery():
    images = Image.query.filter_by(user_id=None).order_by(Image.id.desc()).limit(16).all()  # only public images
    return render_template('gallery.html', images=images, title="Public Gallery")


@app.route('/private_gallery', methods=['GET'])
def private_gallery():
    if current_user.is_authenticated:  # Only for logged-in users
        images = Image.query.filter_by(user_id=current_user.id, in_private_gallery=True).order_by(
            Image.id.desc()).limit(16).all()
        return render_template('gallery.html', images=images, title="Private Gallery")
    else:
        abort(403)  # Forbidden access if not authenticated


@app.route('/api/update-views', methods=['POST'])
def update_views():
    image_id = request.json.get('image_id')

    if not image_id:
        return jsonify({"error": "Missing image_id"}), 400

    image = Image.query.get(image_id)
    if not image:
        return jsonify({"error": "Image not found"}), 404

    # Increase the views count
    image.views += 1
    db.session.commit()

    return jsonify({"success": True, "views": image.views})


@app.route('/api/update-likes', methods=['POST'])
def update_likes():
    session = db.session
    data = request.get_json()
    image_id = data.get('image_id')
    try:
        image = Image.query.get(image_id)
        if image:
            image.likes += 1
            db.session.commit()
            return jsonify(success=True, likes=image.likes)
        else:
            return jsonify(success=False, message="Image not found"), 404
    except Exception as e:
        app.logger.error(f"Error updating likes: {str(e)}")
        return jsonify(success=False, message=str(e)), 500


@app.route('/report', methods=['POST'])
def report():
    data = request.get_json()
    report_text = data.get('reason')
    tracking_id = data.get('tracking_id')
    # Now that you have the report, you could log it, save it in a database, send it in an email, etc.
    # For now, let's just log it:
    app.logger.info(f'Received report: {report_text}, tracking ID: {tracking_id}')
    return {'message': 'Report received'}


@app.route('/checkdb', methods=['GET'])
def checkdb():
    images = Image.query.all()
    return jsonify([image.url for image in images])


@app.route('/is_premium', methods=['GET'])
def is_premium():
    if current_user.is_authenticated:
        return jsonify({'is_premium': current_user.premium})
    return jsonify({'is_premium': False})


def send_email(to, subject, template):
    msg = Message(
        subject,
        recipients=[to],
        html=template,
        sender=app.config['MAIL_USERNAME']
    )
    mail.send(msg)


@app.route('/confirm/<token>')
def confirm_email(token):
    try:
        email = confirm_token(token)  # You'll need to implement this function
    except:
        flash('The confirmation link is invalid or has expired.', 'danger')
    user = User.query.filter_by(email=email).first_or_404()
    if user.email_confirmed:
        flash('Account already confirmed. Please login.', 'success')
    else:
        user.email_confirmed = True
        db.session.add(user)
        db.session.commit()
        flash('You have confirmed your account. Thanks!', 'success')
    return redirect(url_for('login'))


def generate_confirmation_token(email):
    serializer = URLSafeTimedSerializer(app.config['SECRET_KEY'])
    return serializer.dumps(email, salt=app.config['SECURITY_PASSWORD_SALT'])


def confirm_token(token, expiration=3600):
    serializer = URLSafeTimedSerializer(app.config['SECRET_KEY'])
    try:
        email = serializer.loads(
            token,
            salt=app.config['SECURITY_PASSWORD_SALT'],
            max_age=expiration
        )
    except:
        return False
    return email


@app.route('/create-checkout-session', methods=['POST'])
@login_required
def create_checkout_session():
    # Check if the user is authenticated
    if not current_user.is_authenticated:
        return jsonify({'redirect': True, 'redirect_url': "http://localhost:5001/login?next=/create-checkout-session"}), 401    # Retrieve user information and other details as needed
    user_id = current_user.id

    try:
        # Create a Checkout session
        session = stripe.checkout.Session.create(
            payment_method_types=['card'],

            mode='subscription',  # or 'payment' if you're selling a one-time product
            success_url='https://www.aihentaigenerator.net/success?session_id={CHECKOUT_SESSION_ID}',
            cancel_url='https://www.aihentaigenerator.net/cancel',
            customer_email=current_user.email,
            billing_address_collection='required',  # Require billing address
            discounts=[{
                'coupon': '6eh4nvtc',
            }],
            line_items=[
                {
                    'price': 'price_1OEYyeJInIllC3FupVpas4Ok',
                    'quantity': 1,

                },
            ],
            metadata={
                'user_id': user_id,
                'referral': request.form.get('referral'),  # Add this line to include referral ID

            },
        )

        # Update the user's premium status in your database
        user = User.query.get(user_id)
        user.premium = True
        db.session.commit()

        return jsonify({'sessionId': session.id})
    except stripe.error.StripeError as e:
        return jsonify({'error': str(e)}), 400


@app.route('/subscribe', methods=['POST'])
def subscribe():
    # Get the user ID of the logged-in user (assuming you have user authentication set up)
    user_id = current_user.id

    # Create a Stripe Customer or retrieve an existing one (associated with the user's email)
    stripe_customer = create_or_get_stripe_customer(user_id)

    # Create a Stripe Subscription for the customer
    try:
        subscription = stripe.Subscription.create(
            customer=stripe_customer.id,
            items=[
                {
                    'price': 'price_1OEYyeJInIllC3FupVpas4Ok',  # Replace with your actual price ID from Stripe
                },
            ],
        )

        # Update the user's premium status in your database
        user = User.query.get(user_id)
        print(f"User's premium status before update: {user.premium}")

        user.premium = True
        db.session.commit()
        print(f"User's premium status after update: {user.premium}")

        return jsonify({'message': 'Subscription successful'})
    except stripe.error.StripeError as e:
        return jsonify({'error': str(e)}), 400


def create_or_get_stripe_customer(user_id):
    # Check if a Stripe customer exists with the user's email
    user = User.query.get(user_id)
    email = user.email

    # Search for a Stripe customer with the same email
    existing_customer = stripe.Customer.list(email=email).data

    if existing_customer:
        return existing_customer[0]  # Use the first matching customer
    else:
        # Create a new Stripe customer with the user's email
        customer = stripe.Customer.create(email=email)
        return customer


@app.route('/stripe-webhook', methods=['POST'])
def stripe_webhook():
    # Retrieve the webhook event data from the request
    payload = request.data
    sig_header = request.headers.get('Stripe-Signature')

    try:
        # Verify the webhook signature to ensure it's a legitimate Stripe event
        event = stripe.Webhook.construct_event(
            payload, sig_header, os.getenv('STRIPE_WEBHOOK_SECRET')
        )

        print("Webhook Payload:")
        print(payload)
        print("Webhook Event:")
        print(event)

        # Handle different event types here
        if event.type == 'customer.subscription.created':
            # Check if 'customer' and 'data' attributes exist before accessing them
            if hasattr(event, 'data') and hasattr(event.data, 'object'):
                subscription = event.data.object
                # Update your database with subscription information

        # Handle other webhook event types as needed

        return '', 200

    except ValueError as e:
        return 'Invalid payload', 400
    except stripe.error.SignatureVerificationError as e:
        return 'Invalid signature', 400


@app.route('/success')
def success():
    session_id = request.args.get('session_id')
    if not session_id:
        abort(403, description="Invalid access")  # abort with a 403 Forbidden status code

    try:
        # Verify the session ID with Stripe
        session = stripe.checkout.Session.retrieve(session_id)

        # Ensure the session was successful. You can add more checks if necessary.
        if session.payment_status != 'paid':
            abort(403, description="Invalid access")  # abort with a 403 Forbidden status code

        # If session is valid and payment was successful, render the success page.
        return render_template('success.html')

    except stripe.error.StripeError:
        abort(403, description="Invalid access")  # abort with a 403 Forbidden status code


@app.route('/cancel')
def cancel():
    # This route handles payment cancellation.
    # You can render a page with a cancellation message and options.
    return render_template('cancel.html')

@app.route('/image-explore', methods=['GET', 'POST'])
def imageExplore():
    return render_template('image-explore.html')

@app.route('/chat', methods=['GET', 'POST'])
def chat():
    return render_template('chat.html')

conversation_histories = {}

@socketio.on('connect')
def handle_connect():
    print("Client connected, session id:", request.sid)

@socketio.on('disconnect')
def handle_disconnect():
    # Remove the user from active_users upon disconnection
    for session_id, sid in active_users.items():
        if sid == request.sid:
            del active_users[session_id]
            break

@socketio.on('user_connected')  # Changed event name here
def handle_user_connected(data):
    track_id = data['track_id']

    active_users[track_id] = [{"track_id":track_id, "session_id":request.sid, "no_watermark":"", "text_input":"", "negative_prompt":""}]
    print(active_users)
    print(f"Connected with track id {track_id} and session id {request.sid}")


@socketio.on('send_message')
async def handle_send_message(data):
    from text_generation import generate_reply_HF
    try:
        question = data['question']
        character = data['character']
        state = data['state']
        
        state['ban_eos_token'] = False
        state['custom_token_bans'] = False
        state['auto_max_new_tokens'] = False

        client_id = request.sid
        if client_id not in conversation_histories:
            conversation_histories[client_id] = f"User: {question}\n{character}:"
        else:
            conversation_histories[client_id] += f"\nUser: {question}\n{character}:"

        modified_question = conversation_histories[client_id]
        print(f"Modified question (conversation history): {modified_question}")

        response_generator = generate_reply_HF(modified_question, question, None, state, character=character)
        print(f"response_generator = {response_generator}")

        character_response = ""
        for output in response_generator:
            print(f"output chunk: {output}")
            character_response += output

        conversation_histories[client_id] += f" {character_response.strip()}"

        response1 = {
            'results': [
                {
                    'history': {
                        'internal': [],
                        'visible': [question, character_response.strip()]
                    }
                }
            ]
        }
        print(f"response1 = {response1}")
        await emit('receive_message', json.dumps(response1), to=client_id)
    except Exception as e:
        error_msg = str(e)
        print(f"Error: {error_msg}")
        await emit('error', {'error': error_msg}, to=client_id)



@socketio.on('generate_image')
def handle_generate_image(data):
        data = json.loads(data)

        text_input = data.get('text_input').lower()
        negative_prompt = data.get('negative_prompt')
        gender = data.get('gender')
        ethnicity = data.get('ethnicity')
        hairColor = data.get('hairColor')
        face = data.get('face')
        hairStyle = data.get('hairStyle')
        eyesColor = data.get('eyesColor')
        outfit = data.get('outfit')
        places = data.get('places')
        race = data.get('race')
        accessories = data.get('accessories')
        seed = data.get('seed', None)  # Get the seed value from the request data
        num_images = data.get('num_images', 1)
        uniqueId = data.get('uniqueId', 1)

        # premium featyres
        private_gallery = False
        no_watermark = "no"  # premium features
        quality = "utlra"
        img_size = data.get('img_size', 'square')

        try:
            seed = int(seed) if seed else None
        except ValueError:
            seed = None  # Reset to None if the conversion fails

        # If user is premium, override some values
        if current_user.is_authenticated and current_user.premium:
            no_watermark = data.get('no_watermark', "no")
            private_gallery = data.get('private_gallery', True)
            img_size = "max"
            quality = data.get('quality')

            # Replace banned words in text_input with empty string
        for word in BANNED_WORDS:
            text_input = text_input.replace(word, "")

        text_input = (
            f"{gender} {ethnicity}, {race}, ((age 20-30)), with {hairColor} hair, "
            f"{face}, Hair Style: {hairStyle}, {eyesColor}, {outfit}, "
            f"In {places}, With {accessories}, tall ((adult)), {text_input}, ((full body)), "
            f"(((nsfw))), (((hdr, masterpiece, highest resolution, best quality, beautiful, raw image))), "
            f"(((extremely detailed, rendered))), "

        )
        # Simulating the time taken to generate the image
        sleep(1)  # wait for 5 seconds, this is just for demonstration, remove it if you don't need a delay

        img_size = 'square'  # width and height of each image

        # image sizes adjustment
        if img_size == 'landscape':
            width = 1024
            height = 512
        elif img_size == 'portrait':
            width = 768
            height = 1024
        else:
            width = 512
            height = 768

        # Generate a unique tracking ID for this image generation request
        track_id = uniqueId
        if quality == 'extreme':
            self_attention = "yes"
        else:
            self_attention = "no"

        # Check if the track_id exists in the dictionary
        if track_id in active_users:
            # Iterate through each dictionary in the list associated with the track_id
            for user_dict in active_users[track_id]:
                # Update the values
                user_dict["no_watermark"] = no_watermark
                user_dict["text_input"] = text_input
                user_dict["negative_prompt"] = negative_prompt
        else:
            print(f"Track ID {track_id} not found in active_users.")

        # Generate the Stable Diffusion image URLs based on the entered text
        url, payload = generate_stable_image_from_text(text_input=text_input, num_images=num_images,
                                                                negative_prompt=negative_prompt, width=width,
                                                                height=height,
                                                                track_id=track_id, seed=seed, self_attention=self_attention)

        send_request_to_third_party(url, payload)


def convert_images_to_base64(images, track_id):
    # Pass the first generated image URL to the template

    if track_id in active_users:
        no_watermark = active_users.get(track_id)[0]['no_watermark']
        text_input = active_users.get(track_id)[0]['text_input']
        negative_prompt = active_users.get(track_id)[0]['negative_prompt']
    
        imageList = []
        for image_url in images:
            # Fetch the image
            response = requests.get(image_url, stream=True)
            response.raw.decode_content = True  # handle spurious Content-Encoding
            image = PILImage.open(response.raw)

            if not (current_user.is_authenticated and current_user.premium and no_watermark == "yes"):
                # Apply the watermark only if the user is not premium or if they haven't chosen to remove the watermark
                draw = ImageDraw.Draw(image)
                font = ImageFont.truetype(FONT_PATH, 30)  # Using Arial font and setting size to 30
                draw.text((10, 5), "AIhentaigenerator.net", font=font, fill=(255, 255, 255, 255))
                draw.text((10, 710), "AIhentaigenerator.net", font=font, fill=(255, 255, 255, 255))

            # Convert image back to data URL for direct display
            buffered = BytesIO()
            image.save(buffered, format="PNG")
            img_str = "data:image/png;base64," + base64.b64encode(buffered.getvalue()).decode()

            imageList.append(img_str)

            new_image = Image(
                url=img_str,
                text_input=text_input,
                negative_prompt=negative_prompt,
                tracking_id=track_id
            )

            if private_gallery:
                new_image.in_private_gallery = True

            if current_user.is_authenticated:
                new_image.user_id = current_user.id

            # Use the watermarked image data URL
            db.session.add(new_image)  # Add new Image to the session
            db.session.commit()  # Commit the session
            # breakpoint()
        return imageList


@app.route('/webhook', methods=['POST'])
def webhook():
    if request.method == 'POST':
        print("Data received from Webhook is: ", request.json)
        # imageList = json.loads(request.data)['output']
        data = json.loads(request.data)
        print("not authorized",current_user.is_authenticated)
        status = data['status']
        track_id = data['track_id']
        images = data['output'] if status == 'success' else []
        recipient_sid = active_users.get(track_id)[0]['session_id']
        print(active_users.get(track_id)[0])
        if recipient_sid:
            if status == 'success':
                images = convert_images_to_base64(images, track_id)
                # print(images)
                socketio.emit('webhook', {'status': 'success', 'images': images, 'uniqueId': track_id}, room=recipient_sid)
            elif status == 'error' and data.get('message') == 'rate limit reached':
                socketio.emit('webhook', {'status': 'rateLimitExceeded', 'images': [], 'uniqueId': track_id}, room=recipient_sid)
            else:
                socketio.emit('webhook', {'status': 'error', 'images': [], 'uniqueId': track_id}, room=recipient_sid)

        return "Webhook received!"




if __name__ == '__main__':
    with app.app_context():
        db.create_all()  # Ensure you're in an application context when running this.

    port = int(os.environ.get("PORT", 5432))
    app.logger.setLevel(logging.INFO)
    # app.run(host='0.0.0.0', port=port, debug=os.environ.get("FLASK_DEBUG", False))
    socketio.run(app, host='0.0.0.0', port=port, debug=os.environ.get("FLASK_DEBUG", False))
