# Assuming you have not changed the general structure of the template no modification is needed in this file.
from . import commands
from .lib import fusion360utils as futil


def run(context):
    try:
        commands.start()
    except:
        futil.handle_error('run')


def stop(context):
    try:
        futil.clear_handlers()

        commands.stop()

    except:
        futil.handle_error('stop')
