import numpy as np
import pandas as pd
from typing import Dict, List
import logging

logger = logging.getLogger(__name__)

def _ema(s, p): return pd.Series(s).ewm(span=p, adjust=False).mean()
def _sma(s, p): return pd.Series(s).rolling(p).mean()
def _rsi(s, p=14):
    s = pd.Series(s); d = s.diff()
    g = d.where(d>0, 0.0); l = -d.where(d<0, 0.0)
    ag = g.ewm(com=p-1, adjust=False).mean()
    al = l.ewm(com=p-1, adjust=False).mean()
    return 100 - (100/(1 + ag/al.replace(0, np.nan)))
def _atr(h, l, c, p=14):
    h=pd.Series(h); l=pd.Series(l); c=pd.Series(c)
    pc=c.shift(1); tr=pd.concat([h-l,(h-pc).abs(),(l-pc).abs()],axis=1).max(axis=1)
    return tr.ewm(span=p, adjust=False).mean()
def _adx(h, l, c, p=14):
    h=pd.Series(h); l=pd.Series(l); c=pd.Series(c)
    ph=h.shift(1); pl=l.shift(1)
    pdm=h-ph; mdm=pl-l
    pdm=pdm.where((pdm>mdm)&(pdm>0), 0.0)
    mdm=mdm.where((mdm>pdm)&(mdm>0), 0.0)
    pc=c.shift(1); tr=pd.concat([h-l,(h-pc).abs(),(l-pc).abs()],axis=1).max(axis=1)
    atr=tr.ewm(span=p, adjust=False).mean()
    pdi=100*pdm.ewm(span=p,adjust=False).mean()/atr
    mdi=100*mdm.ewm(span=p,adjust=False).mean()/atr
    dx=100*(pdi-mdi).abs()/(pdi+mdi).replace(0,np.nan)
    return dx.ewm(span=p,adjust=False).mean(), pdi, mdi


class SniperScore:
    @staticmethod
    def calculate(closes, highs, lows, volumes=None) -> Dict:
        try:
            c=pd.Series(closes); h=pd.Series(highs); l=pd.Series(lows)
            v=pd.Series(volumes) if volumes else pd.Series([1]*len(closes))
            e9=_ema(c,9); e21=_ema(c,21); rsi=_rsi(c)
            m12=_ema(c,12); m26=_ema(c,26); ml=m12-m26; ms=_ema(ml,9)
            adx,pdi,mdi=_adx(h,l,c); va=_sma(v,20)
            bull=0; bear=0
            if e9.iloc[-1]>e21.iloc[-1]: bull+=1
            else: bear+=1
            if rsi.iloc[-1]>50: bull+=1
            else: bear+=1
            if ml.iloc[-1]>ms.iloc[-1]: bull+=1
            else: bear+=1
            if pdi.iloc[-1]>mdi.iloc[-1]: bull+=1
            else: bear+=1
            if adx.iloc[-1]>25: bull+=1
            if volumes and v.iloc[-1]>va.iloc[-1]: bull+=1
            if c.iloc[-1]>e21.iloc[-1]: bull+=1
            else: bear+=1
            atr_val=float(_atr(h,l,c).iloc[-1])
            total=bull+bear
            ema_cross_buy=bool(e9.iloc[-1]>e21.iloc[-1] and e9.iloc[-2]<=e21.iloc[-2])
            ema_cross_sell=bool(e9.iloc[-1]<e21.iloc[-1] and e9.iloc[-2]>=e21.iloc[-2])
            return {
                'bull_score':bull,'bear_score':bear,
                'bull_pct':(bull/total*100) if total else 0,
                'bear_pct':(bear/total*100) if total else 0,
                'bias':'BULL' if bull>bear else 'BEAR' if bear>bull else 'NEUTRAL',
                'atr_risk': atr_val,
                'ema_cross_buy': ema_cross_buy,
                'ema_cross_sell': ema_cross_sell,
            }
        except Exception as e:
            logger.error(f"SniperScore error: {e}")
            return {'bull_score':0,'bear_score':0,'bull_pct':0,'bear_pct':0,'bias':'NEUTRAL','atr_risk':0}


