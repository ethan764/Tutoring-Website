from flask import Blueprint, render_template, request, redirect, url_for
from sqlalchemy import and_, cast, String
from flask_login import login_required

personal_bp = Blueprint("personal", __name__)

