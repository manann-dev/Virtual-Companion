import redis
from passlib.context import CryptContext


redis_client = redis.Redis(
  host='redis-16428.c330.asia-south1-1.gce.redns.redis-cloud.com',
  port=16428,
  password='hftcJafy6dKQ1gQYkxCfCqGeYhsQWmHe')

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def create_user(username: str, password: str):
    hashed_password = pwd_context.hash(password)    
    user_key = f"user:{username}"
    if redis_client.hexists(user_key, "username"):
        raise ValueError("User already exists")
    else:
        redis_client.hmset(user_key, {"username": username, "password": hashed_password})

def get_user(username: str):
    user_key = f"user:{username}"
    if redis_client.exists(user_key):
        user_data = redis_client.hgetall(user_key)
        user = {k.decode('utf-8'): v.decode('utf-8') for k, v in user_data.items()}
        return user
    else:
        return None

def update_user(username: str, update_fields: dict):
    user_key = f"user:{username}"
    if not redis_client.exists(user_key):
        raise ValueError("User does not exist")
    if "password" in update_fields:
        update_fields["password"] = pwd_context.hash(update_fields["password"])
    redis_client.hmset(user_key, update_fields)

def delete_user(username: str):
    user_key = f"user:{username}"
    redis_client.delete(user_key)


def authenticate_user(username: str, password: str):
    user = get_user(username)
    if user and pwd_context.verify(password, user['password']):
        return user
    return None

def set_user_character(username: str, character_name: str):
    user_key = f"user:{username}:character"
    redis_client.set(user_key, character_name)

def get_user_character(username: str):
    user_key = f"user:{username}:character"
    return redis_client.get(user_key).decode('utf-8')

