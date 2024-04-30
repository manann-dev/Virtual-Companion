from flask import Flask, jsonify, request, abort
from flask_jwt_extended import JWTManager, jwt_required, get_jwt_identity, create_access_token, current_user


app = Flask(__name__)
app.config['JWT_SECRET_KEY'] = 'super-secret'  # Change this!
jwt = JWTManager(app)



def get_current_user():
    try:
        current_user = get_jwt_identity()
        if current_user is None:
            abort(401, description="Could not validate credentials")
    except Exception as e:
        abort(401, description=str(e))
    return {"username": current_user}