class PrecisionSniperConfluence:
    @staticmethod
    def calculate(closes, highs, lows, volumes=None) -> Dict:
        try:
            c=pd.Series(closes); h=pd.Series(highs); l=pd.Series(lows)
            v=pd.Series(volumes) if volumes else pd.Series([1]*len(closes))
            e9=_ema(c,9); e21=_ema(c,21); e50=_ema(c,50)
            rsi=_rsi(c); m12=_ema(c,12); m26=_ema(c,26)
            ml=m12-m26; ms=_ema(ml,9); mh=ml-ms
            adx,pdi,mdi=_adx(h,l,c); va=_sma(v,20)
            bull=0.0; bear=0.0
            if e9.iloc[-1]>e21.iloc[-1]>e50.iloc[-1]: bull+=2
            elif e9.iloc[-1]<e21.iloc[-1]<e50.iloc[-1]: bear+=2
            rv=rsi.iloc[-1]
            if rv>60: bull+=1.5
            elif rv<40: bear+=1.5
            if mh.iloc[-1]>0 and mh.iloc[-1]>mh.iloc[-2]: bull+=2
            elif mh.iloc[-1]<0 and mh.iloc[-1]<mh.iloc[-2]: bear+=2
            if adx.iloc[-1]>25:
                if pdi.iloc[-1]>mdi.iloc[-1]: bull+=2
                else: bear+=2
            if volumes and v.iloc[-1]>va.iloc[-1]*1.5: bull+=0.5; bear+=0.5
            grade='A+' if bull>=7 else 'A' if bull>=5 else 'B' if bull>=3 else 'C'
            signal='buy' if bull>bear+2 else 'sell' if bear>bull+2 else 'neutral'
            return {'bull_score':bull,'bear_score':bear,'grade':grade,'signal':signal,'adx':float(adx.iloc[-1])}
        except Exception as e:
            logger.error(f"PrecisionSniperConfluence error: {e}")
            return {'bull_score':0,'bear_score':0,'grade':'C'}


class LinearRegressionChannel:
    @staticmethod
    def calculate(closes, highs=None, lows=None, length=20) -> Dict:
        try:
            c=np.array(closes[-length:],dtype=float)
            x=np.arange(length); m,b=np.polyfit(x,c,1)
            lr=m*(length-1)+b
            res=c-(m*x+b); std=np.std(res)
            return {
                'line':float(lr),'upper':float(lr+2*std),
                'lower':float(lr-2*std),
                'angle':float(np.degrees(np.arctan(m))),
                'above_line':float(c[-1])>lr
            }
        except Exception as e:
            logger.error(f"LinearRegressionChannel error: {e}")
            return {}


class SwingProfile:
    @staticmethod
    def calculate(closes, highs, lows, volumes=None) -> Dict:
        try:
            trend='UPTREND' if closes[-1]>np.mean(closes[-20:]) else 'DOWNTREND'
            return {
                'trend':trend,
                'last_high':max(highs[-20:]),
                'last_low':min(lows[-20:])
            }
        except Exception as e:
            logger.error(f"SwingProfile error: {e}")
            return {}


class FairValueGaps:
    @staticmethod
    def calculate(closes, highs, lows) -> Dict:
        try:
            gaps=[]
            for i in range(2,min(len(closes),50)):
                ph=highs[i-2]; pl=lows[i-2]
                ch=highs[i];   cl=lows[i]
                if cl>ph: gaps.append({'type':'BULLISH','low':ph,'high':cl,'mid':(ph+cl)/2})
                elif ch<pl: gaps.append({'type':'BEARISH','low':ch,'high':pl,'mid':(ch+pl)/2})
            return {'gaps':gaps[-3:] if gaps else []}
        except Exception as e:
            logger.error(f"FairValueGaps error: {e}")
            return {'gaps':[]}


class CommissionAwareSignalEngine:
    def __init__(self, commission_rate=0.001):
        self.commission_rate=commission_rate

    @staticmethod
    def evaluate_trade_viability(entry_price, stop_loss, take_profit, commission_rate=0.001) -> Dict:
        try:
            risk=abs(entry_price-stop_loss)
            reward=abs(take_profit-entry_price)
            cost=entry_price*commission_rate*2
            rr=reward/risk if risk>0 else 0
            profit_pct=round((reward/entry_price)*100, 4) if entry_price>0 else 0
            return {
                'viable': reward>cost*3 and rr>=1.5,
                'rr_ratio': round(rr,2),
                'commission_cost': round(cost,6),
                'potential_profit': round(reward,6),
                'profit_pct': profit_pct,
            }
        except Exception as e:
            logger.error(f"CommissionAwareSignalEngine error: {e}")
            return {'viable':False,'rr_ratio':0,'commission_cost':0,'potential_profit':0}


