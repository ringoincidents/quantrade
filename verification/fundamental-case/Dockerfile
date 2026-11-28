FROM python:3.12-slim
WORKDIR /app
ENV PYTHONPATH=/app PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1
COPY quantrade/capabilities/dart_fundamental_provider.py quantrade/capabilities/fundamental_evidence.py quantrade/capabilities/thesis_contract.py /app/quantrade/capabilities/
COPY verification/private-office/link_transport.py verification/private-office/research_link.py verification/private-office/work_lifecycle.py /app/
COPY verification/fundamental-case/case_pilot.py verification/fundamental-case/worker.py verification/fundamental-case/test_research_handoff.py /app/
RUN python case_pilot.py --test && python -m unittest -v test_research_handoff
USER 65534:65534
CMD ["python", "-B", "/app/worker.py"]
