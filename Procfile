web: gunicorn -w 4 -b 0.0.0.0:$PORT --timeout 60 --preload wsgi:app
release: flask db upgrade
