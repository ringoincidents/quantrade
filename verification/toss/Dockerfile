FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /probe
RUN pip install --no-cache-dir requests==2.32.5 websocket-client==1.8.0
COPY verification/toss/probe.py verification/toss/test_probe.py ./
RUN python -m unittest -v test_probe
USER 65534:65534
CMD ["python","-B","/probe/probe.py"]
