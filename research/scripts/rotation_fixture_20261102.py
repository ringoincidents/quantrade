"""2026-11-02 hindsight paper-only SOXL rotation illustration. NOT ALPHA OR AN ORDER.
OHLC: StockAnalysis daily histories. Synthetic 100 IONQ + 100 TE shares, not client holdings.
10/26 open sells: IONQ $30.94, TE $2.24; US T+1 assumed available at 10/27 open;
10/27 SOXL buy open $95.04; 10/30 close IONQ $30.04, TE $2.70, SOXL $77.05.
Each fill has adverse 10bp slippage plus 10bp commission. No tax/FX/borrow/partial fills.
"""
from dataclasses import dataclass
from math import floor, isclose

FEE=0.001
SLIP=0.001
SELL_OPEN={"IONQ":30.94,"TE":2.24}
END_CLOSE={"IONQ":30.04,"TE":2.70,"SOXL":77.05}
SOXL_BUY=95.04
N=100

@dataclass(frozen=True)
class Result:
    name:str
    end_equity:float
    cash:float
    ionq_shares:int
    te_shares:int
    fees:float
    authority:str="PAPER_ONLY"

def sell(n,px):
    fill=px*(1-SLIP)
    fee=n*fill*FEE
    return n*fill-fee,fee

def buy_integer(cash,px):
    fill=px*(1+SLIP)
    n=floor((cash+1e-10)/(fill*(1+FEE)))
    fee=n*fill*FEE
    rem=cash-n*fill-fee
    assert rem>=-1e-8
    return n,max(0.0,rem),fee

def run(sell_ionq=False,sell_te=False,rotate=False):
    if rotate and not(sell_ionq or sell_te): raise ValueError("no sale funds")
    cash=0.0; fees=0.0
    for symbol,do in (("IONQ",sell_ionq),("TE",sell_te)):
        if do:
            net,fee=sell(N,SELL_OPEN[symbol]);cash+=net;fees+=fee
    if rotate:
        # T+1 cash availability is ASSUMED, not broker-verified.
        n,cash,fee=buy_integer(cash,SOXL_BUY);fees+=fee
        if n:
            net,fee=sell(n,END_CLOSE["SOXL"]);cash+=net;fees+=fee
    qi=0 if sell_ionq else N
    qt=0 if sell_te else N
    label=("sell_both" if sell_ionq and sell_te else
           "sell_ionq" if sell_ionq else "sell_te" if sell_te else "hold")
    return Result(label+("_rotate" if rotate else "_cash"),
                  cash+qi*END_CLOSE["IONQ"]+qt*END_CLOSE["TE"],
                  cash,qi,qt,fees)

def test():
    cases=[run(),run(sell_ionq=True),run(sell_te=True),
           run(sell_ionq=True,sell_te=True),
           run(sell_ionq=True,rotate=True),run(sell_te=True,rotate=True),
           run(sell_ionq=True,sell_te=True,rotate=True)]
    assert len(cases)==7
    assert all(c.cash>=0 and c.end_equity>=0 and c.authority=="PAPER_ONLY" for c in cases)
    assert isclose(run().end_equity,3274.0)
    for a,b in ((cases[1],cases[4]),(cases[2],cases[5]),(cases[3],cases[6])):
        assert a.end_equity>b.end_equity
    try: run(rotate=True)
    except ValueError: pass
    else: raise AssertionError("unfunded rotation")
    return cases

if __name__=="__main__":
    for c in test():
        print(f"{c.name:20} ${c.end_equity:.2f} cash=${c.cash:.2f} fees=${c.fees:.2f}")
    print("7/7 scenarios, basic invariants PASS; NOT a historical strategy backtest.")
