FROM python:3.12-slim
WORKDIR /app
COPY verification/research-worker/metadata_probe.py verification/research-worker/inference_pilot.py /app/
RUN python metadata_probe.py --test && python inference_pilot.py --test
ENV PYTHONUNBUFFERED=1
USER 65534:65534
CMD ["python", "inference_pilot.py"]
