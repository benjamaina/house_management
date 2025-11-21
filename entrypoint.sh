#!/bin/sh

# Run migrations
python manage.py makemigrations
python manage.py migrate

# Then start the server
exec python manage.py runserver 0.0.0.0:8000
