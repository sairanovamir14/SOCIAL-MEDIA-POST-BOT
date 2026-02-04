from starlette.middleware.sessions import SessionMiddleware
from fastapi import FastAPI, Request, Form
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from fastapi.responses import RedirectResponse

from database import engine, Base, SessionLocal
from models import User

from passlib.context import CryptContext
import secrets
from sqlalchemy.orm import Session

# -----------------------

app = FastAPI()

app.add_middleware(
    SessionMiddleware,
    secret_key="super-secret-key"
)

Base.metadata.create_all(bind=engine)

templates = Jinja2Templates(directory="../frontend/templates")
app.mount("/static", StaticFiles(directory="../frontend/static"), name="static")

pwd_context = CryptContext(
    schemes=["pbkdf2_sha256"],
    deprecated="auto"
)

# -----------------------
# PASSWORDS
# -----------------------

def hash_password(password: str):
    return pwd_context.hash(password[:72])

def verify_password(password: str, hashed: str):
    return pwd_context.verify(password, hashed)

# -----------------------
# CURRENT USER
# -----------------------

def get_current_user(request: Request):
    user_id = request.session.get("user_id")

    if not user_id:
        return None

    db = SessionLocal()
    user = db.query(User).filter(User.id == user_id).first()
    db.close()

    return user

# -----------------------
# PAGES
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

# -----------------------

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
        db.close()
        return templates.TemplateResponse(
            "login.html",
            {
                "request": request,
                "error": "Invalid credentials"
            }
        )

    request.session["user_id"] = user.id
    db.close()

    return RedirectResponse("/dashboard", status_code=302)

# -----------------------
# DASHBOARD
# -----------------------

@app.get("/dashboard")
def dashboard(request: Request):
    user = get_current_user(request)

    if not user:
        return RedirectResponse("/login", status_code=302)

    return templates.TemplateResponse(
        "dashboard.html",
        {
            "request": request,
            "email": user.email,
            "token": user.api_token
        }
    )

# -----------------------
# LOGOUT
# -----------------------

@app.get("/logout")
def logout(request: Request):
    request.session.clear()
    return RedirectResponse("/login", status_code=302)

@app.get("/profile")
def profile_redirect(request: Request):
    user = get_current_user(request)

    if user:
        return RedirectResponse("/dashboard", status_code=302)
    else:
        return RedirectResponse("/login", status_code=302)
