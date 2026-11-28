FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app
COPY verification/private-office/server.py verification/private-office/test_server.py verification/private-office/portfolio_projection.py verification/private-office/test_portfolio_projection.py verification/private-office/portfolio_demo.py ./
RUN python -m unittest -v test_server test_portfolio_projection
USER 65534:65534
CMD ["python","-B","/app/server.py"]
