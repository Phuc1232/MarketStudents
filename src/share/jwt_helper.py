from functools import wraps


def admin_role(f):
    @wraps(f)
    def decorate_function(*args, **kwargs):
        pass
            

