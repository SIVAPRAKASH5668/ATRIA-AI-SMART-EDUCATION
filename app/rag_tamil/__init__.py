from flask import Blueprint

bp = Blueprint('rag_tamil', __name__)

from . import routes