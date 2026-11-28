# GDP forecast experiment (QT-EXP-SPF-002)
Research only, #144; #142 production scope unchanged.
Run: python research/gdp_forecast/experiment.py /private/aligned.json
Tests: python -m unittest discover -s research/gdp_forecast -p 'test_*.py'
Input JSON keys actual, spf, iar: aligned chronological finite numeric arrays, annualized quarterly real GDP growth, first-release actuals, same target and horizon. Caller must independently verify alignment, release availability, rights and provenance; this module does not verify these. No raw source data committed. Source: Philadelphia Fed SPF error statistics 2025-08-22 tables 2,3,7, see #144.
Four warmup observations, fixed ridge penalty 25, expanding mean, trailing-four median, persistence, SPF/IAR and equal SPF/median blend. No adaptive model or trading signal. Output exploratory only. No production ledger integration, PIT certification, independent review or promotion. Future: immutable manifests, vintage-aware adapters, forecast ledger, locked holdout and independent review.
