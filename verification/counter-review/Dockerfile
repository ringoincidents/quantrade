FROM python:3.12-slim
WORKDIR /app
ENV PYTHONPATH=/app PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1
COPY research/decision_review/budget_ledger.py research/decision_review/decision_review.py /app/research/decision_review/
COPY quantrade/capabilities/review_gate.py /app/quantrade/capabilities/
COPY verification/counter-review/review_pilot.py /app/
RUN python review_pilot.py --test
USER 65534:65534
CMD ["python","review_pilot.py"]
