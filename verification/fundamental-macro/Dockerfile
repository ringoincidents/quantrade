FROM python:3.12-slim
WORKDIR /probe
COPY verification/fundamental-macro/source_probe.py /probe/provider_probe.py
RUN python /probe/provider_probe.py --test
ENV PYTHONUNBUFFERED=1
USER 65534:65534
CMD ["python", "-B", "/probe/provider_probe.py"]
