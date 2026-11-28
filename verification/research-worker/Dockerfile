FROM python:3.12-slim
WORKDIR /app
COPY verification/research-worker/metadata_probe.py /app/metadata_probe.py
RUN python metadata_probe.py --test
ENV PYTHONUNBUFFERED=1
USER 65534:65534
CMD ["python", "metadata_probe.py"]
