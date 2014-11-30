# coding=utf-8

import threading
from functools import wraps


def debounce(wait_millis):
    """ Decorator that will postpone a functions
        execution until after wait_millis millisecs
        have elapsed since the last time it was invoked. """
    def wrapper(func):
        def debounced(*args, **kwargs):

            def call_func():
                func(*args, **kwargs)

            try:
                debounced.timer.cancel()
            except AttributeError:
                pass
            debounced.timer = threading.Timer(wait_millis / 1000.0, call_func)
            debounced.timer.start()

        return debounced
    return wrapper


def guarded(func):
    """ Decorator that guards func's thread reentrancy """
    lock = threading.Semaphore()

    @wraps(func)
    def wrapper(*args, **kwargs):
        with lock:
            r = func(*args, **kwargs)

        return r

    return wrapper
