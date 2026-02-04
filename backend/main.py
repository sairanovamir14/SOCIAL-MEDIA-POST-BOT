import os
from dotenv import load_dotenv

load_dotenv()

ADMIN_EMAIL = os.getenv("ADMIN_EMAIL")


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

    # 👉 ЕСЛИ АДМИН
    if user.email == ADMIN_EMAIL:
        return RedirectResponse("/admin", status_code=302)

    # 👉 ЕСЛИ ОБЫЧНЫЙ ЮЗЕР
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

# -----------------------
# ADMIN PANEL
# -----------------------

@app.get("/admin")
def admin_panel(request: Request):
    user = get_current_user(request)

    if not user:
        return RedirectResponse("/login", status_code=302)

    if user.email != ADMIN_EMAIL:
        return RedirectResponse("/dashboard", status_code=302)

    db = SessionLocal()
    users = db.query(User).all()
    db.close()

    return templates.TemplateResponse(
        "admin.html",
        {
            "request": request,
            "users": users
        }
    )

# -----------------------
# ADMIN ACTIONS
# -----------------------

@app.post("/admin/unlink/{user_id}")
def admin_unlink(user_id: int, request: Request):
    user = get_current_user(request)
    if not user or user.email != ADMIN_EMAIL:
        return RedirectResponse("/login", status_code=302)

    db = SessionLocal()
    target = db.query(User).filter(User.id == user_id).first()
    if target:
        target.tg_id = None
        db.commit()
    db.close()

    return RedirectResponse("/admin", status_code=302)


@app.post("/admin/reset-token/{user_id}")
def admin_reset_token(user_id: int, request: Request):
    user = get_current_user(request)
    if not user or user.email != ADMIN_EMAIL:
        return RedirectResponse("/login", status_code=302)

    db = SessionLocal()
    target = db.query(User).filter(User.id == user_id).first()
    if target:
        target.api_token = secrets.token_hex(16)
        db.commit()
    db.close()

    return RedirectResponse("/admin", status_code=302)

@app.post("/admin/delete/{user_id}")
def admin_delete_user(user_id: int, request: Request):
    user = get_current_user(request)
    if not user or user.email != ADMIN_EMAIL:
        return RedirectResponse("/login", status_code=302)

    db = SessionLocal()
    target = db.query(User).filter(User.id == user_id).first()
    if target:
        db.delete(target)
        db.commit()
    db.close()

    return RedirectResponse("/admin", status_code=302)
