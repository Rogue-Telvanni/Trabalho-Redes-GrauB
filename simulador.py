import numpy as np
from math import erfc, sqrt
def texto_para_bits(t): return np.unpackbits(np.frombuffer(t.encode('ascii'),dtype=np.uint8))
def bits_para_texto(b): return np.packbits(b).tobytes().decode('ascii',errors='replace')
def mod_bpsk(b): return (2.0*b-1)+0j
def dem_bpsk(s): return (s.real>0).astype(np.uint8)
def mod_qpsk(b):
    b=b.reshape(-1,2); return ((2.0*b[:,0]-1)+1j*(2.0*b[:,1]-1))/sqrt(2)
def dem_qpsk(s): return np.column_stack([s.real>0,s.imag>0]).astype(np.uint8).ravel()
def mod_16qam(b):
    b=b.reshape(-1,4)
    eixo=lambda a,c:(2.0*a-1)*(3-2.0*c)
    return (eixo(b[:,0],b[:,1])+1j*eixo(b[:,2],b[:,3]))/sqrt(10)
def dem_16qam(s):
    s=s*sqrt(10)
    return np.column_stack([s.real>0,abs(s.real)<2,s.imag>0,abs(s.imag)<2]).astype(np.uint8).ravel()
def awgn(s,ebn0_db,k,rng):
    n0=1/(k*10**(ebn0_db/10)); sigma=sqrt(n0/2)
    return s+sigma*(rng.standard_normal(s.shape)+1j*rng.standard_normal(s.shape))
def line_man(b):
    return np.column_stack([2.0*b-1,1-2.0*b]).ravel()/sqrt(2)
def dem_man(r):
    r=r.reshape(-1,2); return (r[:,0]>r[:,1]).astype(np.uint8)
def line_ami(b):
    s=np.zeros(len(b)); u=np.flatnonzero(b)
    s[u]=sqrt(2)*(1-2*(np.arange(len(u))%2)); return s
def dem_ami(r): return (abs(r)>sqrt(2)/2).astype(np.uint8)
Q=lambda x:0.5*erfc(x/sqrt(2))
rng=np.random.default_rng(1)
msg="Ola, Redes 2!"
for n,m,d,k in [("BPSK",mod_bpsk,dem_bpsk,1),("QPSK",mod_qpsk,dem_qpsk,2),("16QAM",mod_16qam,dem_16qam,4)]:
    b=texto_para_bits(msg); pad=(-len(b))%k
    r=d(awgn(m(np.concatenate([b,np.zeros(pad,np.uint8)])),40,k,rng))[:len(b)]
    print(n,bits_para_texto(r),(r!=b).sum())
    p=np.mean(m(rng.integers(0,2,400000,dtype=np.uint8))*np.conj(m(rng.integers(0,2,400000,dtype=np.uint8)))) if 0 else None
    for e in (4,8):
        b=rng.integers(0,2,2000000,dtype=np.uint8)
        s=m(b); ber=(d(awgn(s,e,k,rng))!=b).mean()
        x=10**(e/10)
        th={1:Q(sqrt(2*x)),2:Q(sqrt(2*x)),4:0.75*Q(sqrt(0.8*x))}[k]
        print(' ',e,'dB P=%.3f ber=%.3e th=%.3e'%(np.mean(abs(s)**2),ber,th))
for e in (4,8):
    b=rng.integers(0,2,2000000,dtype=np.uint8); x=10**(e/10); sig=sqrt(1/x/2)
    print('man',e,(dem_man(line_man(b)+sig*rng.standard_normal(4000000))!=b).mean(),Q(sqrt(2*x)))
    print('ami',e,(dem_ami(line_ami(b)+sig*rng.standard_normal(2000000))!=b).mean(),1.5*Q(sqrt(x)))
for e in (10,12):
    x=10**(e/10);print(e,'bpsk',Q(sqrt(2*x)),'16qam',0.75*Q(sqrt(.8*x)))
