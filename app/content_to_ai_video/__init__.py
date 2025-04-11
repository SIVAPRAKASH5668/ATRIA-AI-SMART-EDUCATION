# app/content_to_aivideo/__init__.py
from flask import Blueprint

bp = Blueprint('content_to_ai_video', __name__)

from . import routes
