FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app
COPY verification/private-office/server.py verification/private-office/test_server.py verification/private-office/portfolio_projection.py verification/private-office/test_portfolio_projection.py verification/private-office/portfolio_demo.py verification/private-office/link_transport.py verification/private-office/link_gateway.py verification/private-office/test_link.py verification/private-office/report_demo.py verification/private-office/case_demo.py verification/private-office/risk_demo.py ./
COPY quantrade/workbench/entry_monitor.py quantrade/workbench/local_report.py /app/quantrade/workbench/
COPY quantrade/capabilities/cash_flow_valuation.py quantrade/capabilities/thesis_contract.py quantrade/capabilities/valuation_method_applicability.py /app/quantrade/capabilities/
COPY quantrade/capabilities/investment_case.py quantrade/capabilities/portfolio_opportunity.py quantrade/capabilities/risk_opinion.py quantrade/capabilities/valuation_crosscheck.py /app/quantrade/capabilities/
RUN python -m unittest -v test_server test_portfolio_projection test_link
USER 65534:65534
CMD ["python","-B","/app/server.py"]
