FROM python:3.12-slim
WORKDIR /app
COPY quantrade /app/quantrade
COPY verification/fundamental-case/case_pilot.py /app/case_pilot.py
RUN python -B /app/case_pilot.py --test
RUN mkdir -p /probe && cp /app/case_pilot.py /probe/provider_probe.py
ENV PYTHONPATH=/app PYTHONUNBUFFERED=1
USER 65534:65534
CMD ["python", "-B", "/probe/provider_probe.py"]
