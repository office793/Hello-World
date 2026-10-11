import sys, wave, numpy as np, sherpa_onnx
M=sys.argv[1]; wav=sys.argv[2]; segs=sys.argv[3:]
rec=sherpa_onnx.OfflineRecognizer.from_whisper(encoder=M+"/turbo-encoder.int8.onnx",decoder=M+"/turbo-decoder.int8.onnx",tokens=M+"/turbo-tokens.txt",language="he",task="transcribe",num_threads=4)
w=wave.open(wav); sr=w.getframerate(); a=np.frombuffer(w.readframes(w.getnframes()),dtype=np.int16).astype(np.float32)/32768
pad=np.zeros(int(sr*0.8),dtype=np.float32)
for s in segs:
    t0,t1=map(float,s.split('-')); x=np.concatenate([pad,a[int(t0*sr):int(t1*sr)],pad])
    st=rec.create_stream(); st.accept_waveform(sr,x); rec.decode_stream(st)
    print(f"[{t0:5.2f}-{t1:5.2f}] {st.result.text}", flush=True)
