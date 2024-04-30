from flask import Flask, jsonify, request, abort
from flask_jwt_extended import JWTManager, create_access_token, jwt_required, get_jwt_identity
from passlib.context import CryptContext
from datetime import timedelta
from typing import Optional
from redis__db import create_user, get_user, update_user, delete_user, set_user_character, get_user_character
from pydantic import BaseModel


app = Flask(__name__)

# Configuration
app.config['JWT_SECRET_KEY'] = 'your_secret_key'  # Change this!
app.config['JWT_ACCESS_TOKEN_EXPIRES'] = timedelta(minutes=30)
jwt = JWTManager(app)

# Password context for hashing and verifying passwords
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# In-memory 'database'
fake_users_db = {
    "johndoe": {
        "username": "johndoe",
        "hashed_password": pwd_context.hash("secret")
    }
}

class User:
    def __init__(self, username, hashed_password):
        self.username = username
        self.hashed_password = hashed_password

def get_user(username):
    user = fake_users_db.get(username)
    if user:
        return User(username=user['username'], hashed_password=user['hashed_password'])
    return None

def authenticate_user(username, password):
    user = get_user(username)
    if not user:
        return False
    if not pwd_context.verify(password, user.hashed_password):
        return False
    return user

@app.route('/token', methods=['POST'])
def login_for_access_token():
    username = request.json.get('username', None)
    password = request.json.get('password', None)
    user = authenticate_user(username, password)
    if not user:
        return jsonify({"msg": "Bad username or password"}), 401

    access_token = create_access_token(identity=username)
    return jsonify(access_token=access_token, token_type='bearer')

@app.route('/users/me', methods=['GET'])
@jwt_required()
def read_users_me():
    current_user_username = get_jwt_identity()
    current_user = get_user(current_user_username)
    if current_user:
        return jsonify(username=current_user.username)
    return jsonify({"msg": "User not found"}), 404

if __name__ == '__main__':
    app.run(debug=True)
