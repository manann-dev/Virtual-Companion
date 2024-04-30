from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import Optional
from redis__db import create_user, get_user, update_user, delete_user, set_user_character, get_user_character
import jwt
from fastapi import FastAPI, HTTPException, Depends, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from pydantic import BaseModel
from passlib.context import CryptContext
from jose import jwt, JWTError
from typing import Optional

# Configuration
SECRET_KEY = "your_secret_key"
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30

app = FastAPI()

# Password context for hashing and verifying passwords
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# OAuth2PasswordBearer is a class that we instantiate to handle security
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

class User(BaseModel):
    username: str
    password: str

class UserInDB(User):
    hashed_password: str

class Token(BaseModel):
    access_token: str
    token_type: str

class TokenData(BaseModel):
    username: Optional[str] = None

fake_users_db = {
    "johndoe": {
        "username": "johndoe",
        "hashed_password": pwd_context.hash("secret")
    }
}

def get_user(db, username: str):
    if username in db:
        user_dict = db[username]
        return UserInDB(**user_dict)
    return None

def authenticate_user(fake_db, username: str, password: str):
    user = get_user(fake_db, username)
    if not user:
        return False
    if not pwd_context.verify(password, user.hashed_password):
        return False
    return user

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=15)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

@app.post("/token", response_model=Token)
def login_for_access_token(form_data: OAuth2PasswordRequestForm = Depends()):
    user = authenticate_user(fake_users_db, form_data.username, form_data.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": user.username}, expires_delta=access_token_expires
    )
    return {"access_token": access_token, "token_type": "bearer"}

@app.get("/users/me", response_model=User)
def read_users_me(current_user: User = Depends(authenticate_user)):
    return current_user

# class UserBase(BaseModel):
#     username: str

# class UserCreate(UserBase):
#     password: str

# class UserUpdate(BaseModel):
#     password: Optional[str] = None

# class LoginData(BaseModel):
#     username: str
#     password: str

# @app.post("/users/")
# def create_user_api(user: UserCreate):
#     try:
#         create_user(user.username, user.password)
#         return {"message": "User created successfully"}
#     except ValueError as e:
#         raise HTTPException(status_code=400, detail=str(e))


# @app.post("/login/")
# def login(login_data: LoginData):
#     username = login_data.username
#     password = login_data.password
#     if not username and not password:
#         raise HTTPException(status_code=401, detail="Invalid username or password")
#     token = jwt.encode({"sub": username, "exp": datetime.datetime.utcnow() + datetime.timedelta(hours=1)}, SECRET_KEY, algorithm=ALGORITHM)
#     return {"access_token": token, "token_type": "bearer"}

# @app.get("/users/{username}")
# def read_user_api(username: str):
#     user = get_user(username)
#     if user:
#         user['password'] = "******"
#         return user
#     else:
#         raise HTTPException(status_code=404, detail="User not found")

# @app.put("/users/{username}")
# def update_user_api(username: str, user: UserUpdate):
#     try:
#         update_user(username, user.dict(exclude_none=True))
#         return {"message": "User updated successfully"}
#     except ValueError as e:
#         raise HTTPException(status_code=404, detail=str(e))

# @app.delete("/users/{username}")
# def delete_user_api(username: str):
#     delete_user(username)
#     return {"message": "User deleted successfully"}


# @app.post("/select_character/")
# def select_character(username: str, character_name: str):
    
#     character = get_character(character_name)
#     if character is None:
#         raise HTTPException(status_code=404, detail="Character not found")

#     session_key = f"session:{username}"
#     redis_client.hmset(session_key, {"character": character_name})
#     return {"message": "Character selected successfully"}


# @app.post("/select-character/{username}/{character}")
# async def select_character(username: str, character_: str):
#     try:
#         select_character(username, character)
#         return {"message": "Character selected successfully"}
#     except ValueError as e:
#         raise HTTPException(status_code=404, detail=str(e))