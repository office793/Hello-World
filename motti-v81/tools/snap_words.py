import sys, wave, numpy as np, json
w = wave.open(sys.argv[1]); sr = w.getframerate(); n = w.getnframes(); ch = w.getnchannels(); sw = w.getsampwidth()
raw = w.readframes(n)
if sw == 3:
    b = np.frombuffer(raw, np.uint8).reshape(-1, 3)
    a = (b[:, 0].astype(np.int32) | (b[:, 1].astype(np.int32) << 8) | (b[:, 2].astype(np.int32) << 16))
    a = np.where(a >= 1 << 23, a - (1 << 24), a).astype(np.float32) / (1 << 23)
else:
    a = np.frombuffer(raw, np.int16).astype(np.float32) / 32768
a = a.reshape(-1, ch).mean(1)
hop = int(sr * 0.01)
e = np.array([np.sqrt(np.mean(a[i:i + hop * 2] ** 2) + 1e-12) for i in range(0, len(a) - hop * 2, hop)])
edb = 20 * np.log10(e / e.max())
words = [("עדכון",0.04),("חדש",0.40),("מבית",0.78),("מוטי",1.30),("רוזנפלד",1.62),("היכנסו",2.22),("עכשיו",2.85),("לאתר",3.25),("והאזינו",3.62),("לעדכון",4.25),("החדש",4.70),("תוכלו",5.25),("לדפדף",5.65),("בין",6.00),("התכנים",6.30),("להאזין",6.75),("ולהתרשם",7.40),("מכל",8.05),("מה",8.34),("שנוסף",8.60),("בסט",9.00)]
out = []
for wd, t in words:
    i0 = max(0, int((t - 0.07) / 0.01)); i1 = min(len(edb) - 1, int((t + 0.07) / 0.01))
    j = i0 + int(np.argmin(edb[i0:i1 + 1]))
    ts = j * 0.01 + 0.01
    out.append({"w": wd, "est": t, "snap": round(ts, 2), "dip_db": round(float(edb[j]), 1), "frame": int(round(ts * 25))})
for o in out: print(o)
json.dump(out, open(sys.argv[2], "w"), ensure_ascii=False, indent=1)
