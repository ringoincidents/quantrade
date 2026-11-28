FROM python:3.12-alpine
WORKDIR /srv
COPY index.html /srv/index.html
ENV PYTHONDONTWRITEBYTECODE=1
USER 65534:65534
CMD ["sh", "-c", "exec python -m http.server ${PORT:-8080} --bind 0.0.0.0 --directory /srv"]
