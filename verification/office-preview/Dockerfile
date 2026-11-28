FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app
COPY verification/office-preview/server.py verification/office-preview/index.html verification/office-preview/test_server.py ./
RUN python -m unittest -v test_server
USER 65534:65534
CMD ["python","-B","/app/server.py"]
