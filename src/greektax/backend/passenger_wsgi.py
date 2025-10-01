"""WSGI entrypoint for deploying the GreekTax backend on cPanel."""

from app import create_app

# cPanel's Passenger expects a module-level variable named ``application``.
application = create_app()
