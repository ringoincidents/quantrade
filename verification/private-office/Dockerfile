FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app
COPY verification/private-office/server.py verification/private-office/test_server.py verification/private-office/portfolio_projection.py verification/private-office/test_portfolio_projection.py verification/private-office/portfolio_demo.py verification/private-office/link_transport.py verification/private-office/link_gateway.py verification/private-office/test_link.py verification/private-office/report_demo.py verification/private-office/case_demo.py verification/private-office/risk_demo.py verification/private-office/market_demo.py verification/private-office/market_room.py verification/private-office/calendar_refresh.py verification/private-office/lab_view.py verification/private-office/founder_inbox.py verification/private-office/test_calendar_refresh.py verification/private-office/treasury_view.py verification/private-office/test_treasury_view.py verification/private-office/macro_view.py verification/private-office/bls_monthly.py verification/private-office/test_macro_view.py ./
COPY quantrade/workbench/entry_monitor.py quantrade/workbench/local_report.py quantrade/workbench/session_calendar.py /app/quantrade/workbench/
COPY quantrade/capabilities/cash_flow_valuation.py quantrade/capabilities/thesis_contract.py quantrade/capabilities/valuation_method_applicability.py /app/quantrade/capabilities/
COPY quantrade/capabilities/investment_case.py quantrade/capabilities/portfolio_opportunity.py quantrade/capabilities/risk_opinion.py quantrade/capabilities/valuation_crosscheck.py /app/quantrade/capabilities/
COPY research/qt_mri/asof_engine.py research/qt_mri/test_asof_engine.py ./
COPY research/market_data_vault/indicators.py research/market_data_vault/feature_bridge.py research/market_data_vault/multiframe.py research/market_data_vault/vault.py research/market_data_vault/treasury_pilot.py ./
RUN python -m unittest -v test_server test_portfolio_projection test_link test_asof_engine test_calendar_refresh test_treasury_view test_macro_view
USER 65534:65534
CMD ["python","-B","/app/server.py"]
