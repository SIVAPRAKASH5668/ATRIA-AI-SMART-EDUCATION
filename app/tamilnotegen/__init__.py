from flask import Blueprint

bp = Blueprint('tamilnotegen', __name__)

from . import routes