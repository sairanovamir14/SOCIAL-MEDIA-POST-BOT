from fastapi import FastAPI, Request, Form
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles

from database import engine, Base, SessionLocal
import models
from models import User

from passlib.context import CryptContext
import secrets
from sqlalchemy.orm import Session

# -----------------------

app = FastAPI()

Base.metadata.create_all(bind=engine)

templates = Jinja2Templates(directory="../frontend/templates")
app.mount("/static", StaticFiles(directory="../frontend/static"), name="static")

pwd_context = CryptContext(
    schemes=["pbkdf2_sha256"],
    deprecated="auto"
)

# -----------------------

def hash_password(password: str):
    return pwd_context.hash(password[:72])

def verify_password(password: str, hashed: str):
    return pwd_context.verify(password, hashed)

# -----------------------

@app.get("/")
def home(request: Request):
    return templates.TemplateResponse(
        "index.html",
        {"request": request}
    )

# -----------------------

@app.get("/register")
def register_page(request: Request):
    return templates.TemplateResponse(
        "register.html",
        {"request": request}
    )

# -----------------------

@app.post("/register")
def register_user(
    request: Request,
    email: str = Form(...),
    password: str = Form(...)
):
    db: Session = SessionLocal()

    hashed = hash_password(password)
    token = secrets.token_hex(16)

    user = User(
        email=email,
        password=hashed,
        api_token=token
    )

    db.add(user)
    db.commit()
    db.close()

    return templates.TemplateResponse(
        "register.html",
        {
            "request": request,
            "token": token
        }
    )

@app.get("/login")
def login_page(request: Request):
    return templates.TemplateResponse(
        "login.html",
        {"request": request}
    )

@app.post("/login")
def login_user(
    request: Request,
    email: str = Form(...),
    password: str = Form(...)
):
    db: Session = SessionLocal()

    user = db.query(User).filter(User.email == email).first()

    if not user or not verify_password(password, user.password):
        return templates.TemplateResponse(
            "login.html",
            {
                "request": request,
                "error": "Invalid credentials"
            }
        )

    return templates.TemplateResponse(
        "login.html",
        {
            "request": request,
            "token": user.api_token
        }
    )
