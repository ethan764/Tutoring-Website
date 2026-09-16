from flask import Blueprint, render_template, request, redirect, url_for

static_bp = Blueprint("static", __name__)

@static_bp.route('/')
def home():
    return render_template('home.html')

@static_bp.route('/about-me')
def about_me():
    return render_template('about_me.html')

@static_bp.route('/policies')
def policies():
    return render_template('policies.html')

@static_bp.route('/message/<message>')
def message(message):
    return render_template('message.html', message=message)