class IchimokuCloud:
    @staticmethod
    def calculate(closes, highs, lows) -> Dict:
        try:
            h=pd.Series(highs); l=pd.Series(lows); c=pd.Series(closes)
            tenkan=(h.rolling(9).max()+l.rolling(9).min())/2
            kijun=(h.rolling(26).max()+l.rolling(26).min())/2
            sa=((tenkan+kijun)/2).shift(26)
            sb=((h.rolling(52).max()+l.rolling(52).min())/2).shift(26)
            price=float(c.iloc[-1])
            ct=float(sa.iloc[-1]) if not pd.isna(sa.iloc[-1]) else price
            cb=float(sb.iloc[-1]) if not pd.isna(sb.iloc[-1]) else price
            cloud_top=max(ct,cb); cloud_bot=min(ct,cb)
            signal='bull' if price>cloud_top else 'bear' if price<cloud_bot else 'neutral'
            return {
                'tenkan':float(tenkan.iloc[-1]),'kijun':float(kijun.iloc[-1]),
                'senkou_a':ct,'senkou_b':cb,'signal':signal,
                'above_cloud':price>cloud_top,'below_cloud':price<cloud_bot
            }
        except Exception as e:
            logger.error(f"IchimokuCloud error: {e}")
            return {'signal':'neutral','above_cloud':False,'below_cloud':False}


class NeuroTrendII:
    @staticmethod
    def calculate(closes, highs, lows, volumes=None) -> Dict:
        try:
            c=pd.Series(closes); h=pd.Series(highs); l=pd.Series(lows)
            ema=_ema(c,20); atr=_atr(h,l,c,14)
            trend='up' if c.iloc[-1]>ema.iloc[-1] else 'down'
            strength=float(abs(c.iloc[-1]-ema.iloc[-1])/atr.iloc[-1]) if atr.iloc[-1]>0 else 0
            slope_power=round(float((c.iloc[-1]-ema.iloc[-1])/atr.iloc[-1]) if atr.iloc[-1]>0 else 0, 2)
            return {
                'trend':trend,
                'trend_direction':'Bullish' if trend=='up' else 'Bearish',
                'phase':'Expansion' if strength>1.0 else 'Contraction',
                'confidence':min(int(strength*50), 100),
                'slope_power':slope_power,
                'ema':float(ema.iloc[-1]),
                'upper_band':float(ema.iloc[-1]+atr.iloc[-1]*2),
                'lower_band':float(ema.iloc[-1]-atr.iloc[-1]*2),
                'strength':strength,
            }
        except Exception as e:
            logger.error(f"NeuroTrendII error: {e}")
            return {'trend':'neutral','strength':0}


class SuperTrendedRSI:
    @staticmethod
    def calculate(closes, highs, lows) -> Dict:
        try:
            c=pd.Series(closes); h=pd.Series(highs); l=pd.Series(lows)
            rsi=_rsi(c); atr=_atr(h,l,c,10)
            hl2=(h+l)/2
            rv=float(rsi.iloc[-1])
            signal='buy' if rv<30 else 'sell' if rv>70 else 'neutral'
            trend='bullish' if rv>=50 else 'bearish'
            return {
                'rsi':rv,'signal':signal,'trend':trend,
                'upper_band':float(hl2.iloc[-1]+atr.iloc[-1]*3),
                'lower_band':float(hl2.iloc[-1]-atr.iloc[-1]*3),
                'overbought':rv>70,'oversold':rv<30
            }
        except Exception as e:
            logger.error(f"SuperTrendedRSI error: {e}")
            return {'rsi':50,'signal':'neutral'}


class TurtleChannels:
    @staticmethod
    def calculate(closes, highs, lows, period=20) -> Dict:
        try:
            h=pd.Series(highs); l=pd.Series(lows); c=pd.Series(closes)
            upper=h.rolling(period).max()
            lower=l.rolling(period).min()
            mid=(upper+lower)/2
            price=float(c.iloc[-1])
            u=float(upper.iloc[-1]); lo=float(lower.iloc[-1])
            signal='buy' if price>=u else 'sell' if price<=lo else 'neutral'
            return {
                'upper_channel':u,'lower_channel':lo,'middle':float(mid.iloc[-1]),
                'signal':signal,'breakout_up':price>=u,'breakout_down':price<=lo
            }
        except Exception as e:
            logger.error(f"TurtleChannels error: {e}")
            return {'signal':'neutral','breakout_up':False,'breakout_down':False}


# ─────────────────────────────────────────────────────────────────────────────
# Indicadores profesionales adicionales (muy usados por exchanges/instituciones)
# ─────────────────────────────────────────────────────────────────────────────

class VWAP:
    """Volume Weighted Average Price — precio medio ponderado por volumen."""
    @staticmethod
    def calculate(closes, highs, lows, volumes) -> Dict:
        try:
            h=pd.Series(highs); l=pd.Series(lows); c=pd.Series(closes); v=pd.Series(volumes)
            tp=(h+l+c)/3
            cum_v=v.cumsum().replace(0, np.nan)
            vwap=(tp*v).cumsum()/cum_v
            price=float(c.iloc[-1]); val=float(vwap.iloc[-1])
            return {'vwap':val,'above':price>val,
                    'distance_pct':round((price-val)/val*100, 3) if val else 0}
        except Exception as e:
            logger.error(f"VWAP error: {e}"); return {'vwap':0,'above':False}


