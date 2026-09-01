from functools import wraps
from flask import abort

from flask_login import current_user


ADMIN_USER_EMAILS = {'ethannguyen764@gmail.com', 'ethan.nguyen.tutoring@gmail.com'}
def admin_whitelist_check(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        if not current_user.is_authenticated:
            abort(401)
        if current_user.email not in ADMIN_USER_EMAILS:
            abort(403)
        return f(*args, **kwargs)
    return wrapper