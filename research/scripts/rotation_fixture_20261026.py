"""QuanTrade retrospective illustration. No real positions, no order authorization.
Prices are 2026-10-20 OPEN (IONQ/TE), 2026-10-21 OPEN (SOXL),
and 2026-10-23 CLOSE (SOXL). Hypothetical rule was fixed ex post,
NOT a validated strategy or out-of-sample backtest.
"""
from dataclasses import dataclass
from decimal import Decimal
from datetime import date, timedelta
import unittest

D = Decimal
FEE = D('0.001')
SLIP = D('0.001')

@dataclass(frozen=True)
class Event:
    day: str
    action: str
    ticker: str
    qty: int
    reference: Decimal
    cash_effect: Decimal
    idempotency_key: str

def next_business_day(day):
    # Weekends handled; official NYSE/DTCC holidays still need a calendar feed.
    due=day+timedelta(days=1)
    while due.weekday() >= 5: due += timedelta(days=1)
    return due

class Ledger:
    def __init__(self):
        self.available = D('0')
        self.pending = []
        self.positions = {}
        self.events = []
        self.keys = set()
    def settle(self, day):
        remaining=[]
        for due, amount in self.pending:
            if due <= day: self.available += amount
            else: remaining.append((due,amount))
        self.pending=remaining
    def trade(self, day, action, ticker, qty, reference, key):
        if key in self.keys: return False
        if qty <= 0: raise ValueError('invalid qty')
        ref=D(str(reference)); gross=ref*qty
        if action == 'BUY':
            cost=gross*(1+SLIP)*(1+FEE)
            if cost>self.available: raise ValueError('unsettled or insufficient cash')
            self.available-=cost
            self.positions[ticker]=self.positions.get(ticker,0)+qty
            effect=-cost
        elif action == 'SELL':
            if self.positions.get(ticker,0)<qty: raise ValueError('unowned shares')
            proceeds=gross*(1-SLIP)*(1-FEE)
            self.positions[ticker]-=qty
            self.pending.append((next_business_day(day),proceeds))
            effect=proceeds
        else: raise ValueError('invalid side')
        self.keys.add(key)
        self.events.append(Event(day.isoformat(),action,ticker,qty,ref,effect,key))
        return True

def run_case():
    l=Ledger()
    l.positions={'IONQ':10,'TE':100}
    t0=date(2026,10,20); t1=date(2026,10,21); t2=date(2026,10,23)
    l.trade(t0,'SELL','IONQ',10,'30.28','ionq-exit')
    l.trade(t0,'SELL','TE',100,'2.47','te-exit')
    assert l.available==0
    l.settle(t1)
    cash_only=l.available
    l.trade(t1,'BUY','SOXL',1,'102.86','soxl-entry')
    l.trade(t2,'SELL','SOXL',1,'83.56','soxl-exit')
    l.settle(date(2026,10,26))
    return l, cash_only

class Tests(unittest.TestCase):
    def test_unsettled_cash_blocks_purchase(self):
        l=Ledger(); l.positions={'IONQ':10}; day=date(2026,10,20)
        l.trade(day,'SELL','IONQ',10,'30.28','sale')
        with self.assertRaises(ValueError): l.trade(day,'BUY','SOXL',1,'100','buy')
    def test_tplus1_business_day_concept(self):
        l,c=run_case(); self.assertEqual(c,D('548.70094980'))
        self.assertEqual(next_business_day(date(2026,10,23)),date(2026,10,26))
    def test_idempotency(self):
        l=Ledger();l.positions={'TE':100};d=date(2026,10,20)
        self.assertTrue(l.trade(d,'SELL','TE',100,'2.47','same'))
        self.assertFalse(l.trade(d,'SELL','TE',100,'2.47','same'))
        self.assertEqual(len(l.events),1)
    def test_risk_no_leverage(self):
        l=Ledger();l.available=D('20')
        with self.assertRaises(ValueError): l.trade(date(2026,10,21),'BUY','SOXL',1,'102.86','buy')
    def test_after_cost_cash_vs_rotation(self):
        l,c=run_case()
        self.assertEqual(l.available,D('529.02809050'))
        self.assertEqual(c-l.available,D('19.67285930'))
        self.assertEqual(l.positions['SOXL'],0)

if __name__=='__main__':
    unittest.main(verbosity=2)
    l,c=run_case()
    print('CASH_ONLY',c,'ROTATION',l.available,'HOLD_MARK_TO_MARKET',D('541.70'))
    for e in l.events: print(e)