class OBV:
    """On-Balance Volume — acumulación/distribución por volumen y dirección."""
    @staticmethod
    def calculate(closes, volumes) -> Dict:
        try:
            c=pd.Series(closes); v=pd.Series(volumes)
            direction=np.sign(c.diff()).fillna(0)
            obv=(direction*v).cumsum()
            slope=float(obv.iloc[-1]-obv.iloc[-10]) if len(obv)>10 else 0
            return {'obv':float(obv.iloc[-1]),
                    'trend':'up' if slope>0 else 'down' if slope<0 else 'flat','rising':slope>0}
        except Exception as e:
            logger.error(f"OBV error: {e}"); return {'obv':0,'trend':'flat'}


class ADXIndicator:
    """Average Directional Index — fuerza de la tendencia (>25 = tendencia fuerte)."""
    @staticmethod
    def calculate(closes, highs, lows, period=14) -> Dict:
        try:
            adx,pdi,mdi=_adx(highs,lows,closes,period)
            a=float(adx.iloc[-1]); p=float(pdi.iloc[-1]); m=float(mdi.iloc[-1])
            return {'adx':round(a,2),'plus_di':round(p,2),'minus_di':round(m,2),
                    'strong':a>25,'direction':'bullish' if p>m else 'bearish'}
        except Exception as e:
            logger.error(f"ADX error: {e}"); return {'adx':0,'strong':False}


class CVD:
    """Cumulative Volume Delta — presión compradora vs vendedora acumulada."""
    @staticmethod
    def calculate(closes, opens, volumes) -> Dict:
        try:
            c=pd.Series(closes)
            o=pd.Series(opens) if opens is not None and len(opens) else c.shift(1).fillna(c.iloc[0])
            v=pd.Series(volumes)
            delta=np.where(c>=o, v, -v)
            cvd=pd.Series(delta).cumsum()
            slope=float(cvd.iloc[-1]-cvd.iloc[-10]) if len(cvd)>10 else 0
            return {'cvd':float(cvd.iloc[-1]),
                    'pressure':'buyers' if slope>0 else 'sellers' if slope<0 else 'neutral'}
        except Exception as e:
            logger.error(f"CVD error: {e}"); return {'cvd':0,'pressure':'neutral'}


class MFI:
    """Money Flow Index — RSI ponderado por volumen (sobrecompra>80, sobreventa<20)."""
    @staticmethod
    def calculate(closes, highs, lows, volumes, period=14) -> Dict:
        try:
            h=pd.Series(highs); l=pd.Series(lows); c=pd.Series(closes); v=pd.Series(volumes)
            tp=(h+l+c)/3; mf=tp*v
            pos=mf.where(tp>tp.shift(1), 0.0).rolling(period).sum()
            neg=mf.where(tp<tp.shift(1), 0.0).rolling(period).sum().replace(0, np.nan)
            mfi=100-(100/(1+pos/neg))
            val=float(mfi.iloc[-1])
            return {'mfi':round(val,2),'overbought':val>80,'oversold':val<20,
                    'signal':'sell' if val>80 else 'buy' if val<20 else 'neutral'}
        except Exception as e:
            logger.error(f"MFI error: {e}"); return {'mfi':50,'signal':'neutral'}


# Clase principal para compatibilidad con código que use AdvancedIndicators()
class AdvancedIndicators:
    def get_all_advanced(self, klines):
        if not klines or len(klines)<50: return {}
        closes=[float(k[4]) for k in klines]
        highs=[float(k[2]) for k in klines]
        lows=[float(k[3]) for k in klines]
        volumes=[float(k[5]) for k in klines]
        return {
            'sniper_score':     SniperScore.calculate(closes,highs,lows,volumes),
            'confluence_score': PrecisionSniperConfluence.calculate(closes,highs,lows,volumes),
            'linear_regression':LinearRegressionChannel.calculate(closes,highs,lows),
            'swing_profile':    SwingProfile.calculate(closes,highs,lows,volumes),
            'fvg':              FairValueGaps.calculate(closes,highs,lows),
            'ichimoku':         IchimokuCloud.calculate(closes,highs,lows),
            'neurotrend':       NeuroTrendII.calculate(closes,highs,lows,volumes),
            'st_rsi':           SuperTrendedRSI.calculate(closes,highs,lows),
            'turtle':           TurtleChannels.calculate(closes,highs,lows),
        }
